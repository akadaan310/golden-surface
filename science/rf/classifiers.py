"""GM-RF-006: signal-processing baseline vs small regularized logistic classifier.
Synthetic environment/session-separated split; no participant generalization claim.
"""
import numpy as np,json,time
from pathlib import Path
from dataclasses import replace
from kernel import RFConfig,csi_forward,estimate_csi,rssi_forward,estimate_rssi
from experiments import wilson

def session_split(groups):
 groups=np.asarray(groups);return groups<32,(groups>=32)&(groups<40),groups>=40

def fit_logistic(x,y,iterations=1000,penalty=.02):
 mu=x.mean(axis=0);sd=np.maximum(x.std(axis=0),1e-6);z=np.column_stack([np.ones(len(x)),(x-mu)/sd]);w=np.zeros(z.shape[1])
 for _ in range(iterations):
  p=1/(1+np.exp(-np.clip(z@w,-30,30)));gradient=z.T@(p-y)/len(y)+penalty*np.r_[0,w[1:]];w-=.2*gradient
 return {'mean':mu,'std':sd,'weights':w}

def predict_logistic(model,x):
 z=np.column_stack([np.ones(len(x)),(x-model['mean'])/model['std']]);return 1/(1+np.exp(-np.clip(z@model['weights'],-30,30)))

def features(t,h,valid,rssi):
 hv=h[valid];x,y=hv[:,0,15],hv[:,1,15];z=x*np.conj(y)/np.maximum(1e-9,np.abs(x*y));s=np.abs(np.fft.fft((z-z.mean())*np.hanning(len(z))))**2;s[0]=0;s/=max(1e-9,s.sum());nz=s[s>1e-12]
 return np.array([np.log10(np.mean(abs(z-z.mean())**2)+1e-8),float(s.max()),float(-np.sum(nz*np.log(nz))/np.log(len(s))),float(np.std(rssi))])

def metrics(y,p,threshold=.5):
 pred=p>=threshold;n=len(y);neg=y==0;pos=y==1;correct=int(np.sum(pred==y));fp=int(np.sum(pred[neg]));tp=int(np.sum(pred[pos]));brier=float(np.mean((p-y)**2));bins=[]
 for a,b in zip(np.arange(0,1,.2),np.arange(.2,1.01,.2)):
  ix=(p>=a)&(p<=b if b==1 else p<b)
  if ix.any():bins.append({'bin':[float(a),float(b)],'n':int(ix.sum()),'mean_predicted_probability':float(p[ix].mean()),'fraction_motion':float(y[ix].mean())})
 return {'n':n,'accuracy':correct/n,'accuracy_wilson_95':wilson(correct,n),'false_activation_rate':fp/max(1,int(neg.sum())),'false_activation_wilson_95':wilson(fp,int(neg.sum())),'recall':tp/max(1,int(pos.sum())),'brier_score':brier,'calibration_bins':bins}

def session_bootstrap(y,p,groups,threshold=.5):
 sessions=np.unique(groups);scores=[]
 for g in sessions:
  ix=groups==g;pred=p[ix]>=threshold;truth=y[ix];scores.append([np.mean(pred==truth),np.mean(pred[truth==0]),np.mean(pred[truth==1])])
 a=np.array(scores);rng=np.random.default_rng(8027);boot=a[rng.integers(0,len(a),(2000,len(a)))].mean(axis=1)
 return {key:[float(np.quantile(boot[:,i],.025)),float(np.quantile(boot[:,i],.975))] for i,key in enumerate(['accuracy','false_activation_rate','recall'])}

