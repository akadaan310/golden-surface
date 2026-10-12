"""Physically motivated RF models; all generated data have synthetic provenance.

Complex CSI tracks electrical path delay. RSSI has a different log-distance model.
Inter-antenna products cancel *common* packet phase, not independent phase drift.
"""
from dataclasses import dataclass, field
import numpy as np
C=299792458.0
@dataclass
class RFConfig:
 tx: np.ndarray = field(default_factory=lambda:np.array([0.,0.,0.]))
 rx: np.ndarray = field(default_factory=lambda:np.array([1.,0.,0.]))
 position: tuple = (.5,.55,.15)
 velocity: tuple = (0.,.15,0.)
 amplitude: float = .55
 static_amplitude: float = 1.
 static_paths: tuple = (((1.,.9,.4),.25),)
 carrier: float = 5.2e9
 subcarrier_spacing: float = 312500
 subcarriers: int = 30
 antenna_count: int = 2
 antenna_spacing: float = C/5.2e9/2
 sample_hz: float = 100
 noise: float = .01
 cfo_hz: float = 22
 sfo_ppm: float = 8
 phase_noise: float = .02
 packet_loss: float = .03
 clock_drift_ppm: float = 15
 independent_phase_drift_hz: float = 0
 monostatic: bool = False
 iso_delay: bool = False
 extra_movers: tuple = ()
 motion_threshold: float = .012
 light_speed: float = C
 @property
 def frequencies(self): return self.carrier+(np.arange(self.subcarriers)-(self.subcarriers-1)/2)*self.subcarrier_spacing

def moving_positions(c,t):
 p=np.asarray(c.position)+t[:,None]*np.asarray(c.velocity)
 if c.iso_delay:
  # Circle about the TX/RX baseline: exact constant delay at the base antenna.
  p=np.tile(np.asarray(c.position),(len(t),1)); r=np.hypot(p[0,1],p[0,2]); angle=.4*t
  p[:,1]=r*np.cos(angle);p[:,2]=r*np.sin(angle)
 return p

def csi_forward(c=None,duration=4,seed=1):
 c=c or RFConfig();rng=np.random.default_rng(seed)
 if not (0<duration<=60 and 1<=c.antenna_count<=8 and 0<=c.packet_loss<=1): raise ValueError('bounded configuration required')
 t=np.arange(int(duration*c.sample_hz))/c.sample_hz
 h=np.zeros((len(t),c.antenna_count,c.subcarriers),complex)
 movers=[(moving_positions(c,t),c.amplitude)]
 movers += [(np.asarray(p)+t[:,None]*np.asarray(v),a) for p,v,a in c.extra_movers]
 for a in range(c.antenna_count):
  rx=np.asarray(c.rx)+np.array([a*c.antenna_spacing,0,0])
  direct=np.linalg.norm(np.asarray(c.tx)-rx)
  h[:,a,:]=c.static_amplitude*np.exp(-2j*np.pi*c.frequencies*direct/C)
  for pos,amp in c.static_paths:
   delay=(np.linalg.norm(np.asarray(pos)-c.tx)+np.linalg.norm(np.asarray(pos)-rx))/C
   h[:,a,:] += amp*np.exp(-2j*np.pi*c.frequencies*delay)
  for p,amp in movers:
   length=np.linalg.norm(p-c.tx,axis=1)+np.linalg.norm(p-rx,axis=1)
   h[:,a,:] += amp*np.exp(-2j*np.pi*length[:,None]*c.frequencies[None,:]/C)
 common=2*np.pi*c.cfo_hz*t+rng.normal(0,c.phase_noise,len(t))
 slope=2*np.pi*t[:,None]*(c.frequencies-c.carrier)[None,:]*c.sfo_ppm*1e-6
 for a in range(c.antenna_count):
  h[:,a,:] *= np.exp(1j*(common[:,None]+slope+2*np.pi*c.independent_phase_drift_hz*a*t[:,None]))
 h+=c.noise*(rng.normal(size=h.shape)+1j*rng.normal(size=h.shape))
 valid=rng.random(len(t))>=c.packet_loss
 p=moving_positions(c,t);u1=(p-c.tx)/np.linalg.norm(p-c.tx,axis=1)[:,None];u2=(p-c.rx)/np.linalg.norm(p-c.rx,axis=1)[:,None]
 path_rate=np.sum((u1+u2)*np.asarray(c.velocity),axis=1)
 if c.iso_delay:path_rate=np.zeros_like(t)
 timestamps=t*(1+c.clock_drift_ppm*1e-6)
 return timestamps,h,path_rate,valid

