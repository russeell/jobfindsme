import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const projectRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
export function sourceDigest(root,kind){
 const spec=JSON.parse(readFileSync(path.join(root,'scripts/desktop-build-inputs.json'),'utf8'))[kind];
 const files=new Set(spec.files);
 function walk(directory){
  for(const entry of readdirSync(path.join(root,directory),{withFileTypes:true})){
   const relative=`${directory}/${entry.name}`;
   if(entry.isDirectory())walk(relative);
   else if(entry.isFile()&&spec.extensions.includes(path.extname(relative)))files.add(relative);
  }
 }
 for(const directory of spec.directories)walk(directory);
 const hash=createHash('sha256');
 for(const file of [...files].sort()){hash.update(file+'\0');hash.update(readFileSync(path.join(root,file)));hash.update('\0');}
 return hash.digest('hex');
}
export function assertProvenance(record,expected){
 if(!record||Object.entries(expected).some(([key,value])=>record[key]!==value))throw Error('Build inputs or dependencies changed; rebuild desktop and frozen API before packaging');
}
export function packageProvenance(desktopRoot,pythonRoot){
 const root=path.resolve(desktopRoot,'../..');
 const version=JSON.parse(readFileSync(path.join(desktopRoot,'package.json'),'utf8')).version;
 const pythonVersion=readFileSync(path.join(root,'pyproject.toml'),'utf8').match(/^version\s*=\s*"([^"]+)"/m)?.[1];
 if(version!==pythonVersion)throw Error('Desktop and Python versions must match');
 if(process.env.GITHUB_REF_TYPE==='tag'&&process.env.GITHUB_REF_NAME!==`v${version}`)throw Error('Version tag must match the packaged version');
 const specs=JSON.parse(readFileSync(path.join(root,'scripts/desktop-build-inputs.json'),'utf8'));
 const inputs=[...new Set(Object.values(specs).flatMap(spec=>[...spec.directories,...spec.files]))];
 if(execFileSync('git',['status','--porcelain','--untracked-files=all','--',...inputs],{cwd:root,encoding:'utf8'}).trim())throw Error('Commit production inputs before packaging so sourceCommit identifies the actual code');
 const sourceCommit=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
 const dependencyLocks={desktop:sha256(readFileSync(path.join(desktopRoot,'package-lock.json'))),python:sha256(readFileSync(path.join(root,'requirements/release.txt')))};
 const sourceInputs={desktop:sourceDigest(root,'desktop'),python:sourceDigest(root,'python')};
 for(const [kind,directory] of [['desktop',path.join(desktopRoot,'dist-electron')],['python',pythonRoot]]){
  assertProvenance(JSON.parse(readFileSync(path.join(directory,'build-provenance.json'),'utf8')),{sourceCommit,sourceDigest:sourceInputs[kind],dependencyLock:dependencyLocks[kind]});
 }
 return {dependencyLocks,sourceInputs};
}
if(path.resolve(process.argv[1]||'')===fileURLToPath(import.meta.url)&&process.argv[2]==='--record'){
 const desktopRoot=path.join(projectRoot,'apps/desktop');
 writeFileSync(path.join(desktopRoot,'dist-electron/build-provenance.json'),JSON.stringify({sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:projectRoot,encoding:'utf8'}).trim(),sourceDigest:sourceDigest(projectRoot,'desktop'),dependencyLock:sha256(readFileSync(path.join(desktopRoot,'package-lock.json')))},null,2)+'\n');
}
