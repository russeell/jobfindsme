import {_electron as electron} from 'playwright';
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdirSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';
const mac=process.platform==='darwin';
const output=path.resolve(mac?'release/mac-unpacked':'release/windows');
const executablePath=path.join(output,mac?'JobFindsMe.app/Contents/MacOS/JobFindsMe':'JobFindsMe/JobFindsMe.exe');
const profile=path.join(process.env.RUNNER_TEMP,`jfm-${process.platform}-smoke`);
mkdirSync(profile,{recursive:true});
let workspaceId;
for(let attempt=0;attempt<2;attempt++){
 const app=await electron.launch({executablePath,args:[`--user-data-dir=${profile}`],timeout:90000});
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
  await window.screenshot({path:path.join(output,`smoke-${attempt}.png`)});
  console.log(`Packaged ${process.platform} UI + IPC + Python + SQLite bootstrap passed (${attempt+1}/2)`);
 }finally{await app.close();}
}
