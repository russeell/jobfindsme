// Native Electron regression checks. In-memory pages are fixtures, not live evidence.
const {app,BrowserWindow,session}=require('electron');
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'../../../..');
app.setPath('userData','/private/tmp/jfm-d38-contracts-'+Date.now());
const {SourceBrowserManager}=require(root+'/apps/desktop/dist-electron/main/source-browser.js');
const {sourceListExtractionScript}=require(root+'/apps/desktop/dist-electron/main/source-actions.js');
const {researchExtractionScript}=require(root+'/apps/desktop/dist-electron/main/research-extraction.js');
app.whenReady().then(async()=>{
 const s=session.fromPartition('persist:jobfindsme-source-wuyou');
 const html=`<div class="joblist-item"><div class="joblist-item-job"><span class="jname" onclick="const child=window.open('_blank');child.location.href='https://jobs.51job.com/shanghai/173000001.html';">工程师</span><div class="joblist-item-jobinfo"><span class="sal">2-3万</span><div class="area">上海</div></div></div><span class="cname">示例公司</span><a href="https://jobs.51job.com/all/co123.html">公司</a><button onclick="window.applied=true">投递</button></div><div class="el-pagination"><button class="btn-next">下一页</button></div>`;
 await s.protocol.handle('https',()=>new Response(html,{headers:{'content-type':'text/html; charset=utf-8'}}));
 const w=new BrowserWindow({show:false}),m=new SourceBrowserManager(w),bounds={x:0,y:0,width:900,height:700};
 try{
  await m.show('wuyou',bounds,'https://we.51job.com/pc/search');
  const wc=m.tabs[0].view.webContents;
  const raw=await wc.executeJavaScript(sourceListExtractionScript('wuyou'));
  assert.equal(raw.jobs.length,1);assert.equal(raw.jobs[0].url,'https://jobs.51job.com/shanghai/173000001.html');assert.equal(raw.jobs[0].company,'示例公司');assert.equal(raw.jobs[0].location,'上海');assert.equal(raw.hasNext,true);
  assert.equal(await wc.executeJavaScript('!!window.applied'),false);assert.equal(m.state().tabs.length,1);
  await wc.executeJavaScript(`document.querySelector('.jname').click()`);
  const deadline=Date.now()+5000;
  while(Date.now()<deadline&&m.state().url!=='https://jobs.51job.com/shanghai/173000001.html')await new Promise(r=>setTimeout(r,50));
  assert.equal(m.state().url,'https://jobs.51job.com/shanghai/173000001.html');assert.equal(m.state().tabs.length,2);
  console.log('PASS native WindowProxy redirect; 51job title destination, fields, next control; no application click');
 }finally{m.destroy();w.destroy();await s.protocol.unhandle('https');}
 app.quit();
}).catch(e=>{console.error(e);app.exit(1);});
