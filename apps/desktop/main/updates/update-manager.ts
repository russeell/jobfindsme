import {spawn,execFile} from 'node:child_process';
import {createHash,randomBytes,randomUUID} from 'node:crypto';
import {createWriteStream} from 'node:fs';
import {access,cp,mkdir,readFile,rename,rm,writeFile,realpath} from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {Readable,Transform} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {releaseUpdate,type ReleaseAsset} from '../updates';
import type {UpdateResult,UpdateState} from '../../shared/update-contracts';

type Options={currentTag:string;platform:string;arch:string;cache:string;target?:string;runtime?:string;restartArgs?:string[];request?:typeof fetch;onState(state:UpdateState):void;beforeQuit():Promise<void>;quit():void};
type Transaction={schema:1;id:string;job:string;platform:string;target:string;version:string;currentVersion:string;sha256:string;token:string;parentPid:number;restartArgs:string[]};

export function safeDownloadUrl(value:string):boolean{
 try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password&&!url.port&&['github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'].includes(url.hostname);}catch{return false;}
}
export async function fetchReleaseAsset(url:string,request:typeof fetch,signal:AbortSignal):Promise<Response>{
 for(let redirects=0;redirects<6;redirects++){
  if(!safeDownloadUrl(url))throw Error('更新下载地址不受信任。');
  const response=await request(url,{method:'GET',credentials:'omit',referrerPolicy:'no-referrer',redirect:'manual',signal,headers:{Accept:'application/octet-stream'}});
  if([301,302,303,307,308].includes(response.status)){
   const location=response.headers.get('location');await response.body?.cancel();if(!location)throw Error('更新下载重定向无效。');url=new URL(location,url).href;continue;
  }
  if(!response.ok||!response.body)throw Error('更新下载失败，请稍后重试。');
  return response;
 }
 throw Error('更新下载重定向过多。');
}
export async function downloadRelease(asset:ReleaseAsset,file:string,request:typeof fetch,signal:AbortSignal,progress:(received:number)=>void):Promise<void>{
 const partial=`${file}.part`;
 const stalled=new AbortController();let timer:ReturnType<typeof setTimeout>;
 const touch=()=>{clearTimeout(timer);timer=setTimeout(()=>stalled.abort(),60_000);};touch();
 const combined=AbortSignal.any([signal,stalled.signal]);
 try{
  const response=await fetchReleaseAsset(asset.url,request,combined);
  const length=response.headers.get('content-length');
  if(length!==null&&Number(length)!==asset.size){await response.body?.cancel();throw Error('更新文件大小不符，已停止下载。');}
  const hash=createHash('sha256');let received=0,last=0;
  const meter=new Transform({transform(chunk,_encoding,callback){touch();received+=chunk.length;if(received>asset.size){callback(Error('更新文件超过声明大小。'));return;}hash.update(chunk);if(Date.now()-last>150||received===asset.size){progress(received);last=Date.now();}callback(null,chunk);}});
  await pipeline(Readable.fromWeb(response.body as never),meter,createWriteStream(partial,{flags:'wx',mode:0o600}),{signal:combined});
  if(received!==asset.size||hash.digest('hex')!==asset.sha256)throw Error('更新文件校验失败，当前程序未更改，请重新下载。');
  await rename(partial,file);
 }catch(error){await rm(partial,{force:true});if(stalled.signal.aborted)throw Error('下载长时间没有响应，请检查网络后重试。');throw error;}finally{clearTimeout(timer!);}
}
function runHelper(executable:string,args:string[],signal?:AbortSignal):Promise<void>{
 return new Promise((resolve,reject)=>execFile(executable,args,{windowsHide:true,timeout:180_000,maxBuffer:64_000,signal,env:{...process.env,PYINSTALLER_RESET_ENVIRONMENT:'1'}},error=>error?reject(Error('更新包无法准备；请检查目录权限和磁盘空间后重试。')):resolve()));
}

