import {_electron as electron} from 'playwright';
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdirSync,readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
const mac=process.platform==='darwin';
const output=path.resolve(mac?'release/mac-unpacked':'release/windows');
const executablePath=path.join(output,mac?'JobFindsMe.app/Contents/MacOS/JobFindsMe':'JobFindsMe/JobFindsMe.exe');
const profile=path.join(process.env.RUNNER_TEMP,`jfm-${process.platform}-smoke`);
mkdirSync(profile,{recursive:true});
const resumeFolder=path.join(process.env.RUNNER_TEMP,`jfm-${process.platform}-resume`);
const fixtureScript=path.resolve('../../scripts/desktop_resume_smoke.py');
function fixture(command){
 const result=spawnSync('python',[fixtureScript,command,resumeFolder],{encoding:'utf8'});
 assert.equal(result.status,0,`${result.stdout}\n${result.stderr}`);
 console.log(result.stdout);
}
fixture('create');
let workspaceId,savedResumeId,originalSource;
async function checkEditor(window){
 const editor=window.getByRole('textbox',{name:'简历文档编辑器',exact:true});
 await editor.waitFor({state:'visible'});
 const name=editor.locator('span').filter({hasText:'Example Candidate'}).first();
 assert.equal(await name.evaluate(node=>getComputedStyle(node).color),'rgb(26, 51, 76)');
 assert.equal(await name.evaluate(node=>getComputedStyle(node).fontSize),'32px');
 assert.ok(await editor.textContent());
 return editor;
}
async function exportFiles(app,window,prefix){
 for(const [format,label] of [['docx','Word · 继续编辑'],['pdf','PDF · 用于投递']]){
  await app.evaluate(({dialog},filePath)=>{
   dialog.showSaveDialog=async()=>({canceled:false,filePath});
  },path.join(resumeFolder,`${prefix}.${format}`));
  await window.getByRole('button',{name:'导出简历',exact:true}).click();
  await window.getByRole('button',{name:label,exact:true}).click();
  await window.getByText(format==='docx'?'已导出可继续编辑的 Word 文档。':'已导出 PDF。',{exact:true}).waitFor({state:'visible'});
 }
}
for(let attempt=0;attempt<2;attempt++){
 const app=await electron.launch({executablePath,args:[`--user-data-dir=${profile}`],env:{...process.env,JFM_QA_DIAGNOSTICS:'1'},timeout:90000});
 app.process().stderr.on('data',chunk=>process.stderr.write(chunk));
 try{
  const window=await app.firstWindow({timeout:90000});
  await window.waitForFunction(()=>!!window.jobfindsme,{timeout:30000});
  let data,lastError;
  const deadline=Date.now()+75000;
  while(Date.now()<deadline){
   try{
    data=await window.evaluate(async()=>JSON.parse(JSON.stringify(await window.jobfindsme.getBootstrap())));
    if(Array.isArray(data?.workspaces)&&Array.isArray(data?.sources))break;
    throw Error(`Invalid bootstrap response: ${JSON.stringify(data)}`);
   }catch(error){lastError=error;}
   await delay(500);
  }
  assert.ok(data?.workspaces,`Backend never became ready: ${lastError}`);
  assert.ok(data.workspaces.length>0);assert.equal(data.sources.length,4);
  if(attempt===0)workspaceId=data.workspaces[0].workspace_id;
  else assert.equal(data.workspaces[0].workspace_id,workspaceId,'Workspace must survive restart');
  // Exercise pin persistence in the actual packaged renderer and SQLite bridge.
  if(attempt===0){
   await window.evaluate(async workspace=>{
    for(const [id,title,date] of [['pin-old','置顶测试旧对话','2026-01-01T00:00:00Z'],['pin-new','置顶测试新对话','2026-01-02T00:00:00Z']]){
     await window.jobfindsme.saveResearchChat({workspace_id:workspace,id,chat_title:title,updated_at:date,turns:[{role:'user',text:title},{role:'assistant',text:'Synthetic packaging test.'}],report_ids:[]});
    }
   },workspaceId);
   await window.reload();
   const pin=window.getByRole('button',{name:'置顶聊天：置顶测试旧对话',exact:true});
   await pin.waitFor({state:'visible'});
   await window.getByRole('button',{name:'置顶测试旧对话',exact:true}).hover();
   await pin.click();
  }
  const pinned=window.getByRole('button',{name:'取消置顶：置顶测试旧对话',exact:true});
  await pinned.waitFor({state:'visible'});
  assert.equal(await pinned.getAttribute('aria-pressed'),'true');
  assert.equal(await window.locator('.research-history-item').first().textContent(),'置顶测试旧对话');
  if(attempt===1){
   await pinned.click();
   await window.getByRole('button',{name:'置顶聊天：置顶测试旧对话',exact:true}).waitFor({state:'visible'});
   assert.equal(await window.locator('.research-history-item').first().textContent(),'置顶测试新对话');
  }
  for(const page of ['岗位管理','我的简历','求职助手','找工作']){
   await window.getByRole('button',{name:page,exact:true}).click();
   await window.getByRole('button',{name:page,exact:true}).waitFor({state:'visible'});
   assert.equal(await window.getByText('本地服务暂时异常',{exact:false}).count(),0);
  }
  await window.getByRole('button',{name:'我的简历',exact:true}).click();
  if(attempt===0){
   // Substitute only native file picker results; all product IPC and the frozen
   // Python service run unchanged, with fictional input in an isolated profile.
   await app.evaluate(({dialog},filePath)=>{
    dialog.showOpenDialog=async()=>({canceled:false,filePaths:[filePath]});
   },path.join(resumeFolder,'fictional.pdf'));
   await window.getByRole('button',{name:'选择简历文件',exact:true}).click();
   await window.getByRole('button',{name:'编辑副本',exact:true}).waitFor({state:'visible'});
   await window.waitForFunction(()=>document.querySelector('.resume-pdf-page canvas')?.width>400);
   originalSource=await window.evaluate(async workspace=>{
    const versions=await window.jobfindsme.listResumeVersions(workspace);
    const current=versions.find(row=>row.is_current);
    const source=await window.jobfindsme.resumeSource({workspace_id:workspace,document_id:current.source_document_id});
    return {...source,document_id:current.source_document_id};
   },workspaceId);
   assert.deepEqual(Buffer.from(originalSource.content_base64,'base64'),readFileSync(path.join(resumeFolder,'fictional.pdf')));
   await window.getByRole('button',{name:'编辑副本',exact:true}).click();
   const editor=await checkEditor(window);
   await editor.click();
   await editor.press(mac?'Meta+End':'Control+End');
   await editor.press('End');
   await window.keyboard.type(' Packaged edit');
   await window.getByRole('button',{name:'保存',exact:true}).click();
   await window.getByText('修改已保存。',{exact:true}).waitFor({state:'visible'});
   savedResumeId=await window.evaluate(async workspace=>(await window.jobfindsme.listResumeVersions(workspace)).find(row=>row.is_current).version_id,workspaceId);
   await exportFiles(app,window,'export');
   fixture('verify');
   // Also exercise Word parsing in the frozen runtime, then restore the edited
   // PDF copy so that restart checks cover the saved document and its styles.
   await app.evaluate(({dialog},filePath)=>{
    dialog.showOpenDialog=async()=>({canceled:false,filePaths:[filePath]});
   },path.join(resumeFolder,'fictional.docx'));
   await window.evaluate(()=>window.jobfindsme.chooseAndImportResume());
   const wordVersion=await window.evaluate(async workspace=>(await window.jobfindsme.listResumeVersions(workspace)).find(row=>row.is_current),workspaceId);
   assert.ok(JSON.stringify(wordVersion.document).includes('#17324d'));
   assert.ok(JSON.stringify(wordVersion.document).includes('#0f766e'));
   const restored=await window.evaluate(async({workspace,id})=>window.jobfindsme.restoreResumeVersion(workspace,id),{workspace:workspaceId,id:savedResumeId});
   assert.notEqual(restored.version_id,savedResumeId,'Restoring history creates a new version without rewriting the old one');
   assert.ok(JSON.stringify(restored.document).includes('Packaged edit'));
   savedResumeId=restored.version_id;
   await window.reload();
   await window.getByRole('button',{name:'我的简历',exact:true}).click();
  }
  const editor=await checkEditor(window);
  assert.ok((await editor.textContent()).includes('Packaged edit'),'Saved edit must survive restart');
  for(const name of ['编辑历史','文字样式','段落排版']){
   assert.ok(await window.getByRole('group',{name,exact:true}).isVisible(),`Missing new toolbar group: ${name}`);
  }
  if(attempt===0){
   // Select actual styled text, clear only its formatting, then undo once.
   const before=await editor.innerHTML();
   await editor.locator('span').filter({hasText:'Example Candidate'}).first().evaluate(node=>{
    const range=document.createRange();range.selectNodeContents(node);
    const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
    node.closest('[contenteditable]').focus();
   });
   await window.getByRole('button',{name:'清除格式',exact:true}).click();
   assert.notEqual(await editor.innerHTML(),before,'Clear formatting must change selected styles');
   assert.ok((await editor.textContent()).includes('Example Candidate'),'Clear formatting must retain text');
   await window.getByRole('button',{name:'撤销',exact:true}).click();
   assert.equal(await editor.innerHTML(),before,'One undo must restore formatting');
   await checkEditor(window);
   await window.getByRole('button',{name:'简历助手',exact:true}).click();
   await window.locator('aside.resume-editor-assistant').waitFor({state:'visible'});
   await window.getByRole('button',{name:'关闭简历助手',exact:true}).click();
   await window.getByRole('button',{name:'专注编辑',exact:true}).click();
   await window.getByRole('dialog',{name:'专注简历编辑',exact:true}).waitFor({state:'visible'});
   assert.equal(await window.getByRole('button',{name:'找工作',exact:true,includeHidden:true}).evaluate(node=>!!node.closest('[inert]')),true,'Focus mode must isolate background navigation');
   await window.screenshot({path:path.join(output,'smoke-focus.png')});
   await editor.press('Escape');
   await window.getByRole('dialog',{name:'专注简历编辑',exact:true}).waitFor({state:'detached'});
   await editor.click();
   await editor.press(mac?'Meta+End':'Control+End');
   await editor.press('End');
   await window.keyboard.type(' Recovered draft');
   await window.getByText('草稿已存本机',{exact:true}).waitFor({state:'visible'});
   await window.waitForFunction(({workspace,id})=>localStorage.getItem(`jfm.resume.document-draft.${workspace}.${id}`)?.includes('Recovered draft'),{workspace:workspaceId,id:savedResumeId});
   const saved=await window.evaluate(async workspace=>(await window.jobfindsme.listResumeVersions(workspace)).find(row=>row.is_current),workspaceId);
   assert.equal(saved.version_id,savedResumeId);
   assert.ok(!JSON.stringify(saved.document).includes('Recovered draft'),'Unsaved draft must not overwrite saved version');
  }else{
   await window.getByText('已恢复本机未保存的草稿。',{exact:true}).waitFor({state:'visible'});
   assert.ok((await editor.textContent()).includes('Recovered draft'),'Unsaved draft must survive actual app restart');
   const saved=await window.evaluate(async workspace=>(await window.jobfindsme.listResumeVersions(workspace)).find(row=>row.is_current),workspaceId);
   assert.equal(saved.version_id,savedResumeId,'Draft recovery must not silently save a version');
   await editor.click();
   await editor.press(mac?'Meta+s':'Control+s');
   await window.getByText('修改已保存。',{exact:true}).waitFor({state:'visible'});
   await window.waitForFunction(()=>document.querySelector('[aria-label="简历文档编辑器"]').contains(document.activeElement));
   const recovered=await window.evaluate(async workspace=>(await window.jobfindsme.listResumeVersions(workspace)).find(row=>row.is_current),workspaceId);
   assert.notEqual(recovered.version_id,savedResumeId);
   assert.ok(JSON.stringify(recovered.document).includes('Recovered draft'));
   assert.equal(await window.evaluate(({workspace,id})=>localStorage.getItem(`jfm.resume.document-draft.${workspace}.${id}`),{workspace:workspaceId,id:savedResumeId}),null,'Saved draft cache must be removed');
   await exportFiles(app,window,'recovered');
   fixture('verify-draft');
   await window.getByRole('button',{name:'分页预览',exact:true}).click();
   await window.waitForFunction(()=>document.querySelector('.resume-pdf-page canvas')?.width>400);
   await window.getByRole('button',{name:'编辑',exact:true}).click();
   await checkEditor(window);
  }
  const source=await window.evaluate(input=>window.jobfindsme.resumeSource(input),{workspace_id:workspaceId,document_id:originalSource.document_id});
  assert.equal(source.content_base64,originalSource.content_base64,'Original must remain unchanged');
  await window.screenshot({path:path.join(output,`smoke-${attempt}.png`)});
  console.log(`Packaged ${process.platform} UI + IPC + frozen Python + SQLite + styled resume + draft recovery passed (${attempt+1}/2)`);
 }finally{await app.close();}
}
