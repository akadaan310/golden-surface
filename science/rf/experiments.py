"""GM-RF-001/002/006/007 deterministic synthetic falsification experiments.
Runs 40 fixed seeds for CSI/RSSI; preserves weak, blind, and confounded failures.
"""
from dataclasses import replace
from pathlib import Path
import json,hashlib,sys,platform
import numpy as np
from kernel import RFConfig,csi_forward,estimate_csi,rssi_forward,estimate_rssi,fisher_geometry,fuse_presence,C
ROOT=Path(__file__).parent
SEEDS=list(range(101,141))
def wilson(k,n,z=1.96):
 p=k/n;d=1+z*z/n;center=(p+z*z/(2*n))/d;half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return [float(max(0,center-half)),float(min(1,center+half))]
def interval(x,seed=37):
 a=np.asarray(x,float)
 if not len(a):return None
 rng=np.random.default_rng(seed);boot=rng.choice(a,(2000,len(a)),replace=True).mean(axis=1)
 return [float(np.quantile(boot,.025)),float(np.quantile(boot,.975))]
def raw_phase_baseline(t,h,valid,c):
 """Naive one-antenna phase velocity: expected to fail on oscillator offset."""
 tv=t[valid];phase=np.unwrap(np.angle(h[valid,0,c.subcarriers//2]));slope=np.polyfit(tv,phase,1)[0]
 return {'presence':bool(abs(slope)>2*np.pi*.3),'path_rate_mps':float(abs(slope)*C/(2*np.pi*c.carrier))}
def main():
 base=RFConfig();cases={
 'nominal_moving':(base,True),
 'no_hand_static':(replace(base,velocity=(0,0,0)),False),
 'no_reflector':(replace(base,amplitude=0),False),
 'strong_common_CFO':(replace(base,velocity=(0,0,0),cfo_hz=43,phase_noise=.2,sfo_ppm=100),False),
 'clock_drift_2000ppm':(replace(base,clock_drift_ppm=2000),True),
 'noise_005':(replace(base,noise=.05),True),
 'noise_020':(replace(base,noise=.2),True),
 'loss_50percent':(replace(base,packet_loss=.5),True),
 'weak_reflector':(replace(base,amplitude=.08),True),
 'iso_delay_movement':(replace(base,iso_delay=True),True),
 'independent_antenna_drift_no_hand':(replace(base,velocity=(0,0,0),independent_phase_drift_hz=3),False),
 'multiple_opposed_movers':(replace(base,extra_movers=(((.5,1.1,.15),(0,-.10,0),.55),)),True),
 'one_antenna_unobservable':(replace(base,antenna_count=1),True),
 }
 summaries={};trials=[]
 for name,(c,truth) in cases.items():
  det=0;rawdet=0;errors=[];cover=0;conf=[];brier=[]
  for seed in SEEDS:
   t,h,rate,valid=csi_forward(c,seed=seed);e=estimate_csi(t,h,valid,c);raw=raw_phase_baseline(t,h,valid,c)
   det+=e['presence'];rawdet+=raw['presence'];conf.append(e['confidence']);p=.5 if e['quality']=='unobservable' else (e['confidence'] if e['presence'] else 1-e['confidence']);brier.append((p-truth)**2)
   err=None
   if e['presence']:
    err=abs(e['path_rate_mps']-abs(float(np.median(rate))));errors.append(err);cover+=err<=e['uncertainty_mps']
   trials.append({'scenario':name,'seed':seed,'motion_truth':truth,'truth_median_abs_path_rate_mps':abs(float(np.median(rate))),'estimate':e,'raw_phase_baseline':raw,'absolute_error_mps':err})
  n=len(SEEDS)
  summaries[name]={'motion_truth':truth,'n':n,'detection_rate':det/n,'detection_rate_wilson_95':wilson(det,n),'false_positive_rate':det/n if not truth else None,'naive_raw_phase_detection_rate':rawdet/n,'mean_detected_absolute_error_mps':float(np.mean(errors)) if errors else None,'error_bootstrap_mean_95':interval(errors),'bin_resolution_coverage':cover/len(errors) if errors else None,'mean_heuristic_confidence':float(np.mean(conf)),'brier_score':float(np.mean(brier))}
 rssi={};rssi_trials=[]
 for name,moving,shadow,cadence in [('coarse_moving',True,.8,1),('no_hand',False,.8,1),('shadow_confounded_no_hand',False,6,1),('very_coarse_moving',True,.8,.2)]:
  detections=0;dist_errors=[]
  for seed in SEEDS:
   t,y=rssi_forward(seed=seed,moving=moving,shadow_db=shadow,cadence_hz=cadence,link_distance=2);e=estimate_rssi(t,y);detections+=e['presence'];dist_errors.append(abs(e['calibrated_link_distance_m']-2));rssi_trials.append({'scenario':name,'seed':seed,'motion_truth':moving,'cadence_hz':cadence,'estimate':e})
  rssi[name]={'n':len(SEEDS),'motion_truth':moving,'cadence_hz':cadence,'detection_rate':detections/len(SEEDS),'detection_rate_wilson_95':wilson(detections,len(SEEDS)),'link_distance_mae_m':float(np.mean(dist_errors)),'distance_mae_bootstrap_95':interval(dist_errors),'target_range_observable':False}
 point=np.array([.5,.5,.2]);links1=[(np.array([0,0,0]),np.array([1,0,0]))];links3=links1+[(np.array([0,0,1]),np.array([0,1,1])),(np.array([-1,0,0]),np.array([-1,0,1]))]
 observability={'one_link':fisher_geometry(links1,point),'three_diverse_links':fisher_geometry(links3,point),'range_resolution_m_at_20MHz':C/(2*20e6),'speed_alias_abs_path_rate_mps_at_100Hz':C/base.carrier*base.sample_hz/2,'note':'Fisher full rank is necessary local differential evidence, not a proven global localization algorithm. Bandwidth-limited range resolution is ~7.5m; phase does not establish absolute range.'}
 fusion=[]
 for seed in SEEDS:
  # RF responds to room motion; IMU responds to phone motion. Neither gives hand intent.
  t,h,_,m=csi_forward(replace(base,velocity=(0,0,0),independent_phase_drift_hz=3),seed=seed);csi=estimate_csi(t,h,m,base)
  rt,ry=rssi_forward(seed=seed,moving=False,shadow_db=6);rss=estimate_rssi(rt,ry)
  fusion.append({'seed':seed,'hand_intent_truth':False,'csi_presence':csi['presence'],'rssi_presence':rss['presence'],'or_presence':fuse_presence([csi,rss]),'and_presence':bool(csi['presence'] and rss['presence']),'reason':'oscillator mismatch and correlated shadowing can both be false hand evidence'})
 hypotheses={
 'GM-RF-001_complex_delay_model':{'status':'supported_synthetic','test':'single-path analytical complex exponential parity'},
 'GM-RF-002_practical_paths':{'status':'documented_public_sources','test':'path A-H hardware/API/permission/cadence matrix in artifacts/rf-report.md; no physical validation'},
 'hypothesis_CSI_RSSI_equivalence':{'status':'rejected','test':'RSSI coarse motion detection differs from CSI and cannot measure Doppler'},
 'GM-RF-006_classical_statistical_comparison':{'status':'executed_synthetic','test':'classifiers.json; 56 entire environment sessions split train32/validation8/test16; no physical participants'},
 'hypothesis_scalar_localization':{'status':'rejected','test':'one-link Fisher rank1; iso-delay motion remains invisible'},
 'GM-RF-007_modality_comparison':{'status':'executed_synthetic','test':'fusion.json actual acoustic signal kernel + optical bearing proxy + RF; quality-gated alternative preserves bias/dropout/identity failures'},
 'hypothesis_unqualified_fusion_improves':{'status':'rejected','test':'OR/AND of confounded sensors have false positives','or_false_positive_rate':sum(x['or_presence'] for x in fusion)/len(fusion),'and_false_positive_rate':sum(x['and_presence'] for x in fusion)/len(fusion)},
 'GM-RF-005_hardware':{'status':'pending_hardware','physical_tested':False},
 }
 output={'schema_version':1,'provenance':'synthetic','physical_tested':False,'seeds':SEEDS,'runtime':{'python':sys.version.split()[0],'numpy':np.__version__,'platform':platform.system()},'csi':summaries,'rssi':rssi,'observability':observability,'hypotheses':hypotheses,'fusion_trials':fusion,'method':'40 independent fixed-seed synthetic trials/scenario; Wilson binomial intervals; 2000 bootstrap means; uncertainty is one Fourier bin, not calibrated probability'}
 path=ROOT/'results';path.mkdir(exist_ok=True)
 (path/'experiments.json').write_text(json.dumps(output,indent=2)+'\n');(path/'trials.json').write_text(json.dumps({'csi':trials,'rssi':rssi_trials},indent=2)+'\n')
 digest=hashlib.sha256((path/'experiments.json').read_bytes()).hexdigest();(path/'fingerprint.txt').write_text(digest+'  experiments.json\n')
 print(json.dumps({'csi':summaries,'rssi':rssi,'hypotheses':hypotheses},indent=2))
if __name__=='__main__':main()
