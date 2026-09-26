import {_electron as electron} from 'playwright';
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdirSync} from 'node:fs';
const executablePath=path.resolve('release/windows/JobFindsMe/JobFindsMe.exe');
const profile=path.join(process.env.RUNNER_TEMP,'jfm-windows-smoke');
mkdirSync(profile,{recursive:true});
for(let attempt=0;attempt<2;attempt++){
 const app=await electron.launch({executablePath,args:[`--user-data-dir=${profile}`],timeout:90000});
 try{
  const window=await app.firstWindow({timeout:90000});
  await window.waitForFunction(()=>!!window.jobfindsme,{timeout:30000});
  const data=await window.evaluate(()=>window.jobfindsme.getBootstrap());
  assert.ok(data.workspaces.length>0);assert.equal(data.sources.length,20);
  await window.screenshot({path:`release/windows/smoke-${attempt}.png`});
  console.log(`Packaged Windows UI + IPC + Python + SQLite bootstrap passed (${attempt+1}/2)`);
 }finally{await app.close();}
}
