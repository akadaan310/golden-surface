"""GM-RF-007: actual acoustic signal kernel + synthetic optical bearing + RF CSI.

Optical is a calibrated geometric proxy, not image detection. RF is unsigned path
rate and cannot create XYZ. Fused position uses optical bearing + acoustic range.
"""
from pathlib import Path
import sys,json,time
import numpy as np
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from science.golden_motion.model import AcousticConfig,simulate_echo,estimate_delay
from science.golden_motion.experiments import synthetic_optical
from kernel import RFConfig,csi_forward,estimate_csi,fisher_geometry
from experiments import wilson,interval

def optical_proxy(p,rng,available=True,hand_present=True):
 if not available or not hand_present:return None
 # Camera extrinsic identity and pinhole focal length.7 are explicit assumptions.
 return np.array(synthetic_optical(p,seed=int(rng.integers(0,2**31)))['bearing'])

def decode_position(bearing,scalar_range):
 return bearing*scalar_range

def main():
 records=[];metrics={};times=np.linspace(0,3.8,12);basep=np.array([.08,.12,.35]);velocity=np.array([.02,0,.05])
 cases=['nominal','no_hand_rf_drift','optical_dropout','acoustic_clock_bias','acoustic_multipath','weak_rf_motion','unrelated_moving_object']
 for case in cases:
  hand=case not in ('no_hand_rf_drift','unrelated_moving_object');physical_reflector=case!='no_hand_rf_drift';count=0;rf_count=0;ac_count=0;op_count=0;or_count=0;errors=[];rf_added=0;rejected_rf=0
  for seed in range(101,141):
   rng=np.random.default_rng(seed);c=RFConfig(position=tuple(basep),velocity=tuple(velocity),tx=np.array([0.,0.,0.]),rx=np.array([1.,0.,0.]))
   if not physical_reflector:c=replace(c,velocity=(0,0,0),independent_phase_drift_hz=3)
   if case=='weak_rf_motion':c=replace(c,amplitude=.08)
   rt,rh,rate,valid=csi_forward(c,duration=4,seed=seed);re=estimate_csi(rt,rh,valid,c);rf_count+=re['presence']
   acoustic_valid=[];optical_valid=[];fused=[];truth=[];scalars=[]
   cfg=AcousticConfig(clock_offset_s=.001 if case=='acoustic_clock_bias' else 0)
   for i,t in enumerate(times):
    p=basep+velocity*t;sig=simulate_echo(p,velocity,cfg,seed=seed*100+i,hand_present=physical_reflector,reflections=((.20,2.),) if case=='acoustic_multipath' else ())
    ac=estimate_delay(sig,cfg);op=optical_proxy(p,rng,available=case!='optical_dropout',hand_present=physical_reflector)
    acoustic_valid.append(ac['valid']);optical_valid.append(op is not None);truth.append(p)
    if ac['valid'] and op is not None:fused.append(decode_position(op,ac['range_m']));scalars.append(ac['range_m'])
   acp=bool(np.mean(acoustic_valid)>.5);opp=bool(np.mean(optical_valid)>.5);fp=bool(acp and opp);count+=fp;ac_count+=acp;op_count+=opp;or_count+=bool(acp or opp or re['presence'])
   err=None;consistent=None
   if fused:
    f=np.asarray(fused);tr=np.asarray(truth);err=float(np.mean(np.linalg.norm(f-tr,axis=1)));errors.append(err)
    # A corroboration gate predicts RF path rate from estimated positions, never truth.
    path=np.linalg.norm(f-c.tx,axis=1)+np.linalg.norm(f-c.rx,axis=1)
    predicted=abs(float((path[-1]-path[0])/(times[-1]-times[0])))
    if re['presence']:
     consistent=bool(abs(re['path_rate_mps']-predicted)<=max(.05,2*re['uncertainty_mps']));rf_added+=consistent;rejected_rf+=not consistent
   records.append({'scenario':case,'seed':seed,'hand_presence_truth':hand,'semantic_confound':case=='unrelated_moving_object','RF':re,'acoustic_presence':acp,'optical_proxy_presence':opp,'fused_presence':fp,'naive_OR_presence':bool(acp or opp or re['presence']),'fused_position_MAE_m':err,'rf_consistent_with_acoustic_optical':consistent,'fused_position_source':'calibrated optical bearing + acoustic scalar; no RF xyz'})
  n=40;metrics[case]={'hand_presence_truth':hand,'n':n,'rf_only_activation':rf_count/n,'acoustic_only_activation':ac_count/n,'optical_proxy_only_activation':op_count/n,'naive_OR_activation':or_count/n,'quality_gated_acoustic_optical_activation':count/n,'quality_gated_activation_wilson_95':wilson(count,n),'fused_position_MAE_m':float(np.mean(errors)) if errors else None,'fused_MAE_bootstrap_95':interval(errors),'rf_corroborated_fraction':rf_added/n,'rf_rejected_fraction':rejected_rf/n}
 p=basep;u=p/np.linalg.norm(p);g=np.array(fisher_geometry([(np.array([0.,0.,0.]),np.array([1.,0.,0.]))],p)['jacobian'][0]);velocity_rank=int(np.linalg.matrix_rank(np.vstack([u,g])))
 result={'requirement':'GM-RF-007','provenance':'synthetic','physical_tested':False,'common_truth':{'position0_m':basep.tolist(),'velocity_mps':velocity.tolist(),'duration_seconds':4},'assumptions':['acoustic speaker/mic and camera origin colocated, camera extrinsic identity and focal.7 known','optical calibrated pinhole bearing proxy; no camera images or ML detections','RF reflection coefficient fixed; no physical phone/ESP measurements'],'scenarios':metrics,'velocity_information':{'acoustic_radial_rank':1,'acoustic_plus_signed_RF_gradient_rank':velocity_rank,'actual_RF_sign':'unknown','full_velocity_observable':False,'note':'different geometry can add one scalar direction only if signed RF rate becomes identifiable; current unsigned estimate cannot establish unique velocity'},'operational_alternative':'require valid optical hand evidence and valid acoustic scalar before spatial interaction; RF only adds motion corroboration when predicted path-rate agrees. Preserve uncertainty when optical drops out and propagate acoustic bias. No automatic intent from RF presence.','trials':records}
 Path(__file__).with_name('results').joinpath('fusion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(metrics,indent=2))
if __name__=='__main__':main()
