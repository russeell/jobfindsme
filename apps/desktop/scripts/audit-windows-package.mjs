import {existsSync,readdirSync,lstatSync} from 'node:fs';
import path from 'node:path';
const root=path.resolve('release/windows/JobFindsMe');
for(const required of ['JobFindsMe.exe','resources/python/jobfindsme-api/jobfindsme-api.exe','resources/app/dist/index.html','resources/app/dist-electron/main/index.js','resources/app/node_modules/@earendil-works/pi-agent-core/dist/index.js','resources/third-party/PI_LICENSE.txt']){
 if(!existsSync(path.join(root,required)))throw Error(`Missing ${required}`);
}
function visit(directory){
 for(const name of readdirSync(directory)){
  const file=path.join(directory,name);
  if(/\.(?:db|sqlite|sqlite3)(?:-wal|-shm)?$|^\.env(?:\.|$)|^(?:Cookies|Local Storage|Session Storage)$/i.test(name))throw Error(`Private data in package: ${name}`);
  if(lstatSync(file).isDirectory())visit(file);
 }
}
visit(root);console.log('Windows package audit passed');
