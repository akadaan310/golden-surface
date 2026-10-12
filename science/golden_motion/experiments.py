"""GM-001/004/005 comparable deterministic synthetic trials and negative controls."""
import dataclasses
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
import numpy as np
import scipy
from . import MODEL_VERSION
from .model import *
from .adapters import BLEAdapter, RSSICalibration

SEED=20261012
EPOCH_MS=1791763200000


def common_trajectory(count=121,dt=1/30):
    t=np.arange(count)*dt
    p=np.column_stack([.06*np.sin(1.3*t),.04*np.cos(.9*t),.28+.035*np.sin(1.1*t)+.015*t])
    v=np.column_stack([.078*np.cos(1.3*t),-.036*np.sin(.9*t),.0385*np.cos(1.1*t)+.015])
    return t,p,v


def synthetic_optical(position,*,seed=0,noise_std=.003,image_bias=(0.,0.)):
    """Calibrated pinhole image coordinates; no depth observation.

    For this experiment ONLY the synthetic camera is colocated with acoustic
    origin, z is optical forward, principal point (.5,.5), focal length .7.
    Phone camera extrinsics and intrinsics have not been measured.
    """
    p=np.asarray(position,dtype=float)
    if p.shape!=(3,) or not np.isfinite(p).all() or p[2]<=0 or not np.isfinite(noise_std) or noise_std<0:
        raise ValueError('invalid optical input')
    image=.5+.7*p[:2]/p[2]+np.random.default_rng(seed).normal(0,noise_std,2)+np.asarray(image_bias)
    ray=np.r_[(image-.5)/.7,1.]; ray=ray/np.linalg.norm(ray)
    return {'image':image.tolist(),'bearing':ray.tolist(),'coordinateFrame':'camera-image-normalized',
            'source':'synthetic','confidence':.95,'imageStd':noise_std,'depthObserved':False}


def fusion_observability(position):
    p=np.asarray(position,dtype=float);x,y,z=p
    if p.shape!=(3,) or not np.isfinite(p).all() or z<=0:
        raise ValueError('invalid camera position')
    range_jac=(p/np.linalg.norm(p))[None,:]
    optical_jac=np.array([[.7/z,0.,-.7*x/z**2],[0.,.7/z,-.7*y/z**2]])
    combined=np.vstack([range_jac,optical_jac])
    return {'rankRange':int(np.linalg.matrix_rank(range_jac)),
        'rankOptical':int(np.linalg.matrix_rank(optical_jac)),
        'rankCombined':int(np.linalg.matrix_rank(combined)),
        'combinedSingularValues':np.linalg.svd(combined,compute_uv=False).tolist(),
        'combinedJacobian':combined.tolist(),'localOnly':True}


def rmse(estimate,truth):
    difference=np.asarray(estimate)-np.asarray(truth)
    return float(np.sqrt(np.mean(np.sum(difference*difference,axis=1)))) if difference.ndim==2 else float(np.sqrt(np.mean(difference*difference)))


