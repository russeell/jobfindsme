import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createOriginalReader} from '../dist-electron/main/research/original-reader.js';
import {createPublicNetworkGuard} from '../dist-electron/main/browser/public-network.js';
const input={workspace:'w1',session:'public',site:'web',url:'https://example.org/a',company:'',focus:'topic'};
const original={status:'read_original',evidence_id:'ev_test',url:input.url,excerpt:'Verified original',context:{}};
test('HTTP empty body falls back once, cache isolates workspace/session/focus and expires',async()=>{
 let now=1000,reads=0,browsers=0;const read=createOriginalReader(()=>now),http=async()=>{reads++;return {status:'empty_body'};},browser=async()=>{browsers++;return original;},signal=new AbortController().signal;
 assert.equal((await read(input,http,browser,signal,8000)).status,'read_original');
 assert.equal((await read(input,http,browser,signal,8000)).context.cache_status,'fresh');assert.equal(browsers,1);
 for(const changed of [{...input,workspace:'w2'},{...input,session:'logged-in'},{...input,focus:'other'}])await read(changed,http,browser,signal,8000);
 now+=300001;await read(input,http,browser,signal,8000);assert.equal(reads,5);assert.equal(browsers,5);
});
test('cancelling an original aborts its network and never starts a browser',async()=>{
 const c=new AbortController();let aborted=false,browsers=0;
 const work=createOriginalReader()(input,signal=>new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>{aborted=true;reject(Error('cancelled'));},{once:true})),async()=>{browsers++;return original;},c.signal,5000);
 c.abort();await assert.rejects(work,/cancelled/);assert.equal(aborted,true);assert.equal(browsers,0);
});
test('gate pages are not cached, and unsafe transport errors never use browser fallback',async()=>{
 const read=createOriginalReader(),signal=new AbortController().signal;let calls=0;
 for(let i=0;i<2;i++)assert.equal((await read(input,async()=>({status:'verification_required'}),async()=>{calls++;return {status:'verification_required'};},signal,8000)).status,'verification_required');
 assert.equal(calls,2);await assert.rejects(read(input,async()=>{throw Error('TLS certificate invalid');},async()=>{throw Error('unexpected browser');},signal,8000),/TLS/);
});
test('public browser DNS rejects private, mixed and special addresses while accepting public resources',async()=>{
 for(const address of ['127.0.0.1','10.2.3.4','100.64.0.1','198.18.0.1','169.254.169.254','::1','fd00::1']){
  const guard=createPublicNetworkGuard(async()=>[{address,family:address.includes(':')?6:4}]);assert.equal(await guard('https://public.example.org/a'),false,address);
 }
 const mixed=createPublicNetworkGuard(async()=>[{address:'8.8.8.8',family:4},{address:'10.0.0.1',family:4}]);assert.equal(await mixed('https://public.example.org/'),false);
 const publicOnly=createPublicNetworkGuard(async()=>[{address:'8.8.8.8',family:4}]);assert.equal(await publicOnly('https://public.example.org/app.js'),true);assert.equal(await publicOnly('https://public.example.org:3000/'),false);
});

test('a structured TLS failure is returned without retrying through another transport',async()=>{
 let browserCalls=0;const row={status:'read_failed',url:input.url,limit:'TLS certificate failure'};
 const value=await createOriginalReader()(input,async()=>row,async()=>{browserCalls++;return original;},new AbortController().signal,8000);
 assert.equal(value.limit,row.limit);assert.equal(browserCalls,0);
});
