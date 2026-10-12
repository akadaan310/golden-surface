/** RF laboratory kernel. Synthetic evidence only; a bistatic scalar is never xyz. */
export type Vec3 = [number,number,number];
export interface Complex {re:number;im:number}
export interface Reflector {position:Vec3;velocity:Vec3;amplitude:number}
export interface RfConfig {
 tx:Vec3;rx:Vec3;reflectors:Reflector[];staticReflectors:Reflector[];
 carrierHz:number;subcarrierSpacingHz:number;subcarriers:number;antennas:number;
 antennaSpacingM:number;cadenceHz:number;rssiCadenceHz:number;noiseStd:number;
 staticAmplitude:number;cfoHz:number;sfoPpm:number;phaseNoiseRad:number;
 packetLoss:number;clockDriftPpm:number;shadowingDb:number;monostatic:boolean;
 rssiReferenceDbm:number;pathLossExponent:number;motionThreshold:number;
}
export interface RfFrame {timestamp:number;timeSeconds:number;csi:Complex[][];
 rssiDbm:number;rssiUpdated:boolean;lost:boolean;source:'synthetic'}
export interface RssiSample {timestamp:number;rssiDbm:number;source:'synthetic'|'recorded'|'live'}
export interface CsiDiagnostics {spectrumHz:number[];spectrumPower:number[];trace:{timestamp:number;re:number;im:number}[];correctedPhaseRad:number[];variance:number}
export interface RfEstimate {modality:'wifi-csi'|'wifi-rssi';presence:boolean;motionScore:number;
 confidence:number;quality:'good'|'degraded'|'unobservable';pathRateMps?:number;
 radialVelocityMps?:number;dopplerHz?:number;uncertaintyMps?:number;
 calibratedLinkDistanceM?:number;warnings:string[];provenance:'synthetic'|'recorded'|'live';
 sampleCount:number;diagnostics?:CsiDiagnostics;coordinateFrame:'measurement-space';ambiguity?:'unsigned-bistatic'|'unsigned-monostatic'}
const C=299792458, TAU=2*Math.PI;
const norm=(v:Vec3)=>Math.hypot(...v);
const sub=(a:Vec3,b:Vec3):Vec3=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const mean=(a:number[])=>a.reduce((s,v)=>s+v,0)/Math.max(1,a.length);
const clamp=(x:number)=>Math.max(0,Math.min(1,x));
function random(seed:number) {let s=seed>>>0;return ()=>{s=(Math.imul(1664525,s)+1013904223)>>>0;return (s+.5)/4294967296;};}
function gaussian(r:()=>number) {return Math.sqrt(-2*Math.log(r()))*Math.cos(TAU*r());}
function phase(a:number,p:number):Complex {return {re:a*Math.cos(p),im:a*Math.sin(p)};}
function validate(c:RfConfig) {
 const vector=(v:Vec3)=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite);
 if(!vector(c.tx)||!vector(c.rx)||!Array.isArray(c.reflectors)||!Array.isArray(c.staticReflectors)||c.reflectors.length+c.staticReflectors.length>64||
  [...c.reflectors,...c.staticReflectors].some(r=>!vector(r.position)||!vector(r.velocity)||!Number.isFinite(r.amplitude))||
  Object.values(c).some(v=>typeof v==='number'&&!Number.isFinite(v)))throw new Error('RF geometry and nuisance parameters must be finite');
 if(!Number.isInteger(c.antennas)||!Number.isInteger(c.subcarriers)||c.motionThreshold<=0||c.phaseNoiseRad<0||c.shadowingDb<0||c.antennaSpacingM<0||c.clockDriftPpm<=-1e6)throw new Error('Invalid RF sampling or nuisance configuration');
 if(!(c.carrierHz>0&&c.cadenceHz>0&&c.rssiCadenceHz>0&&c.subcarriers>=1&&c.subcarriers<=128&&c.antennas>=1&&c.antennas<=8&&c.pathLossExponent>0&&c.noiseStd>=0&&c.packetLoss>=0&&c.packetLoss<=1))throw new Error('Invalid/beyond-budget RF configuration');
 if(c.monostatic&&norm(sub(c.tx,c.rx))>1e-9)throw new Error('Monostatic velocity requires colocated TX/RX');
}
export function defaultRfConfig():RfConfig {return {
 tx:[0,0,0],rx:[1,0,0],reflectors:[{position:[.5,.55,.15],velocity:[0,.15,0],amplitude:.55}],
 staticReflectors:[{position:[1,.9,.4],velocity:[0,0,0],amplitude:.25}],
 carrierHz:5.2e9,subcarrierSpacingHz:312500,subcarriers:30,antennas:2,
 antennaSpacingM:C/5.2e9/2,cadenceHz:100,rssiCadenceHz:1,noiseStd:.01,
 staticAmplitude:1,cfoHz:22,sfoPpm:8,phaseNoiseRad:.02,packetLoss:.03,
 clockDriftPpm:15,shadowingDb:.8,monostatic:false,rssiReferenceDbm:-40,pathLossExponent:2.4,motionThreshold:.012};}
