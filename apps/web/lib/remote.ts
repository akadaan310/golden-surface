/** Protocol tolerance and action freshness are separate. This assumes synchronized epoch clocks. */
export function remoteEventFresh(timestamp:number,now:number){return Number.isFinite(timestamp)&&Math.abs(now-timestamp)<=1000;}
export function remoteFrameAllowed(frame:string,kind?:string){return frame==='phone-local-m'||frame==='camera-image-normalized'||frame==='measurement-space'&&['range','rf-motion-score'].includes(kind??'');}
