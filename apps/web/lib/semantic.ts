/** Consumer policy accepts ISI inference events; it never sees simulator truth. */
export interface SemanticControls {running:boolean;intent:boolean;mode:string;input:string;view:string;rfKind:string;direction:number;}
interface Event {type:string;deviceId:string;confidence:number;zoneId?:string;relative?:{kind:string;value:number;unit:string};metadata?:Record<string,unknown>;}
export interface Action {active?:boolean;scroll?:number;translation?:number[];rotation?:number;}
export function actionFromEvent(event:Event,c:SemanticControls):Action {
 if(!c.running||!c.intent)return {};
 const device=c.view==='rf'?'web-rf':c.input==='proxy'?'web-proxy':undefined;
 if(device?event.deviceId!==device:!['web-lab','web-camera'].includes(event.deviceId))return {};
 if(event.confidence<.55||!Number.isFinite(event.confidence))return {active:false};
 if(c.view==='rf'&&c.rfKind==='rssi')return {};
 if(['cancel','zone-exit'].includes(event.type))return {active:false};
 if(event.type==='hover'&&event.zoneId){
  if(c.view==='rf'){if(event.metadata?.presence!==true)return {active:false};return {active:true,...(c.mode==='scroll'?{scroll:c.direction*2}:{})};}
  return {active:true};
 }
 if(event.type==='scroll'&&c.mode==='scroll'&&typeof event.metadata?.scrollDelta==='number'&&Number.isFinite(event.metadata.scrollDelta))return {scroll:event.metadata.scrollDelta};
 if(event.type==='drag'&&c.mode==='translate'&&c.input==='proxy'&&Array.isArray(event.metadata?.delta))return {translation:event.metadata.delta as number[]};
 if(event.type==='rotate'&&c.mode==='rotate'&&c.input==='proxy'&&typeof event.metadata?.angleRad==='number')return {rotation:event.metadata.angleRad};
 return {};
}
