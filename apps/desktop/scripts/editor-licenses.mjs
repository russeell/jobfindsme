import {readFileSync,existsSync,writeFileSync} from 'node:fs';
import path from 'node:path';
export function writeEditorLicenses(desktopRoot,destination){
 const visited=new Set(),notices=[];
 function visit(name){
  if(visited.has(name))return;visited.add(name);
  // React already belongs to the application; these are editor dependencies.
  const directory=path.join(desktopRoot,'node_modules',name);
  const manifest=JSON.parse(readFileSync(path.join(directory,'package.json'),'utf8'));
  const license=['LICENSE','LICENSE.md','LICENSE.txt','license','license.md'].map(file=>path.join(directory,file)).find(existsSync);
  if(!license)throw Error(`Missing license for editor dependency: ${name}`);
  notices.push(`${name} ${manifest.version}\n${readFileSync(license,'utf8')}`);
  for(const dependency of Object.keys(manifest.dependencies||{}))visit(dependency);
 }
 for(const name of ['@tiptap/core','@tiptap/react','@tiptap/starter-kit','@tiptap/pm'])visit(name);
 writeFileSync(destination,notices.join('\n\n--------------------\n\n'));
}
