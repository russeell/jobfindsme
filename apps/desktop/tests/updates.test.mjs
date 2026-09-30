import test from 'node:test';
import assert from 'node:assert/strict';
import {checkForUpdates} from '../dist-electron/main/updates.js';
const reply=(data,status=200)=>async()=>new Response(JSON.stringify(data),{status});
test('unpublished, missing desktop asset and installed version are distinguished',async()=>{
 assert.equal((await checkForUpdates('','darwin',reply({},404))).status,'unpublished');
 assert.equal((await checkForUpdates('','darwin',reply({tag_name:'v1',assets:[{name:'source.tar.gz'}]}))).status,'unpublished');
 assert.equal((await checkForUpdates('v1.0.0','darwin',reply({tag_name:'v1.0.1',assets:[{name:'mac-arm64.zip'}]}), 'arm64')).status,'available');
 assert.equal((await checkForUpdates('v1.0.1','darwin',reply({tag_name:'v1.0.1',assets:[{name:'mac-arm64.zip'}]}), 'arm64')).status,'current');
 assert.equal((await checkForUpdates('v1.1.0','darwin',reply({tag_name:'v1.0.1',assets:[{name:'mac-arm64.zip'}]}), 'arm64')).status,'current');
});
test('service errors never masquerade as current version',async()=>{
 await assert.rejects(checkForUpdates('','darwin',reply({},403)),/限流/);
 await assert.rejects(checkForUpdates('','darwin',reply({})),/无效/);
 await assert.rejects(checkForUpdates('','darwin',async()=>{throw Error('offline');}),/offline/);
 await assert.rejects(checkForUpdates('preview','darwin',reply({tag_name:'v1.0.0',assets:[{name:'mac-arm64.zip'}]}),'arm64'),/无法比较/);
});

test('Windows portable releases are compatible only on Windows',async()=>{
 const response=reply({tag_name:'v2.0.0',assets:[{name:'windows-x64.zip'}]});
 assert.equal((await checkForUpdates('v1.0.0','win32',response,'x64')).status,'available');
 assert.equal((await checkForUpdates('v1.0.0','darwin',response,'arm64')).status,'unpublished');
 assert.equal((await checkForUpdates('v1.0.0','win32',response,'arm64')).status,'unpublished');
});
