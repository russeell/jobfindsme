const {app,BrowserWindow}=require('electron'),fs=require('fs');
const root='/Users/russeell/Documents/开源项目开发/jobfindsme',out='/private/tmp/jfm-d37-public-evidence';
app.setPath('userData','/private/tmp/jfm-d37-navigation-'+Date.now());
const {SourceBrowserManager}=require(root+'/apps/desktop/dist-electron/main/source-browser.js');
const {sourceBrowserSpecs}=require(root+'/apps/desktop/dist-electron/main/source-browser-policy.js');
app.whenReady().then(async()=>{const w=new BrowserWindow({show:false}),m=new SourceBrowserManager(w);
for(const id of ['company_13']){const v=m.backgroundView(id),events=[];v.webContents.on('will-redirect',(_e,url)=>events.push({redirect:url}));v.webContents.session.webRequest.onCompleted((d)=>{if(d.resourceType==='xhr'){const u=new URL(d.url);events.push({endpoint:u.origin+u.pathname,status:d.statusCode});}});
try{let url=sourceBrowserSpecs[id].loginUrl;if(id==='company_04')url='https://career.meituan.com/web/social';if(id==='company_13')url=JSON.parse(fs.readFileSync(out+'/'+id+'.json')).samples[0].url;
await Promise.race([v.webContents.loadURL(url),new Promise((_,r)=>setTimeout(()=>r(Error('timeout')),12000))]).catch(()=>{});await new Promise(r=>setTimeout(r,4000));const raw=await Promise.race([v.webContents.executeJavaScript(`(()=>{const c=document.body.cloneNode(true);c.querySelectorAll('svg,script,style').forEach(x=>x.remove());return {text:document.body.innerText.slice(0,20000),html:c.outerHTML.slice(0,180000)}})()`),new Promise((_,r)=>setTimeout(()=>r(Error('DOM timeout')),5000))]);fs.writeFileSync(out+'/'+id+'-navigation.json',JSON.stringify({...raw,events}));console.log(id,raw.text.slice(0,80),JSON.stringify(events).slice(0,2000));}catch(e){console.log(id,String(e));}}
m.destroy();w.destroy();app.quit();});
