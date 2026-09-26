import test from 'node:test';
import assert from 'node:assert/strict';
import {checkForUpdates} from '../dist-electron/main/updates.js';
const reply=(data,status=200)=>async()=>new Response(JSON.stringify(data),{status});
test('unpublished, missing desktop asset and preview are distinguished',async()=>{
 assert.equal((await checkForUpdates('','darwin',reply({},404))).status,'unpublished');
 assert.equal((await checkForUpdates('','darwin',reply({tag_name:'v1',assets:[{name:'source.tar.gz'}]}))).status,'unpublished');
 assert.equal((await checkForUpdates('','darwin',reply({tag_name:'v1',assets:[{name:'JobFindsMe-mac.dmg'}]}))).status,'available');
 assert.equal((await checkForUpdates('v1','darwin',reply({tag_name:'v1',assets:[{name:'JobFindsMe-mac.dmg'}]}))).status,'current');
});
test('service errors never masquerade as current version',async()=>{
 await assert.rejects(checkForUpdates('','darwin',reply({},403)),/限流/);
 await assert.rejects(checkForUpdates('','darwin',reply({})),/无效/);
 await assert.rejects(checkForUpdates('','darwin',async()=>{throw Error('offline');}),/offline/);
});

test('Windows portable releases are compatible only on Windows',async()=>{
 const response=reply({tag_name:'v2',assets:[{name:'JobFindsMe-windows-x64.zip'}]});
 assert.equal((await checkForUpdates('v1','win32',response)).status,'available');
 assert.equal((await checkForUpdates('v1','darwin',response)).status,'unpublished');
});
