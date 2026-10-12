'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { HandLandmarker } from '@mediapipe/tasks-vision';
import type {CameraObservation} from './camera';
export type {CameraObservation} from './camera';
export function useCamera(onObservation:(observation:CameraObservation)=>void){
 const videoRef=useRef<HTMLVideoElement>(null),stream=useRef<MediaStream|null>(null),model=useRef<HandLandmarker|null>(null),raf=useRef(0),generation=useRef(0),callback=useRef(onObservation),timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const [state,setState]=useState<'off'|'loading'|'live'|'unavailable'>('off'),[message,setMessage]=useState('Opt-in camera reference. Frames stay in this browser; no measured depth.');
 callback.current=onObservation;
 const stop=useCallback(()=>{generation.current++;cancelAnimationFrame(raf.current);if(timer.current)clearTimeout(timer.current);stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;model.current?.close();model.current=null;if(videoRef.current)videoRef.current.srcObject=null;setState('off');setMessage('Camera stopped. No frames retained.');},[]);
 const start=useCallback(async()=>{
  if(state==='loading'||state==='live')return;const id=++generation.current;setState('loading');setMessage('Requesting camera permission and loading local hand model…');
  try {
   if(!navigator.mediaDevices?.getUserMedia)throw new Error('Camera API unavailable. Use localhost or an HTTPS secure context.');
   const media=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480,facingMode:'user'},audio:false});if(id!==generation.current){media.getTracks().forEach(t=>t.stop());return;}stream.current=media;
   const {FilesetResolver,HandLandmarker}=await import('@mediapipe/tasks-vision');const files=await FilesetResolver.forVisionTasks('/vision');const hand=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/vision/hand_landmarker.task',delegate:'CPU'},runningMode:'VIDEO',numHands:1,minHandDetectionConfidence:.65,minHandPresenceConfidence:.65,minTrackingConfidence:.65});
   if(id!==generation.current){hand.close();return;}model.current=hand;const video=videoRef.current;if(!video)throw new Error('Camera view is unavailable');video.srcObject=media;await video.play();if(id!==generation.current)return;setState('live');setMessage('Live image-plane hand landmarks · local CPU · no measured depth.');
   let previous=-1,last=0;const frame=(now:number)=>{if(id!==generation.current)return;if(video.readyState>=2&&video.currentTime!==previous&&now-last>90){try{previous=video.currentTime;last=now;const acquiredAt=Date.now(),result=hand.detectForVideo(video,now),p=result.landmarks[0]?.[9];callback.current(p?{x:p.x,y:p.y,confidence:result.handedness[0]?.[0]?.score??.7,acquiredAt,processedAt:Date.now(),hand:true}:{x:0,y:0,confidence:0,acquiredAt,processedAt:Date.now(),hand:false});}catch{stop();setState('unavailable');setMessage('Hand inference failed; camera released. Synthetic reference remains available.');return;}}raf.current=requestAnimationFrame(frame);};raf.current=requestAnimationFrame(frame);
   timer.current=setTimeout(()=>{stop();setMessage('Five-minute camera session ended automatically. Re-enable to continue.');},300000);
  }catch(error){stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;model.current?.close();model.current=null;if(id===generation.current){setState('unavailable');setMessage(error instanceof Error?`Camera unavailable (${error.name}): ${error.message}`:'Camera unavailable.');}}
 },[state,stop]);
 useEffect(()=>{const hidden=()=>{if(document.hidden)stop();};document.addEventListener('visibilitychange',hidden);window.addEventListener('pagehide',stop);return()=>{document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pagehide',stop);generation.current++;cancelAnimationFrame(raf.current);if(timer.current)clearTimeout(timer.current);stream.current?.getTracks().forEach(t=>t.stop());model.current?.close();};},[stop]);
 return {videoRef,state,message,start,stop};
}