def main():
 features_all=[];labels=[];groups=[];scenarios=[];fixed=[];raw=[];lat=[]
 cases=['static','nominal','weak','iso_delay','independent_phase_no_hand','noise_static','loss_motion','shadow_no_hand']
 for session in range(56):
  rng=np.random.default_rng(5000+session);base=RFConfig(position=(float(rng.uniform(.35,.65)),float(rng.uniform(.45,.7)),.15),noise=float(rng.uniform(.008,.03)),clock_drift_ppm=float(rng.uniform(-100,100)),packet_loss=float(rng.uniform(0,.1)))
  for case in cases:
   truth=case in ('nominal','weak','iso_delay','loss_motion');c=base
   if case in ('static','noise_static','shadow_no_hand'):c=replace(c,velocity=(0,0,0))
   if case=='weak':c=replace(c,amplitude=.08)
   if case=='iso_delay':c=replace(c,iso_delay=True)
   if case=='independent_phase_no_hand':c=replace(c,velocity=(0,0,0),independent_phase_drift_hz=float(rng.uniform(2,5)))
   if case=='noise_static':c=replace(c,noise=.2)
   if case=='loss_motion':c=replace(c,packet_loss=.5)
   t,h,v,m=csi_forward(c,seed=10000+session*8+cases.index(case));rt,ry=rssi_forward(seed=20000+session*8+cases.index(case),moving=truth,shadow_db=6 if case=='shadow_no_hand' else .8)
   start=time.perf_counter();f=features(t,h,m,ry);e=estimate_csi(t,h,m,c);lat.append((time.perf_counter()-start)*1000)
   features_all.append(f);labels.append(int(truth));groups.append(session);scenarios.append(case);fixed.append(int(e['presence']));raw.append(f[0])
 x=np.array(features_all);y=np.array(labels);groups=np.array(groups);train,val,test=session_split(groups)
 # Tune a classical variance threshold on validation sessions only.
 candidates=np.linspace(-5,0,100);best=min(candidates,key=lambda b:np.mean((x[val,0]>=b)!=y[val]));classical=(x[test,0]>=best).astype(float)
 model=fit_logistic(x[train],y[train]);start=time.perf_counter();p=predict_logistic(model,x[test]);latency=(time.perf_counter()-start)*1000/len(p)
 # Validation-only probability threshold selection; preserve test performance regardless.
 pv=predict_logistic(model,x[val]);threshold=min(np.linspace(.2,.8,61),key=lambda b:np.mean((pv>=b)!=y[val]))
 model_csi=fit_logistic(x[train,:3],y[train]);pcsi=predict_logistic(model_csi,x[test,:3]);pvcsi=predict_logistic(model_csi,x[val,:3]);threshold_csi=min(np.linspace(.2,.8,61),key=lambda b:np.mean((pvcsi>=b)!=y[val]))
 bycase={}
 sc=np.array(scenarios)[test]
 for case in cases:
  ix=sc==case;bycase[case]={'motion_truth':bool(y[test][ix][0]),'classical_detection':float(classical[ix].mean()),'logistic_detection':float(np.mean(p[ix]>=threshold)),'mean_logistic_probability':float(p[ix].mean())}
 output={'requirement':'GM-RF-006','provenance':'synthetic','physical_tested':False,'split':{'train_sessions':list(range(32)),'validation_sessions':list(range(32,40)),'test_sessions':list(range(40,56)),'windows_per_session':8,'participant_count':0,'leakage_control':'entire generated environment/session held out; no physical participants, no transfer claim'},'feature_names':['log10_interantenna_variance','peak_spectral_fraction','normalized_spectral_entropy','coarse_RSSI_std_db'],'classical_variance_threshold':float(10**best),'classical':metrics(y[test],classical),'fixed_physics_threshold':metrics(y[test],np.asarray(fixed)[test].astype(float)),'regularized_logistic':metrics(y[test],p,float(threshold)),'regularized_logistic_csi_only':metrics(y[test],pcsi,float(threshold_csi)),'probability_threshold_validation':float(threshold),'by_scenario':bycase,'latency':{'window_duration_seconds':4,'feature_plus_CSI_estimator_median_ms':float(np.median(lat)),'logistic_per_window_ms':latency,'note':'single container runtime; not native phone latency'},'model':{k:v.tolist() for k,v in model.items()},'limitation':'simulator features are not human gesture labels; identical nuisance/motion signals remain nonidentifiable. No deep network justified by 256 synthetic training windows.'}
 for key,prob,th in [('classical',classical,.5),('fixed_physics_threshold',np.asarray(fixed)[test],.5),('regularized_logistic',p,float(threshold)),('regularized_logistic_csi_only',pcsi,float(threshold_csi))]:output[key]['clustered_session_bootstrap_95']=session_bootstrap(y[test],prob,groups[test],th)
 output['interval_note']='Wilson intervals describe window counts with iid approximation; session-bootstrap intervals preserve within-session dependence and are preferred.'
 Path(__file__).with_name('results').joinpath('classifiers.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
if __name__=='__main__':main()