export class DesktopUpdater{
 private state:UpdateState={phase:'idle',message:'点击检查新版本。'};
 private checkFlight?:Promise<UpdateResult>;
 private flight?:Promise<UpdateState>;
 private controller?:AbortController;
 private transaction?:Transaction;
 private installed=false;
 private releaseFlight?:ReturnType<typeof releaseUpdate>;
 constructor(private readonly options:Options){}
 getState():UpdateState{return {...this.state};}
 private set(state:UpdateState){this.state=state;this.options.onState(this.getState());return this.getState();}
 private latest(){if(!this.releaseFlight)this.releaseFlight=releaseUpdate(this.options.currentTag,this.options.platform,this.options.request,this.options.arch).finally(()=>{this.releaseFlight=undefined;});return this.releaseFlight;}
 check():Promise<UpdateResult>{
  if(this.checkFlight)return this.checkFlight;
  const busy=['downloading','verifying','ready','installing'].includes(this.state.phase);
  if(!busy)this.set({phase:'checking',message:'正在检查新版本…'});
  this.checkFlight=this.latest().then(({result})=>{
   if(!busy&&!['downloading','verifying','ready','installing'].includes(this.state.phase))this.set({phase:result.status,tag:result.tag,canInstall:result.canInstall,message:result.message});return result;
  }).catch(error=>{if(!busy)this.set({phase:'error',message:error instanceof Error?error.message:'暂时无法检查更新。'});throw error;}).finally(()=>{this.checkFlight=undefined;});return this.checkFlight;
 }
 async restore():Promise<void>{
  try{
   const active=JSON.parse(await readFile(path.join(this.options.cache,'active.json'),'utf8'));
   if(!/^[a-f0-9-]{36}$/.test(active.id))return;
   const job=path.join(this.options.cache,active.id),transaction=JSON.parse(await readFile(path.join(job,'request.json'),'utf8')) as Transaction;
   const state=JSON.parse(await readFile(path.join(job,'state.json'),'utf8'));
   if(transaction.job!==await realpath(job)||transaction.id!==active.id||transaction.target!==this.options.target)return;
   if(state.phase==='ready'&&transaction.currentVersion===this.options.currentTag){this.transaction=transaction;this.set({phase:'ready',tag:transaction.version,message:'更新已下载，重启前将再次校验。'});}
   if(state.phase==='installed'&&transaction.version===this.options.currentTag)this.set({phase:'installed',tag:transaction.version,transactionId:transaction.id,message:'更新成功，本地资料与登录会话已保留。'});
   if(state.phase==='rolled_back')this.set({phase:'rolled_back',tag:transaction.version,transactionId:transaction.id,message:'新版启动失败，已恢复旧程序。本地资料仍保留，可重新下载或手动安装。'});
  }catch{/* Missing/partial records are never trusted as ready. */}
 }
 download():Promise<UpdateState>{
  if(this.flight)return this.flight;
  if(this.state.phase==='ready')return Promise.resolve(this.getState());
  if(this.state.phase==='installing')return Promise.resolve(this.getState());
  this.controller=new AbortController();
  this.flight=this.downloadWork(this.controller.signal).catch(error=>this.set({phase:this.controller?.signal.aborted?'cancelled':'error',tag:this.state.tag,message:this.controller?.signal.aborted?'下载已取消，当前程序未更改。':error instanceof Error?error.message:'更新失败，请重试。'})).finally(()=>{this.flight=undefined;this.controller=undefined;});return this.flight;
 }
 private async downloadWork(signal:AbortSignal):Promise<UpdateState>{
  const {target,runtime}=this.options;
  if(!target||!runtime)throw Error('开发版或测试版不自动替换程序，请安装正式版后更新。');
  const cacheRelative=path.relative(target,this.options.cache);
  if(!cacheRelative||!cacheRelative.startsWith(`..${path.sep}`)&&cacheRelative!=='..'&&!path.isAbsolute(cacheRelative))throw Error('用户资料位于程序目录内，不能直接替换此目录；请先保留资料并手动更新。');
  if(target.includes('AppTranslocation'))throw Error('请先将应用移到“应用程序”文件夹并重新打开，再下载更新。');
  try{await access(path.dirname(target),constants.W_OK);}catch{throw Error('当前安装目录不可写，请将应用移到可写目录后重试，或手动安装。');}
  this.set({phase:'checking',message:'正在确认适合当前系统的新版本…'});
  const {result,asset}=await this.latest();
  if(!asset||result.status!=='available')return this.set({phase:result.status,tag:result.tag,message:result.message,canInstall:false});
  signal.throwIfAborted();
  await mkdir(this.options.cache,{recursive:true,mode:0o700});
  const id=randomUUID(),job=path.join(await realpath(this.options.cache),id);await mkdir(job,{mode:0o700});
  const transaction:Transaction={schema:1,id,job,platform:this.options.platform,target,version:result.tag!,currentVersion:this.options.currentTag,sha256:asset.sha256,token:randomBytes(32).toString('hex'),parentPid:process.pid,restartArgs:this.options.restartArgs??[]};
  this.set({phase:'downloading',tag:result.tag,received:0,total:asset.size,message:'正在下载更新…'});
  try{
   await downloadRelease(asset,path.join(job,'update.zip'),this.options.request??fetch,signal,received=>this.set({phase:'downloading',tag:result.tag,received,total:asset.size,message:'正在下载更新…'}));
   signal.throwIfAborted();this.set({phase:'verifying',tag:result.tag,message:'正在校验并准备更新，当前程序仍可使用…'});
   await cp(runtime,path.join(job,'runtime'),{recursive:true,verbatimSymlinks:true});signal.throwIfAborted();
   await writeFile(path.join(job,'request.json'),JSON.stringify(transaction),{mode:0o600});
   await runHelper(this.helper(transaction),['--desktop-update','prepare',path.join(job,'request.json')],signal);
   signal.throwIfAborted();await writeFile(path.join(this.options.cache,'active.json'),JSON.stringify({id}),{mode:0o600});this.transaction=transaction;
   return this.set({phase:'ready',tag:result.tag,message:'更新已校验。重启将保存本机草稿、安装新版并恢复窗口。'});
  }catch(error){await rm(job,{recursive:true,force:true});throw error;}
 }
 cancel():UpdateState{if(['checking','downloading'].includes(this.state.phase))this.controller?.abort();return this.getState();}
 private helper(transaction:Transaction){return path.join(transaction.job,'runtime',this.options.platform==='win32'?'jobfindsme-api.exe':'jobfindsme-api');}
 install():Promise<UpdateState>{
  if(this.flight)return this.flight;
  if(this.installed)return Promise.resolve(this.getState());
  this.flight=this.installWork().catch(error=>this.set({phase:'error',tag:this.state.tag,message:error instanceof Error?error.message:'未能开始安装，当前程序未更改。'})).finally(()=>{this.flight=undefined;});return this.flight;
 }
 private async installWork():Promise<UpdateState>{
  const transaction=this.transaction;
  if(!transaction||this.state.phase!=='ready')throw Error('请先完成更新下载和校验。');
  this.set({phase:'installing',tag:transaction.version,message:'正在再次校验更新并准备安全退出…'});
  transaction.parentPid=process.pid;await writeFile(path.join(transaction.job,'request.json'),JSON.stringify(transaction),{mode:0o600});
  const child=spawn(this.helper(transaction),['--desktop-update','install',path.join(transaction.job,'request.json')],{cwd:transaction.job,stdio:['ignore','pipe','ignore'],windowsHide:true,detached:true,env:{...process.env,PYINSTALLER_RESET_ENVIRONMENT:'1'}});
  try{
   await new Promise<void>((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('安装准备超时，当前程序未更改。')),180_000);const finish=(error?:Error)=>{clearTimeout(timer);child.stdout?.removeAllListeners('data');error?reject(error):resolve();};child.once('error',()=>finish(Error('无法启动独立更新进程。')));child.once('exit',()=>finish(Error('更新包未通过安装前校验。')));child.stdout?.on('data',chunk=>{output+=chunk.toString();if(output.includes('"waiting"'))finish();else if(output.length>64_000)finish(Error('更新进程响应异常。'));});});
   let quitTimer:ReturnType<typeof setTimeout>|undefined;
   try{await Promise.race([this.options.beforeQuit(),new Promise<never>((_resolve,reject)=>{quitTimer=setTimeout(()=>reject(Error('资料保存超时，已保留当前程序，请稍后重试。')),15_000);})]);}finally{clearTimeout(quitTimer);}
   if(child.exitCode!==null)throw Error('独立更新进程已退出，当前程序未更改。');
   child.stdout?.destroy();child.unref();this.installed=true;this.options.quit();return this.getState();
  }catch(error){child.kill();this.set({phase:'ready',tag:transaction.version,message:'未能安全退出，当前程序未更改。请完成正在进行的操作后重试。'});throw error;}
 }
}

export async function acknowledgeUpdateStartup(manifestPath:string|undefined,installedRoot:string|undefined,tag:string):Promise<void>{
 if(!manifestPath||!installedRoot)return;
 try{
  const request=JSON.parse(await readFile(manifestPath,'utf8')) as Transaction;
  if(request.version!==tag||request.target!==installedRoot||request.job!==await realpath(path.dirname(manifestPath))||!/^([a-f0-9]{64})$/.test(request.token))return;
  await writeFile(path.join(request.job,'health.json'),JSON.stringify({id:request.id,token:request.token,version:tag,pid:process.pid}),{mode:0o600});
 }finally{delete process.env.JFM_UPDATE_MANIFEST;}
}
