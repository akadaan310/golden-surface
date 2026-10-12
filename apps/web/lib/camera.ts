import type {InteractionEngine,Measurement} from '@golden-motion/isi';
/** Browser observation of a newly decoded frame; acquiredAt is before inference, not hardware exposure time. */
export interface CameraObservation {x:number;y:number;confidence:number;acquiredAt:number;processedAt:number;hand:boolean;}
export function cameraMeasurement(o:CameraObservation,intent:boolean):Measurement {
 const hand=o.hand&&Number.isFinite(o.x)&&Number.isFinite(o.y)&&o.x>=0&&o.x<=1&&o.y>=0&&o.y<=1;
 return {timestamp:o.acquiredAt,source:'live',modality:'optical',deviceId:'web-camera',coordinateFrame:'camera-image-normalized',...(hand?{position:[o.x,o.y,0] as [number,number,number],uncertainty:[.02,.02,0]}:{relative:{kind:'hand-presence',value:0,unit:'unitless'},uncertainty:[1]}),confidence:hand&&Number.isFinite(o.confidence)?Math.max(0,Math.min(1,o.confidence)):0,intent,metadata:{acquiredAt:o.acquiredAt,processedAt:o.processedAt,acquisitionTimeMeaning:'epoch when a new decoded browser video frame was observed before inference; hardware exposure timestamp unavailable',depth:'unmeasured',evidence:'MediaPipe image-plane landmarks',z:'fixed placeholder; not depth',confidenceMeaning:'MediaPipe handedness score; not calibrated tracking accuracy'}};
}
/** Acquisition identity survives SDK dropout/reset, so replaying a frozen frame cannot re-enter a zone. */
export class CameraFrameConsumer {
 private lastAcquiredAt=-Infinity;
 constructor(private readonly maxFrameAgeMs=350){}
 sample(engine:InteractionEngine,o:CameraObservation|null,intent:boolean,now:number):Measurement|null {
  engine.tick(now);
  if(!o||!Number.isFinite(o.acquiredAt)||o.acquiredAt<=this.lastAcquiredAt)return null;
  this.lastAcquiredAt=o.acquiredAt;
  if(now-o.acquiredAt>this.maxFrameAgeMs||o.acquiredAt>now||!Number.isFinite(o.processedAt))return null;
  const m=cameraMeasurement(o,intent);engine.ingest(m);return m;
 }
}
