// Real source smoke test: production Electron collector, fresh isolated profile.
// No fixtures, credentials, application submissions, or user's running profile.
const {app,BrowserWindow}=require('electron');
const path=require('path'),fs=require('fs');
const root='/Users/russeell/Documents/开源项目开发/jobfindsme';
app.setPath('userData',process.env.JFM_SMOKE_PROFILE||'/private/tmp/jfm-d37-public-'+Date.now());
const {SourceBrowserManager}=require(root+'/apps/desktop/dist-electron/main/source-browser.js');
const {sourceBrowserSpecs}=require(root+'/apps/desktop/dist-electron/main/source-browser-policy.js');
const out=process.env.JFM_SMOKE_OUTPUT||'/private/tmp/jfm-d37-public-evidence';fs.mkdirSync(out,{recursive:true});
app.whenReady().then(async()=>{
 const win=new BrowserWindow({show:false,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}}),manager=new SourceBrowserManager(win);
 const ids=(process.env.JFM_SMOKE_SOURCES||Object.keys(sourceBrowserSpecs).filter(x=>x.startsWith('company_')&&x!=='company_12').join(',')).split(',');
 for(const id of ids){
  const started=Date.now();let evidence={source:id,date:new Date().toISOString(),path:'production Electron WebContentsView DOM',profile:'fresh isolated, no user login'};
  try{
   const r=await manager.collectCareer(id,{keyword:process.env.JFM_SMOKE_KEYWORD||'工程师',city:process.env.JFM_SMOKE_CITY||'',maxPages:2,seconds:Number(process.env.JFM_SMOKE_SECONDS||18)});
   evidence.count=r.records.length;evidence.collection=r.collection;evidence.samples=r.records.slice(0,2).map(x=>({id:x.external_id,title:x.payload.title,url:x.payload.url,location:x.payload.location}));
   if(r.records[0])try{const d=await manager.readResearchJob(id,r.records[0].payload.url);evidence.detail={title:d.title,url:d.url,chars:d.description.length};}catch(e){evidence.detailError=String(e);const dv=manager.backgroundView(id);await Promise.race([dv.webContents.loadURL(r.records[0].payload.url),new Promise((_,reject)=>setTimeout(()=>reject(Error('detail diagnostic timeout')),10000))]).catch(()=>{});}
  }catch(e){evidence.error=String(e);}
  const v=manager.backgroundView(id);evidence.finalUrl=v.webContents.getURL();
  try {const diagnostic=await Promise.race([v.webContents.executeJavaScript(`({text:(document.body?.innerText||'').slice(0,16000),links:Array.from(document.querySelectorAll('a[href]')).slice(0,100).map(a=>({text:a.innerText,url:a.href})),html:(document.querySelector('main')||document.body)?.outerHTML.slice(0,250000)})`),new Promise((_,reject)=>setTimeout(()=>reject(Error('diagnostic timeout')),3000))]);fs.writeFileSync(path.join(out,id+'-dom.json'),JSON.stringify(diagnostic,null,2));}catch{}
  evidence.elapsed=(Date.now()-started)/1000;fs.writeFileSync(path.join(out,id+'.json'),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));
 }
 manager.destroy();win.destroy();app.quit();
}).catch(e=>{console.error(e);app.exit(1);});
