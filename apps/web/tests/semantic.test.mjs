import {test} from 'node:test';import assert from 'node:assert/strict';import {actionFromEvent} from '../lib/semantic.ts';
const event={type:'scroll',confidence:.8,deviceId:'web-lab',relative:{kind:'range',value:.3,unit:'m'},metadata:{scrollDelta:25}};
const controls={running:true,intent:true,mode:'scroll',input:'sensor',view:'spatial',rfKind:'csi',direction:1};
test('scroll applies the shared inference event delta rather than synthetic truth',()=>{assert.deepEqual(actionFromEvent(event,controls),{scroll:25});});
test('stop disarm lowconfidence and wrong observation prevent actions',()=>{for(const change of [{running:false},{intent:false},{input:'proxy'}])assert.deepEqual(actionFromEvent(event,{...controls,...change}),{});assert.deepEqual(actionFromEvent({...event,confidence:.1},controls),{active:false});});
test('unsigned RF score never creates a signed sensor displacement',()=>{assert.deepEqual(actionFromEvent({...event,deviceId:'web-rf',relative:{kind:'rf-motion-score',value:.9,unit:'unitless'},metadata:{}},{...controls,view:'rf'}),{});});
test('RF synthetic continuous policy requires inference hover and explicit user direction',()=>{const rf={type:'hover',deviceId:'web-rf',confidence:.8,zoneId:'rf-trigger',metadata:{presence:true}};assert.deepEqual(actionFromEvent(rf,{...controls,view:'rf',direction:-1}),{active:true,scroll:-2});assert.deepEqual(actionFromEvent(rf,{...controls,view:'rf',rfKind:'rssi'}),{});});
test('a low-confidence event releases previous consumer hover state',()=>{assert.deepEqual(actionFromEvent({...event,confidence:.1},controls),{active:false});});
