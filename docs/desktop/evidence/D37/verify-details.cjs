const {app,BrowserWindow}=require('electron'),fs=require('fs');
const root='/Users/russeell/Documents/开源项目开发/jobfindsme',out=process.env.JFM_SMOKE_OUTPUT||'/private/tmp/jfm-d37-public-evidence';
app.setPath('userData','/private/tmp/jfm-d37-detail-check-'+Date.now());
const {SourceBrowserManager}=require(root+'/apps/desktop/dist-electron/main/source-browser.js');
app.whenReady().then(async()=>{const w=new BrowserWindow({show:false}),m=new SourceBrowserManager(w);
for(const id of (process.env.JFM_SMOKE_SOURCES||'company_04').split(',')){const e=JSON.parse(fs.readFileSync(out+'/'+id+'.json'));try{const d=await m.readResearchJob(id,e.samples[0].url);e.detail={title:d.title,url:d.url,chars:d.description.length};delete e.detailError;e.detailCheckedAt=new Date().toISOString();fs.writeFileSync(out+'/'+id+'.json',JSON.stringify(e,null,2));console.log(JSON.stringify(e.detail));}catch(error){console.log(id,String(error));}}
m.destroy();w.destroy();app.quit();});
