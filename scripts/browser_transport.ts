/** Same-host semantic latency/render benchmark, not Galaxy A16 performance. */
import { chromium } from '@playwright/test';
import { randomBytes } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import WebSocket from 'ws';
import { startRelay } from '../services/relay/src/server';

async function main(){
const token=randomBytes(24).toString('hex');
const relay=await startRelay({token,port:0});
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let socket:WebSocket|undefined;
try {
 const page=await browser.newPage({viewport:{width:1280,height:960}});
 await page.goto(process.env.GM_WEB_URL??'http://127.0.0.1:3001');
 await page.getByRole('heading',{name:'Beyond the screen.'}).waitFor();
 await page.locator('canvas').waitFor();
 await page.waitForFunction(()=>Boolean(document.querySelector('canvas')?.getAttribute('data-rendered-frames')));
 const counterBefore=await page.locator('canvas').getAttribute('data-rendered-frames');
 const standbyStarted=Date.now();
 // A literal browser program avoids TSX/esbuild's Node-only function-name helper
 // leaking into Playwright's serialized callback.
 const frameIntervals=await page.evaluate<number[]>(`new Promise(resolve=>{
  const intervals=[];let previous=performance.now();
  function frame(time){intervals.push(time-previous);previous=time;
   if(intervals.length>=120)resolve(intervals.slice(1));else requestAnimationFrame(frame);}
  requestAnimationFrame(frame);
 })`);
 const standbyElapsed=Date.now()-standbyStarted;
 const idleFrames=Number(await page.locator('canvas').getAttribute('data-rendered-frames'))-Number(counterBefore);
 await page.getByRole('button',{name:/Evidence & protocol/}).click();
 await page.getByRole('textbox',{name:'Relay URL',exact:true}).fill(relay.address);
 await page.getByLabel('Relay session token',{exact:true}).fill(token);
 await page.getByRole('button',{name:'Connect relay',exact:true}).click();
 await page.getByText('connected',{exact:true}).waitFor();
 await page.getByRole('switch',{name:/Use fresh relay events in preview/}).click();
 await page.getByRole('button',{name:/Spatial laboratory/}).click();
 await page.getByTestId('running-toggle').click();await page.getByTestId('intent-toggle').click();
 const activeStartFrames=Number(await page.locator('canvas').getAttribute('data-rendered-frames'));
 const activeStart=Date.now();await page.waitForTimeout(2000);
 const activeElapsed=Date.now()-activeStart;
 const activeFrames=Number(await page.locator('canvas').getAttribute('data-rendered-frames'))-activeStartFrames;
 const rendererPolicy=await page.locator('canvas').evaluate(canvas=>({
  policy:canvas.getAttribute('data-frame-policy'),quality:canvas.getAttribute('data-render-quality'),
  scheduledHz:Number(canvas.getAttribute('data-animation-cap-hz'))}));
 socket=new WebSocket(relay.address);await new Promise<void>(resolve=>socket!.once('open',()=>resolve()));
 socket.send(JSON.stringify({type:'auth',token,role:'publisher'}));
 await new Promise<void>(resolve=>socket!.once('message',()=>resolve()));
 const latencies:number[]=[];
 for(let i=1;i<=10;i++){
  const sentAt=Date.now();
  socket.send(JSON.stringify({type:'event',event:{id:`latency-${i}`,type:'scroll',timestamp:sentAt,
    source:'synthetic',modality:'acoustic',deviceId:'latency-native-shaped',coordinateFrame:'measurement-space',
    confidence:.95,relative:{kind:'range',value:.3,unit:'m'},uncertainty:[.001],
    metadata:{scrollDelta:5,intentional:true,evidence:'same-host synthetic protocol benchmark'}}}));
  await page.waitForFunction(target=>Number(document.querySelector('[data-testid="scroll-demo"]')?.getAttribute('data-scroll-position'))===target,i*5,{polling:'raf',timeout:2000});
  latencies.push(Date.now()-sentAt);
 }
 const sorted=(values:number[])=>[...values].sort((a,b)=>a-b);
 const percentile=(values:number[],q:number)=>sorted(values)[Math.min(values.length-1,Math.floor(q*values.length))];
 const mean=(values:number[])=>values.reduce((s,v)=>s+v,0)/values.length;
 const result={source:'synthetic',environment:'same-host headless Chromium software rendering',
   physicalPhoneTested:false,latency:{samplesMs:latencies,meanMs:mean(latencies),p95Ms:percentile(latencies,.95),
     measurement:'host publisher send to observable browser semantic action commit; synchronized same-host epoch'},
   rendering:{samples:frameIntervals.length,meanRafIntervalMs:mean(frameIntervals),p95RafIntervalMs:percentile(frameIntervals,.95),
     observedStandbyRafFps:1000/mean(frameIntervals),standbyRenderedFrames:idleFrames,standbyElapsedMs:standbyElapsed,
     activeRenderedFrames:activeFrames,activeElapsedMs:activeElapsed,observedActiveRenderFps:activeFrames*1000/activeElapsed,
     ...rendererPolicy,measurement:'Actual Three.js frame counter plus browser RAF cadence; software renderer, not Galaxy A16 GPU'},
   limitations:['No Galaxy A16 FPS/power/network/camera performance measured.','Browser cadence and instrumentation include software-renderer/host load.']};
 await writeFile('artifacts/browser-performance.json',JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result,null,2));
} finally {socket?.terminate();await browser.close();await relay.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
