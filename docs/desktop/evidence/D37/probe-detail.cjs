const {app,BrowserWindow}=require('electron'),fs=require('fs');
const root='/Users/russeell/Documents/开源项目开发/jobfindsme',out='/private/tmp/jfm-d37-public-evidence';
app.setPath('userData','/private/tmp/jfm-d37-detail-'+Date.now());
const {SourceBrowserManager}=require(root+'/apps/desktop/dist-electron/main/source-browser.js');
app.whenReady().then(async()=>{const w=new BrowserWindow({show:false}),m=new SourceBrowserManager(w);
for(const id of ['company_13','company_09','company_11']){const d=JSON.parse(fs.readFileSync(out+'/'+id+'.json')),v=m.backgroundView(id);try{await Promise.race([v.webContents.loadURL(d.samples[0].url),new Promise((_,r)=>setTimeout(()=>r(Error('timeout')),12000))]);await new Promise(r=>setTimeout(r,2500));const raw=await v.webContents.executeJavaScript(`({text:document.body.innerText.slice(0,20000),html:document.body.outerHTML.slice(0,200000)})`);fs.writeFileSync(out+'/'+id+'-detail-dom.json',JSON.stringify(raw));console.log(id,raw.text.slice(0,150));}catch(e){console.log(id,String(e));}}
m.destroy();w.destroy();app.quit();});