def run_common_experiment():
    t,positions,velocities=common_trajectory(); dt=float(t[1]-t[0]); cfg=AcousticConfig()
    truth_ranges=np.linalg.norm(positions,axis=1)
    truth_rates=np.sum(positions*velocities,axis=1)/truth_ranges
    delays=[]; dopplers=[]; phases=[]; optical=[]; costs=[]; trace_signal=None
    for i,(p,v) in enumerate(zip(positions,velocities)):
        start=time.perf_counter_ns(); signal=simulate_echo(p,v,cfg,seed=SEED+i)
        delay=estimate_delay(signal,cfg); echo_elapsed=time.perf_counter_ns()-start
        start=time.perf_counter_ns(); tone=simulate_tone(p,v,cfg,seed=SEED+1000+i,duration_s=.025)
        doppler=estimate_doppler(tone,cfg)
        phases.append(np.mean(tone.received*np.conjugate(tone.transmitted)))
        costs.append([echo_elapsed/1e6,(time.perf_counter_ns()-start)/1e6])
        delays.append(delay); dopplers.append(doppler)
        optical.append(synthetic_optical(p,seed=SEED+2000+i))
        if i==0: trace_signal=signal
    ranges=np.array([d['range_m'] for d in delays]); radial=np.array([d['radial_velocity_m_s'] for d in dopplers])
    phase_range=np.r_[ranges[0],ranges[0]+np.cumsum([phase_displacement(a,b,cfg) for a,b in zip(phases[:-1],phases[1:])])]
    integrated_doppler=np.r_[ranges[0],ranges[0]+np.cumsum((radial[:-1]+radial[1:])*dt/2)]
    state=filter_range_velocity(ranges,radial,dt,range_std=.001,velocity_std=.001)
    rays=np.asarray([o['bearing'] for o in optical]); fused=rays*ranges[:,None]
    initial_ray=positions[0]/truth_ranges[0]
    acoustic_anchored=ranges[:,None]*initial_ray[None,:]
    optical_anchored=rays*ranges[0]
    corrupted_rays=np.array([synthetic_optical(p,seed=SEED+i,image_bias=(.15,0))['bearing'] for i,p in enumerate(positions)])
    corrupted_fused=corrupted_rays*ranges[:,None]
    rng=np.random.default_rng(SEED+3000); calibration=RSSICalibration(); adapter=BLEAdapter('synthetic-tag',source='synthetic',calibration=calibration)
    rssi=calibration.tx_power_at_one_m_dbm-10*calibration.path_loss_exponent*np.log10(truth_ranges)+rng.normal(0,calibration.rssi_std_db,len(t))
    ble=[]; ble_ranges=[]; ble_body=[]
    for i,value in enumerate(rssi):
        measurement=adapter.ingest(EPOCH_MS+round(t[i]*1000),float(value)); ble.append(measurement)
        ble_ranges.append(measurement['metadata']['scalarRangeEstimateM'])
        ble_body.append(calibration.range_estimate(value-6)[0])
    bearing_error=np.arccos(np.clip(np.sum(rays*positions/truth_ranges[:,None],axis=1),-1,1))
    metrics={
      'GM-001':{'name':'Acoustic scalar range and rate comparison','matched_filter_range_rmse_m':rmse(ranges,truth_ranges),
          'phase_anchored_range_rmse_m':rmse(phase_range,truth_ranges),'doppler_integrated_range_rmse_m':rmse(integrated_doppler,truth_ranges),
          'kalman_range_rmse_m':rmse(state[:,0],truth_ranges),'doppler_radial_velocity_rmse_m_s':rmse(radial,truth_rates),
          'accepted_fraction':float(np.mean([d['valid'] for d in delays])),'scalar_only_position_rmse_m':None,
          'phase_unambiguous_step_m':cfg.sound_speed_m_s/(4*cfg.carrier_hz),
          'reasonNoSpatialScore':'Single half-path and radial rate leave angular directions unobserved.'},
      'GM-004':{'name':'Synthetic calibrated range and optical ray fusion','optical_bearing_rmse_rad':rmse(bearing_error,np.zeros_like(bearing_error)),
          'fused_position_rmse_m':rmse(fused,positions),'acoustic_anchored_bearing_prior_position_rmse_m':rmse(acoustic_anchored,positions),
          'optical_anchored_prior_position_rmse_m':rmse(optical_anchored,positions),
          'corrupt_optical_fused_position_rmse_m':rmse(corrupted_fused,positions),
          'fusionHelps':rmse(fused,positions)<min(rmse(acoustic_anchored,positions),rmse(optical_anchored,positions)),
          'failure':'Unmodeled 0.15 image-coordinate bias makes fusion worse; no calibration claim.',
          'opticalOnlyDepthObserved':False,**fusion_observability(positions[0])},
      'GM-005':{'name':'BLE scalar alternative requiring instrumented tag','rssi_range_rmse_m':rmse(ble_ranges,truth_ranges),
          'body_attenuated_range_rmse_m':rmse(ble_body,truth_ranges),'noise_std_db':calibration.rssi_std_db,
          'path_loss_exponent':calibration.path_loss_exponent,'body_attenuation_db':6,
          'claim':'Log-distance model only; no bare-hand localization and no BLE hardware connected.'},
      'costs':{'measurement':'wall-clock per simulated frame incl estimator; does not measure hardware latency',
          'echo_ms_mean':float(np.mean(np.array(costs)[:,0])),'echo_ms_p95':float(np.percentile(np.array(costs)[:,0],95)),
          'tone_ms_mean':float(np.mean(np.array(costs)[:,1])),'tone_ms_p95':float(np.percentile(np.array(costs)[:,1],95))}}
    frames=[]
    for i,instant in enumerate(t):
        frames.append({'timestampMs':EPOCH_MS+round(instant*1000),'elapsedS':float(instant),
            'truth':{'positionM':positions[i].tolist(),'velocityMps':velocities[i].tolist(),'rangeM':float(truth_ranges[i]),'radialVelocityMps':float(truth_rates[i])},
            'acoustic':{'source':'synthetic','coordinateFrame':'measurement-space','rangeM':float(ranges[i]),'phaseRangeM':float(phase_range[i]),
                'dopplerIntegratedRangeM':float(integrated_doppler[i]),'filteredRangeM':float(state[i,0]),'radialVelocityMps':float(radial[i]),
                'dopplerHz':float(dopplers[i]['frequency_hz']),'confidence':delays[i]['confidence'],'valid':delays[i]['valid']},
            'optical':optical[i],'fused':{'positionM':fused[i].tolist(),'coordinateFrame':'phone-local-m','source':'synthetic','calibrationId':'synthetic-colocated-pinhole-v1'},
            'ble':ble[i]})
    stride=8
    fixture={'schemaVersion':1,'source':'synthetic','modelVersion':MODEL_VERSION,'seed':SEED,
        'units':{'timestampMs':'epoch milliseconds','positionM':'m','velocityMps':'m/s','rangeM':'m equivalent half-path','image':'normalized image coordinates','dopplerHz':'Hz'},
        'assumptions':['Analytic complex chirp and continuous tone; quasi-static path; no physical sensor response.',
            'Optical pinhole and acoustic origin are colocated with known synthetic intrinsics/extrinsics.',
            'Fusion position exists only because calibrated optical ray and acoustic range are combined.',
            'Phase/Doppler tracks are anchored to first matched-filter range, not truth.','BLE requires a transmitting tag; RSSI calibration is synthetic.'],
        'frames':frames,'traces':{'timeS':trace_signal.time_s[::stride].tolist(),'transmittedReal':trace_signal.transmitted.real[::stride].tolist(),
            'receivedReal':trace_signal.received.real[::stride].tolist(),'sampleRateHz':cfg.sample_rate_hz,'plotDecimation':stride,
            'decimationWarning':'Trace is decimated for display; do not estimate frequency from these arrays.'},
        'experiments':metrics}
    return metrics,fixture


