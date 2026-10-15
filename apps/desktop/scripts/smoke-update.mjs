// CI only: actual shipped UI, updater, frozen guardian and application processes.
// The sole substituted boundary is the anonymous release GET response. Fixtures
// are generated on the runner; never copy a developer's profile or real resume.
import {_electron as electron} from 'playwright';
import assert from 'node:assert/strict';
import {cp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';

if(!process.env.CI||!process.env.RUNNER_TEMP)throw Error('Run package update smoke only in isolated CI');
const mac=process.platform==='darwin';
const output=path.resolve(mac?'release/mac-unpacked':'release/windows');
const source=path.join(output,mac?'JobFindsMe.app':'JobFindsMe');
const resources=mac?'Contents/Resources':'resources';
const executable=mac?'Contents/MacOS/JobFindsMe':'JobFindsMe.exe';
const archive=path.join(output,mac?'mac-arm64.zip':'windows-x64.zip');
const root=path.join(process.env.RUNNER_TEMP,'jfm-update-native');await mkdir(root,{recursive:true});
const broken=path.join(root,'broken.zip');
const fixtureContext=JSON.parse(await readFile(path.join(process.env.RUNNER_TEMP,`jfm-${process.platform}-fixture-context.json`),'utf8'));
const result=spawnSync('python',[path.resolve('../../scripts/desktop_update_smoke.py'),archive,broken],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);
async function until(read,accept,timeout=180_000){const deadline=Date.now()+timeout;let last;while(Date.now()<deadline){try{last=await read();if(accept(last))return last;}catch{}await delay(200);}throw Error(`Native update timed out: ${JSON.stringify(last)}`);}
function stopOwned(pid){if(!Number.isSafeInteger(pid)||pid<2)return;if(mac){try{process.kill(-pid,'SIGTERM');}catch{}}else spawnSync('taskkill.exe',['/PID',String(pid),'/T','/F'],{stdio:'ignore'});}
async function readRecord(profile,name){const pointer=JSON.parse(await readFile(path.join(profile,'updates/active.json'),'utf8'));return JSON.parse(await readFile(path.join(profile,'updates',pointer.id,name),'utf8'));}

for(const scenario of ['success','startup-failure']){
 const folder=path.join(root,`${scenario} 安装 with 'quotes'`),installed=path.join(folder,mac?'JobFindsMe.app':'JobFindsMe'),profile=path.join(process.env.RUNNER_TEMP,`jfm-${process.platform}-smoke`);
 await mkdir(folder,{recursive:true});await cp(source,installed,{recursive:true,verbatimSymlinks:true});
 // Keep the fictional profile at its original path, exactly as a real update
 // does. Relocating a copied database invalidates its managed original paths.
 const manifestPath=path.join(installed,resources,'app/package.json');const originalManifest=JSON.parse(await readFile(manifestPath,'utf8'));
 await writeFile(manifestPath,JSON.stringify({...originalManifest,version:'0.0.1',build:'v0.0.1',releaseTag:'v0.0.1'}));
 const zip=scenario==='success'?archive:broken,bytes=await readFile(zip),sha256=createHash('sha256').update(bytes).digest('hex');
 let app,window,closed=false,spawnedPid,guardianPid;
 try{
  app=await electron.launch({executablePath:path.join(installed,executable),args:[`--user-data-dir=${profile}`],timeout:90_000});window=await app.firstWindow();window.setDefaultTimeout(180_000);await window.getByRole('button',{name:'我的简历',exact:true}).waitFor({state:'visible'});
  await window.getByRole('button',{name:'我的简历',exact:true}).click();const editor=window.getByRole('textbox',{name:'简历文档编辑器',exact:true});await editor.waitFor({state:'visible'});
  await editor.locator('p').last().click();await window.keyboard.press('End');await window.keyboard.type(' Kept across native update');
  const before=await window.evaluate(async context=>{
   localStorage.setItem('jfm.update.last-check:v0.15.4',String(Date.now()));
   const bootstrap=await window.jobfindsme.getBootstrap(),workspace=bootstrap.workspaces[0].workspace_id;
   const version=(await window.jobfindsme.listResumeVersions(workspace)).find(row=>row.is_current);
   const original=await window.jobfindsme.resumeSource({workspace_id:workspace,document_id:context.originalDocumentId});
   return {workspace,version:version.version_id,document:context.originalDocumentId,source:original.content_base64,draft:localStorage.getItem(`jfm.resume.document-draft.${workspace}.${version.version_id}`)};
  },fixtureContext);assert.ok(before.draft.includes('Kept across native update'));
  await app.evaluate(async({session})=>{await session.defaultSession.cookies.set({url:'https://example.test',name:'fictional-update-session',value:'kept',expirationDate:Date.now()/1000+3600,secure:true});});
  await app.evaluate(async(_electron,{zip,sha256,size,name,tag})=>{
   const fs=process.getBuiltinModule('fs'),stream=process.getBuiltinModule('stream');const originalFetch=globalThis.fetch;globalThis.updateSlow=true;
   globalThis.fetch=async(url,options)=>{
    if(String(url)==='https://api.github.com/repos/russeell/jobfindsme/releases/latest')return Response.json({tag_name:tag,assets:[{name,size,digest:`sha256:${sha256}`}]});
    if(String(url)===`https://github.com/russeell/jobfindsme/releases/download/${tag}/${name}`){
     const slow=globalThis.updateSlow;const body=stream.Readable.from((async function*(){for await(const chunk of fs.createReadStream(zip,{highWaterMark:64*1024})){if(slow)await new Promise(resolve=>setTimeout(resolve,20));yield chunk;}})());return new Response(stream.Readable.toWeb(body),{headers:{'content-length':String(size)}});
    }
    if(new URL(String(url)).hostname==='127.0.0.1')return originalFetch(url,options);
    throw Error('Unexpected external request in fictional update smoke');
   };
  },{zip,sha256,size:bytes.length,name:mac?'mac-arm64.zip':'windows-x64.zip',tag:`v${originalManifest.version}`});
  await window.evaluate(()=>{window.updateProgress=[];window.jobfindsme.onUpdateState(state=>{if(state.phase==='downloading')window.updateProgress.push(state.received);});});
  await window.getByRole('button',{name:/^设置/}).click();await window.getByRole('button',{name:'版本更新',exact:true}).click();await window.getByRole('button',{name:'检查更新',exact:true}).click();
  await window.getByRole('button',{name:'下载更新',exact:true}).click();await window.getByRole('progressbar',{name:'更新下载进度'}).waitFor({state:'visible'});
  await window.getByRole('button',{name:'岗位来源',exact:true}).click();await window.getByRole('button',{name:'版本更新',exact:true}).click();await window.getByRole('progressbar',{name:'更新下载进度'}).waitFor({state:'visible'});
  await window.getByRole('button',{name:'取消下载',exact:true}).click();await window.getByText('下载已取消，当前程序未更改。',{exact:true}).waitFor();
  assert.equal(JSON.parse(await readFile(manifestPath,'utf8')).version,'0.0.1');
  console.log(`${process.platform}/${scenario}: real progress, navigation and cancellation passed`);
  await app.evaluate(()=>{globalThis.updateSlow=false;});
  await window.getByRole('button',{name:'重新下载',exact:true}).click();await window.getByRole('button',{name:'重启并安装',exact:true}).waitFor({state:'visible'});
  const progress=await window.evaluate(()=>window.updateProgress);assert.ok(progress.length>1);assert.ok(progress.at(-1)===bytes.length);
  const request=await readRecord(profile,'request.json');const state=await readRecord(profile,'state.json');assert.equal(state.phase,'ready');
  console.log(`${process.platform}/${scenario}: actual ZIP and copied frozen runtime prepared`);
  const close=new Promise(resolve=>app.once('close',()=>{closed=true;resolve();}));
  await window.getByRole('button',{name:'重启并安装',exact:true}).click();
  const installing=window.getByRole('dialog',{name:'正在准备重启更新',exact:true});await installing.waitFor({state:'visible'});await window.keyboard.press('Escape');assert.equal(await installing.evaluate(node=>node.open),true);await close;
  const completed=await until(()=>readRecord(profile,'state.json'),state=>['installed','rolled_back'].includes(state.phase));
  console.log(`${process.platform}/${scenario}: guardian outcome ${completed.phase}`);
  guardianPid=completed.guardian_pid;spawnedPid=scenario==='success'?(await readRecord(profile,'health.json')).pid:completed.pid;
  assert.equal(completed.phase,scenario==='success'?'installed':'rolled_back');
  assert.equal(JSON.parse(await readFile(manifestPath,'utf8')).version,scenario==='success'?originalManifest.version:'0.0.1');
  assert.ok(spawnedPid>1);
  stopOwned(spawnedPid);await delay(4000);spawnedPid=undefined;
  // Inspect a fresh native launch of whichever program the guardian selected.
  app=await electron.launch({executablePath:path.join(installed,executable),args:[`--user-data-dir=${profile}`],timeout:90_000});closed=false;
  window=await app.firstWindow();window.setDefaultTimeout(90_000);await window.getByRole('button',{name:'我的简历',exact:true}).click();await window.getByRole('textbox',{name:'简历文档编辑器',exact:true}).waitFor();
  assert.ok((await window.getByRole('textbox',{name:'简历文档编辑器',exact:true}).textContent()).includes('Kept across native update'));
  const after=await window.evaluate(async before=>({draft:localStorage.getItem(`jfm.resume.document-draft.${before.workspace}.${before.version}`),source:(await window.jobfindsme.resumeSource({workspace_id:before.workspace,document_id:before.document})).content_base64}),before);
  assert.equal(after.source,before.source);assert.equal(after.draft,before.draft);
  const cookies=await app.evaluate(({session})=>session.defaultSession.cookies.get({url:'https://example.test'}));assert.equal(cookies.find(cookie=>cookie.name==='fictional-update-session')?.value,'kept');
  await window.getByRole('button',{name:/^设置/}).click();await window.getByRole('button',{name:'版本更新',exact:true}).click();
  await window.getByText(scenario==='success'?'更新成功，本地资料与登录会话已保留。':'新版启动失败，已恢复旧程序。本地资料仍保留，可重新下载或手动安装。',{exact:true}).waitFor();
  console.log(`${process.platform}: real packaged update ${scenario}, cancel/progress/restart, resume bytes/draft/cookie preserved`);
 }finally{
  if(app&&!closed)await app.close().catch(()=>{});stopOwned(spawnedPid);stopOwned(guardianPid);
  await rm(folder,{recursive:true,force:true,maxRetries:10,retryDelay:500});
 }
}
