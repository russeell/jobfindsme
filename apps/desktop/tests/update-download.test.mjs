import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {randomUUID} from 'node:crypto';
import {mkdtempSync,realpathSync,readFileSync,existsSync,rmSync,writeFileSync,mkdirSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {releaseUpdate} from '../dist-electron/main/updates.js';
import {downloadRelease,fetchReleaseAsset,safeDownloadUrl,DesktopUpdater} from '../dist-electron/main/updates/update-manager.js';

const data=Buffer.alloc(200_000,'x');
const digest=createHash('sha256').update(data).digest('hex');
const asset={name:'mac-arm64.zip',url:'https://github.com/russeell/jobfindsme/releases/download/v2.0.0/mac-arm64.zip',size:data.length,sha256:digest};
const reply=()=>new Response(new ReadableStream({start(controller){for(let i=0;i<data.length;i+=10_000)controller.enqueue(data.subarray(i,i+10_000));controller.close();}}));
async function temporary(run){const dir=mkdtempSync(path.join(os.tmpdir(),'jfm-update-download-'));try{await run(dir);}finally{rmSync(dir,{recursive:true,force:true});}}

test('only compatible release assets with SHA256 and bounded size allow automatic installation',async()=>{
 for(const [size,checksum,ready] of [[data.length,`sha256:${digest}`,true],[0,`sha256:${digest}`,false],[data.length,undefined,false],[1_000_000_001,`sha256:${digest}`,false]]){
  const {result,asset:found}=await releaseUpdate('v1.0.0','darwin',async()=>Response.json({tag_name:'v2.0.0',assets:[{name:'mac-arm64.zip',size,digest:checksum}]}),'arm64');
  assert.equal(result.canInstall,ready);assert.equal(!!found,ready);
  if(found)assert.equal(found.url,asset.url);
 }
});

test('download follows only HTTPS GitHub asset redirects without credentials or uploads',async()=>{
 const calls=[];
 const response=await fetchReleaseAsset(asset.url,async(url,options)=>{calls.push([url,options]);return calls.length===1?new Response(null,{status:302,headers:{location:'https://release-assets.githubusercontent.com/asset?signature=fictional'}}):reply();},new AbortController().signal);
 await response.arrayBuffer();assert.equal(calls.length,2);
 for(const [,options]of calls){assert.equal(options.method,'GET');assert.equal(options.credentials,'omit');assert.equal(options.body,undefined);assert.equal(options.headers.Authorization,undefined);}
 for(const url of ['http://github.com/a','https://github.com.evil.test/a','https://user:pass@github.com/a','https://github.com:8443/a','file:///tmp/a','https://127.0.0.1/a'])assert.equal(safeDownloadUrl(url),false);
 await assert.rejects(fetchReleaseAsset(asset.url,async()=>new Response(null,{status:302,headers:{location:'https://untrusted.test/file'}}),new AbortController().signal),/不受信任/);
});

test('streamed progress is monotonic and only a completely verified file becomes update.zip',()=>temporary(async dir=>{
 const file=path.join(dir,'update.zip'),progress=[];
 await downloadRelease(asset,file,async()=>reply(),new AbortController().signal,n=>progress.push(n));
 assert.deepEqual(readFileSync(file),data);assert.equal(existsSync(`${file}.part`),false);
 assert.equal(progress.at(-1),data.length);assert(progress.every((n,i)=>i===0||n>=progress[i-1]));
}));

test('tampered, truncated, oversized and length-mismatched downloads cannot replace any program',()=>temporary(async dir=>{
 const marker=path.join(dir,'existing-program');writeFileSync(marker,'Fictional old program');
 for(const response of [new Response('short'),new Response(Buffer.alloc(data.length+1)),new Response(Buffer.alloc(data.length,'y')),new Response(data,{headers:{'content-length':'1'}})]){
  const file=path.join(dir,'update.zip');
  await assert.rejects(downloadRelease(asset,file,async()=>response,new AbortController().signal,()=>{}));
  assert.equal(existsSync(file),false);assert.equal(existsSync(`${file}.part`),false);assert.equal(readFileSync(marker,'utf8'),'Fictional old program');
 }
}));

test('cancellation removes only the partial download and does not send a second request',()=>temporary(async dir=>{
 const controller=new AbortController(),file=path.join(dir,'update.zip');let requests=0;
 await assert.rejects(downloadRelease(asset,file,async()=>{requests++;return reply();},controller.signal,()=>controller.abort()));
 assert.equal(requests,1);assert.equal(existsSync(file),false);assert.equal(existsSync(`${file}.part`),false);
}));

test('concurrent download clicks coalesce and preparation failure never exits the current application',()=>temporary(async dir=>{
 const runtime=path.join(dir,'runtime'),cache=path.join(dir,'cache'),target=path.join(dir,'target');mkdirSync(runtime);mkdirSync(target);writeFileSync(path.join(target,'original'),'fictional');let quits=0,requests=0;
 const updater=new DesktopUpdater({currentTag:'v1.0.0',platform:'darwin',arch:'arm64',target,runtime,cache,onState:()=>{},beforeQuit:async()=>{},quit:()=>quits++,request:async url=>{requests++;return String(url).includes('/releases/latest')?Response.json({tag_name:'v2.0.0',assets:[{name:asset.name,size:asset.size,digest:`sha256:${digest}`}]}):reply();}});
 const one=updater.download(),two=updater.download();assert.equal(one,two);await one;
 assert.equal(requests,2);assert.equal(quits,0);assert.equal(updater.getState().phase,'error');assert.equal(readFileSync(path.join(target,'original'),'utf8'),'fictional');
}));

test('restart reports a rollback without exposing the private transaction to the renderer',()=>temporary(async dir=>{
 const id=randomUUID(),cache=path.join(dir,'updates'),job=path.join(cache,id),target=path.join(dir,'fictional-private-install');mkdirSync(job,{recursive:true});
 writeFileSync(path.join(cache,'active.json'),JSON.stringify({id}));
 writeFileSync(path.join(job,'request.json'),JSON.stringify({id,job:realpathSync(job),target,version:'v2.0.0',currentVersion:'v1.0.0',token:'fictional-private-token'}));
 writeFileSync(path.join(job,'state.json'),JSON.stringify({phase:'rolled_back'}));
 const updater=new DesktopUpdater({currentTag:'v1.0.0',platform:'darwin',arch:'arm64',cache,target,onState:()=>{},beforeQuit:async()=>{},quit:()=>assert.fail('Must not restart while reading an outcome')});
 await updater.restore();assert.equal(updater.getState().phase,'rolled_back');assert.equal(updater.getState().transactionId,id);
 assert(!JSON.stringify(updater.getState()).includes('fictional-private'));
}));