def run_controls():
    base=AcousticConfig(); configurations={
      'baseline':(base,base,()),
      'high_noise':(dataclasses.replace(base,noise_std=.6),base,()),
      'weak_multipath':(base,base,((.06,.35),)),
      'dominant_multipath':(base,base,((.09,1.8),)),
      'sound_speed_mismatch':(dataclasses.replace(base,sound_speed_m_s=331.),base,()),
      'clock_offset_400us':(dataclasses.replace(base,clock_offset_s=.0004),base,()),
      'direct_leakage':(dataclasses.replace(base,leakage_gain=2.),base,())}
    controls={}
    for name,(forward,estimator,reflections) in configurations.items():
        estimates=[]; valid=[]
        for i in range(48):
            radius=.12+i*.006
            signal=simulate_echo([0,0,radius],[0,0,0],forward,seed=SEED+4000+i,reflections=reflections)
            est=estimate_delay(signal,estimator); estimates.append(est['range_m']-radius); valid.append(est['valid'])
        controls[name]={'range_rmse_m':rmse(estimates,np.zeros(len(estimates))),'bias_m':float(np.mean(estimates)),
                        'accepted_fraction':float(np.mean(valid)),'trials':48}
    false_accepts=0
    for i in range(100):
        sig=simulate_echo([0,0,.2],[0,0,0],base,seed=SEED+5000+i,hand_present=False)
        false_accepts+=estimate_delay(sig,base)['valid']
    controls['no_hand']={'false_accepts':int(false_accepts),'trials':100,'source':'synthetic noise only'}
    leakage_cfg=dataclasses.replace(base,leakage_gain=2.)
    background=simulate_echo([0,0,.2],[0,0,0],leakage_cfg,seed=SEED+5999,hand_present=False)
    leakage_false=0;calibrated_false=0;calibrated_error=[]
    for i in range(100):
        absent=simulate_echo([0,0,.2],[0,0,0],leakage_cfg,seed=SEED+6000+i,hand_present=False)
        leakage_false+=estimate_delay(absent,leakage_cfg)['valid']
        calibrated_false+=estimate_delay(absent,leakage_cfg,background=background)['valid']
        hand=simulate_echo([0,0,.2],[0,0,0],leakage_cfg,seed=SEED+7000+i)
        calibrated_error.append(estimate_delay(hand,leakage_cfg,background=background)['range_m']-.2)
    controls['no_hand_direct_leakage']={'raw_false_accepts':int(leakage_false),'background_subtracted_false_accepts':int(calibrated_false),
        'calibrated_range_rmse_m':rmse(calibrated_error,np.zeros(100)),'trials':100,
        'failedHypothesis':'Normalized correlation alone cannot distinguish static direct leakage from a hand echo.',
        'calibrationAssumption':'Measured no-hand background is unchanged except independent additive noise; moving environmental clutter not canceled.'}
    drift_cfg=dataclasses.replace(base,noise_std=0,clock_rate_error=200e-6)
    drift=estimate_doppler(simulate_tone([0,0,.3],[0,0,0],drift_cfg),base)
    controls['clock_drift_200ppm']={'clockRateError':200e-6,'trueVelocityMps':0.,'estimatedRadialVelocityMps':drift['radial_velocity_m_s'],
        'estimatedDopplerHz':drift['frequency_hz'],'confounding':'Carrier clock drift is indistinguishable from target range rate without a reference.'}
    controls['dropout']={'policy':'No measurement is produced from absent acquisition; state expiration belongs to ISI SDK.','rangeEstimateM':None}
    cfg=dataclasses.replace(base,noise_std=0.)
    p0=simulate_tone([0,0,.2],[0,0,0],cfg,duration_s=.005)
    p1=simulate_tone([0,0,.213],[0,0,0],cfg,duration_s=.005)
    controls['phase_alias']={'true_step_m':.013,'estimated_wrapped_step_m':phase_displacement(p0.received[0],p1.received[0],cfg),
                             'phase_period_m':cfg.sound_speed_m_s/(2*cfg.carrier_hz),'hypothesis':'Pure phase does not determine absolute range.'}
    p=np.array([.1,.2,.3]); zero=np.zeros((1,3)); array=np.array([[0,0,0],[.4,0,0],[0,.4,0],[0,0,.4]])
    line=np.array([[0,0,0],[.1,0,0],[.2,0,0]])
    controls['observability']={'single_pair':observability(p,zero,zero),'noncoplanar_array':observability(p,array,array),
       'collinear_target_on_axis':observability([.3,0,0],line,line),
       'symmetry':'With monostatic origin, [0.1,0.2,0.3] and [-0.1,0.2,0.3] have identical range.'}
    return controls


def main():
    output=Path(__file__).resolve().parents[1]/'results'; output.mkdir(exist_ok=True)
    metrics,fixture=run_common_experiment()
    results={'schemaVersion':1,'modelVersion':MODEL_VERSION,'source':'synthetic','seed':SEED,
        'physicalValidation':False,'experiments':metrics,'controls':run_controls(),
        'environment':{'python':sys.version.split()[0],'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform()},
        'configuration':dataclasses.asdict(AcousticConfig())}
    (output/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    (output/'browser-fixture.json').write_text(json.dumps(fixture,separators=(',',':'),allow_nan=False)+'\n')
    manifest={'sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ('results.json','browser-fixture.json')},
        'determinism':'Signals and metrics deterministic; wall-clock cost measurements intentionally vary.',
        'dependencies':results['environment'],'seed':SEED,'modelVersion':MODEL_VERSION}
    (output/'environment-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))

if __name__=='__main__': main()