def estimate_csi(t,h,valid,c=None):
 c=c or RFConfig();tv=np.asarray(t)[valid];hv=np.asarray(h)[valid]
 base={'modality':'wifi-csi','presence':False,'motion_score':0.,'confidence':0.,'quality':'unobservable','source':'synthetic','coordinate_frame':'measurement-space','sample_count':len(tv),'warnings':['unsigned bistatic path-rate; no localization']}
 if len(tv)<20 or h.shape[1]<2:return base
 x,y=hv[:,0,c.subcarriers//2],hv[:,1,c.subcarriers//2]
 z=x*np.conj(y)/np.maximum(1e-9,np.abs(x)*np.abs(y))
 var=float(np.mean(np.abs(z-z.mean())**2));presence=var>c.motion_threshold
 duration=float(tv[-1]-tv[0]);loss=1-len(tv)/len(t)
 uniform=np.linspace(tv[0],tv[-1],len(t));zi=np.interp(uniform,tv,z.real)+1j*np.interp(uniform,tv,z.imag)
 window=np.hanning(len(zi));spec=np.abs(np.fft.fft((zi-zi.mean())*window))**2
 hz=np.fft.fftfreq(len(zi),d=uniform[1]-uniform[0]);spec[0]=0
 peak=int(np.argmax(spec));speed=abs(hz[peak])*C/c.carrier
 base.update(presence=bool(presence),motion_score=float(np.clip(var/(5*c.motion_threshold),0,1)),variance=var,confidence=float(np.clip((spec[peak]/max(1e-10,spec.sum()))*4*(1-loss),0,1)) if presence else float(np.clip(1-var/(5*c.motion_threshold),0,1)),quality='degraded' if loss>.25 else 'good')
 if presence:
  base.update(path_rate_mps=float(speed),doppler_hz=float(abs(hz[peak])),uncertainty_mps=float(C/c.carrier/duration),ambiguity='unsigned-bistatic')
  if c.monostatic:
   if not np.allclose(c.tx,c.rx):raise ValueError('monostatic requires colocated TX/RX')
   base.update(radial_velocity_mps=float(speed/2),ambiguity='unsigned-monostatic')
 return base

def rssi_forward(duration=30,cadence_hz=1,seed=1,moving=True,shadow_db=.8,link_distance=1,reference_dbm=-40,path_loss_exponent=2.4):
 """RSSI at coarse cadence. Correlated shadowing can mimic motion without a hand."""
 rng=np.random.default_rng(seed);t=np.arange(int(duration*cadence_hz))/cadence_hz
 shadow=np.empty(len(t));shadow[0]=rng.normal(0,shadow_db)
 for i in range(1,len(t)):shadow[i]=.8*shadow[i-1]+rng.normal(0,shadow_db*.6)
 y=reference_dbm-10*path_loss_exponent*np.log10(link_distance)+shadow+rng.normal(0,.25,len(t))
 if moving:y+=1.8*np.sin(2*np.pi*.6*t)
 return t,y

def estimate_rssi(t,y,reference_dbm=-40,path_loss_exponent=2.4):
 y=np.asarray(y);sd=float(np.std(y));presence=len(y)>=5 and sd>3
 return {'modality':'wifi-rssi','presence':bool(presence),'motion_score':float(np.clip(sd/6,0,1)),'confidence':float(np.clip(abs(sd-3)/6,0,1)) if len(y)>=5 else 0.,'calibrated_link_distance_m':float(10**((reference_dbm-np.mean(y))/(10*path_loss_exponent))),'std_db':sd,'source':'synthetic','coordinate_frame':'measurement-space','quality':'degraded','warnings':['TX-RX calibrated link distance only; not moving reflector range','shadowing/orientation confound motion; RSSI does not measure Doppler']}

def fisher_geometry(links,point,sigma_range=.03):
 p=np.asarray(point);jac=[]
 for tx,rx in links:
  a=p-tx;b=p-rx
  if min(np.linalg.norm(a),np.linalg.norm(b))<1e-9:raise ValueError('target coincides with transceiver')
  jac.append(a/np.linalg.norm(a)+b/np.linalg.norm(b))
 j=np.array(jac);f=j.T@j/sigma_range**2;sv=np.linalg.svd(j,compute_uv=False);rank=int(np.linalg.matrix_rank(j,tol=1e-8))
 return {'jacobian':j.tolist(),'fisher':f.tolist(),'singular_values':sv.tolist(),'rank':rank,'localizable':rank==3,'condition':float(np.linalg.cond(f)) if rank==3 else None,'caveat':'local differential rank only; global mirrored solutions and calibration may remain'}

def fuse_presence(evidence):
 """Naive OR baseline deliberately included to expose correlated false positives."""
 return any(e['presence'] for e in evidence)
