/** Browser-local forward models. Synthetic scalar observations never become xyz. */
export type Vec3 = [number, number, number];
export type Modality = 'acoustic' | 'optical' | 'magnetic';
export interface LabSettings { noise:number; multipath:number; drift:number; dropout:number; handPresent:boolean; seed:number; }
export const defaults:LabSettings = {noise:.08,multipath:.15,drift:0,dropout:0,handPresent:true,seed:23};
export interface SignalResult { source:'synthetic'; coordinateFrame:'measurement-space'; modality:string; samples:number[]; reference:number[]; correlation:number[]; estimate:number|null; truth:number; confidence:number; uncertainty:number; error:number|null; lost:boolean; unit:string; observable:string; }
export function random(seed:number) {let n=seed>>>0; return ()=>{n=(Math.imul(n,1664525)+1013904223)>>>0;return (n+.5)/4294967296;};}
export function acousticExperiment(s:LabSettings,elapsed:number,point:Vec3):SignalResult {
 const fs=48000,c=343, truth=Math.hypot(...point),lag=Math.round(2*truth/c*fs),rand=random(s.seed+Math.floor(elapsed/80));
 const reference=Array.from({length:96},(_,i)=>Math.sin(2*Math.PI*(5000*i/fs+5000*(i/fs)**2/(2*(96/fs))))*(.5-.5*Math.cos(2*Math.PI*i/95)));
 const packetLost=rand()<s.dropout, drift=Math.round(s.drift*elapsed/12000),samples=Array.from({length:512},()=>s.noise*(rand()*2-1));
 for(let i=0;i<reference.length;i++){samples[i]+=reference[i]*.15;if(s.handPresent&&!packetLost){if(i+lag+drift>=0&&i+lag+drift<512)samples[i+lag+drift]+=reference[i];if(i+lag+32<512)samples[i+lag+32]+=reference[i]*s.multipath*1.5;}}
 const correlation=Array.from({length:210},(_,d)=>reference.reduce((v,x,i)=>v+x*samples[i+d],0));
 let peak=14;for(let d=15;d<210;d++)if(correlation[d]>correlation[peak])peak=d;
 const energy=reference.reduce((a,x)=>a+x*x,0);
 const tail=samples.slice(400),mean=tail.reduce((a,x)=>a+x,0)/tail.length,sd=Math.sqrt(tail.reduce((a,x)=>a+(x-mean)**2,0)/tail.length);
 const threshold=energy*.25+sd*Math.sqrt(energy)*4,detected=!packetLost&&correlation[peak]>threshold;
 let second=peak,bestSecondary=-Infinity;for(let d=14;d<210;d++)if(Math.abs(d-peak)>12&&correlation[d]>bestSecondary){second=d;bestSecondary=correlation[d];}
 const ambiguity=Math.max(0,Math.min(1,correlation[second]/Math.max(1e-8,correlation[peak])));
 const lost=!detected,estimate=detected?peak*c/(2*fs):null,confidence=detected?Math.max(0,Math.min(1,(correlation[peak]-threshold)/(energy*.75)))*(1-ambiguity*.75):0;
 return {source:'synthetic',coordinateFrame:'measurement-space',modality:'acoustic',samples,reference,correlation,estimate,truth,confidence,uncertainty:c/(2*fs)*(1+sd*15+Math.abs(second-peak)*ambiguity),error:estimate===null?null:estimate-truth,lost,unit:'m',observable:'Round-trip scalar range; 3D position is unobservable with one emitter / receiver.'};
}
export function magneticExperiment(s:LabSettings,elapsed:number,point:Vec3):SignalResult {
 const truth=Math.hypot(...point),rand=random(s.seed+Math.floor(elapsed/80)),packetLost=rand()<s.dropout;
 const field=.1/(Math.max(.08,truth)**3),samples=Array.from({length:128},(_,i)=>45+(s.handPresent?field:0)+(rand()*2-1)*s.noise*field*.5+Math.sin(i*.09)*s.drift*.03);
 const mean=samples.reduce((a,b)=>a+b,0)/samples.length-45,sd=Math.sqrt(samples.reduce((a,b)=>a+(b-45-mean)**2,0)/samples.length),lost=packetLost||mean<Math.max(.05,sd*3),estimate=lost?null:Math.cbrt(.1/Math.max(.001,mean));
 return {source:'synthetic',coordinateFrame:'measurement-space',modality:'magnetic',samples,reference:[],correlation:[],estimate,truth,confidence:lost?0:Math.max(0,Math.min(1,1-sd/Math.max(.001,mean))),uncertainty:.003+sd/Math.max(.001,mean)*.035,error:estimate===null?null:estimate-truth,lost,unit:'m',observable:'Ideal calibrated dipole inverse; simulated range only. Phone magnetometer compatibility is unverified.'};
}
export function safeAction(s:{running:boolean;intent:boolean;confidence:number;dropout:boolean;zone:boolean}) {return s.running&&s.intent&&Number.isFinite(s.confidence)&&s.confidence>=.55&&!s.dropout&&s.zone;}
export function pointInZone(point:Vec3,center:Vec3,radius:number) {return Math.hypot(...point.map((v,i)=>v-center[i]))<=radius;}
export function path(values:number[],width=500,height=100) {if(!values.length)return '';const max=Math.max(...values),min=Math.min(...values),spread=Math.max(1e-8,max-min);return values.map((v,i)=>`${i?'L':'M'}${(i/(values.length-1)*width).toFixed(1)},${(height-8-(v-min)/spread*(height-16)).toFixed(1)}`).join(' ');}