/** H_k = sum_l a_l exp(-j 2pi f_k tau_l) + n; nuisance is per packet. */
export function generateCsiFrame(timeSeconds:number, config:RfConfig=defaultRfConfig(), seed=1):RfFrame {
 validate(config);if(!Number.isFinite(timeSeconds)||timeSeconds<0)throw new Error('Invalid time');
 const index=Math.round(timeSeconds*config.cadenceHz),r=random((seed+Math.imul(index+1,2654435761))>>>0);
 const lost=r()<config.packetLoss, common=TAU*config.cfoHz*timeSeconds+config.phaseNoiseRad*gaussian(r);
 const csi:Complex[][]=[];
 for(let a=0;a<config.antennas;a++) {
  const rx:Vec3=[config.rx[0]+a*config.antennaSpacingM,config.rx[1],config.rx[2]];
  const row:Complex[]=[];
  for(let k=0;k<config.subcarriers;k++) {
   const offset=(k-(config.subcarriers-1)/2)*config.subcarrierSpacingHz,f=config.carrierHz+offset;
   let z=phase(config.staticAmplitude,-TAU*f*norm(sub(config.tx,rx))/C);
   for(const reflector of [...config.staticReflectors,...config.reflectors]) {
    const p:Vec3=reflector.position.map((v,i)=>v+reflector.velocity[i]*timeSeconds) as Vec3;
    const path=norm(sub(p,config.tx))+norm(sub(p,rx));
    const q=phase(reflector.amplitude,-TAU*f*path/C);z={re:z.re+q.re,im:z.im+q.im};
   }
   const n=common+TAU*offset*config.sfoPpm*1e-6*timeSeconds,q=phase(1,n);
   row.push({re:z.re*q.re-z.im*q.im+config.noiseStd*gaussian(r),im:z.re*q.im+z.im*q.re+config.noiseStd*gaussian(r)});
  } csi.push(row);
 }
 const rt=Math.floor(timeSeconds*config.rssiCadenceHz)/config.rssiCadenceHz;
 const rr=random(seed+Math.round(rt*config.rssiCadenceHz)*7919);
 const link=norm(sub(config.tx,config.rx));
 const motion=config.reflectors.reduce((s,p)=>s+Math.min(1,norm(p.velocity)*5)*1.8*Math.sin(TAU*.6*rt),0);
 const shadow=config.shadowingDb*(.8*Math.sin(.7*rt)+.6*gaussian(rr));
 const rssiDbm=config.rssiReferenceDbm-10*config.pathLossExponent*Math.log10(Math.max(.1,link))+motion+shadow;
 return {timestamp:1000*timeSeconds*(1+config.clockDriftPpm*1e-6),timeSeconds,csi,rssiDbm,rssiUpdated:index===Math.round(rt*config.cadenceHz),lost,source:'synthetic'};
}
export function simulateRf(config:RfConfig=defaultRfConfig(), options:{durationS?:number;seed?:number}={}):RfFrame[] {
 validate(config);const duration=options.durationS??4;
 if(!(duration>0&&duration<=60&&duration*config.cadenceHz<=12000))throw new Error('RF simulation exceeds bounded window');
 return Array.from({length:Math.floor(duration*config.cadenceHz)},(_,i)=>generateCsiFrame(i/config.cadenceHz,config,options.seed??1));
}
export function extractRssiSamples(frames:RfFrame[]):RssiSample[] {return frames.filter(f=>f.rssiUpdated&&!f.lost).map(f=>({timestamp:f.timestamp,rssiDbm:f.rssiDbm,source:f.source}));}
/** Inter-antenna conjugate product cancels common CFO, SFO and phase noise. */
export function analyzeCsi(frames:RfFrame[], config:RfConfig=defaultRfConfig()):RfEstimate {
 validate(config);const fs=frames.filter(f=>!f.lost),warnings=['CSI Doppler is path-length rate; one link does not localize a reflector.','Cross-product sidebands do not establish direction; speed is unsigned.'];
 const base:RfEstimate={modality:'wifi-csi',presence:false,motionScore:0,confidence:0,quality:'unobservable',warnings,provenance:frames[0]?.source??'synthetic',sampleCount:fs.length,coordinateFrame:'measurement-space'};
 if(fs.length<20||config.antennas<2||!fs.every(f=>f.csi.length>=2)){warnings.push('Two coherent receive antennas and at least 20 packets required by this estimator.');return base;}
 const z=fs.map(f=>{const x=f.csi[0][Math.floor(config.subcarriers/2)],y=f.csi[1][Math.floor(config.subcarriers/2)];const d=Math.max(1e-9,Math.hypot(x.re,x.im)*Math.hypot(y.re,y.im));return {re:(x.re*y.re+x.im*y.im)/d,im:(x.im*y.re-x.re*y.im)/d};});
 const mr=mean(z.map(v=>v.re)),mi=mean(z.map(v=>v.im));
 const variance=mean(z.map(v=>(v.re-mr)**2+(v.im-mi)**2));
 const motionScore=clamp(variance/(config.motionThreshold*5));const presence=variance>config.motionThreshold;
 const duration=(fs.at(-1)!.timestamp-fs[0].timestamp)/1000;
 if(duration<=0)return base;
 const samples=z.length, bins=Math.min(200,Math.floor(config.cadenceHz*duration/2));
 let peak=0,peakHz=0,total=0;const spectrum:{hz:number;power:number}[]=[];
 for(let b=1;b<=bins;b++)for(const sign of [-1,1]){
  const hz=sign*b/duration;let re=0,im=0;
  for(let i=0;i<samples;i++){const t=(fs[i].timestamp-fs[0].timestamp)/1000,p=-TAU*hz*t,w=.5-.5*Math.cos(TAU*i/(samples-1)),zr=z[i].re-mr,zi=z[i].im-mi;re+=w*(zr*Math.cos(p)-zi*Math.sin(p));im+=w*(zr*Math.sin(p)+zi*Math.cos(p));}
  const power=re*re+im*im;spectrum.push({hz,power});total+=power;if(power>peak){peak=power;peakHz=hz;}
 }
 const loss=1-fs.length/Math.max(1,frames.length),quality=loss>.25?'degraded':'good';
 if(loss>.25)warnings.push('High packet loss; Doppler peak and confidence may be biased.');
 const pathRateMps=Math.abs(peakHz)*C/config.carrierHz, confidence=presence?clamp((peak/Math.max(peak,total))*4*(1-loss)):clamp(1-motionScore);
 spectrum.sort((a,b)=>a.hz-b.hz);
 const diagnostics:CsiDiagnostics={spectrumHz:spectrum.map(v=>v.hz),spectrumPower:spectrum.map(v=>v.power),trace:z.map((v,i)=>({...v,timestamp:fs[i].timestamp})),correctedPhaseRad:z.map(v=>Math.atan2(v.im,v.re)),variance};
 const estimate:RfEstimate={...base,presence,motionScore,confidence,quality,diagnostics};
 if(presence){estimate.pathRateMps=pathRateMps;estimate.dopplerHz=Math.abs(peakHz);estimate.uncertaintyMps=C/config.carrierHz/duration;estimate.ambiguity=config.monostatic?'unsigned-monostatic':'unsigned-bistatic';if(config.monostatic)estimate.radialVelocityMps=pathRateMps/2;}
 return estimate;
}
/** Diagnostics reuse the exact estimator calculation; inter-antenna phase is not target phase. */
export function csiDiagnostics(frames:RfFrame[],config:RfConfig=defaultRfConfig()):CsiDiagnostics {return analyzeCsi(frames,config).diagnostics??{spectrumHz:[],spectrumPower:[],trace:[],correctedPhaseRad:[],variance:0};}
/** Separate log-distance inverse. RSSI distance is calibrated TX-RX link distance, not target range. */
export function analyzeRssi(samples:RssiSample[], config:RfConfig=defaultRfConfig()):RfEstimate {
 validate(config);const values=samples.map(s=>s.rssiDbm).filter(Number.isFinite),m=mean(values),sd=Math.sqrt(mean(values.map(x=>(x-m)**2))),presence=values.length>=5&&sd>3;
 return {modality:'wifi-rssi',presence,motionScore:clamp(sd/6),confidence:values.length<5?0:clamp(Math.abs(sd-3)/6),quality:values.length<5?'unobservable':'degraded',calibratedLinkDistanceM:10**((config.rssiReferenceDbm-m)/(10*config.pathLossExponent)),warnings:['RSSI changes can be shadowing, orientation or unrelated traffic.','Coarse RSSI cannot resolve hand Doppler or moving-reflector range.','Link-distance inverse requires a known reference power and path-loss exponent.'],provenance:samples[0]?.source??'synthetic',sampleCount:values.length,coordinateFrame:'measurement-space'};
}
/** Compatible with ISI Measurement; RF variation does not assert deliberate hand intent. */
export function rfMeasurement(estimate:RfEstimate, options:{timestamp:number;deviceId?:string;intent?:boolean}):{
 timestamp:number;deviceId:string;source:'synthetic'|'recorded'|'live';modality:string;
 coordinateFrame:string;confidence:number;intent:boolean;relative:{kind:string;value:number;unit:string};
 metadata:Record<string,unknown>;
} {
 if(!Number.isFinite(options.timestamp))throw new Error('RF event timestamp must be finite');
 return {timestamp:options.timestamp,deviceId:options.deviceId??'rf-lab',source:estimate.provenance,
  modality:estimate.modality,coordinateFrame:'measurement-space',confidence:estimate.confidence,
  intent:options.intent??false,relative:{kind:'rf-motion-score',value:estimate.motionScore,unit:'unitless'},
  metadata:{evidence:{acquisition:estimate.provenance,physicalTested:false},presence:estimate.presence,
   quality:estimate.quality,...(estimate.pathRateMps===undefined?{}:{pathRateMps:estimate.pathRateMps}),
   ...(estimate.radialVelocityMps===undefined?{}:{radialVelocityMps:estimate.radialVelocityMps}),
   ...(estimate.ambiguity===undefined?{}:{ambiguity:estimate.ambiguity}),confidenceMeaning:'uncalibrated signal quality heuristic',
   semanticMeaning:'RF channel variation; hand identity and deliberate intent not established',warnings:estimate.warnings}};
}
