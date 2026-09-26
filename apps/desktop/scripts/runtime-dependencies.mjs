import {cpSync,existsSync,mkdirSync,readFileSync} from 'node:fs';
import path from 'node:path';

// Resolve from each installed package, preserving nested versions and lockfile layout.
export function copyRuntimeDependencies(desktopRoot,destination,roots){
 const modules=path.join(desktopRoot,'node_modules'),visited=new Set();
 function resolve(name,from){
  let cursor=from;
  while(cursor.startsWith(desktopRoot)){
   const candidate=path.join(cursor,'node_modules',name);
   if(existsSync(path.join(candidate,'package.json')))return candidate;
   const parent=path.dirname(cursor);if(parent===cursor)break;cursor=parent;
  }
 }
 function visit(name,from,optional=false){
  const source=resolve(name,from);
  if(!source){if(optional)return;throw Error(`Missing runtime dependency: ${name}`);}
  if(visited.has(source))return;visited.add(source);
  const manifest=JSON.parse(readFileSync(path.join(source,'package.json'),'utf8'));
  const target=path.join(destination,path.relative(modules,source));mkdirSync(path.dirname(target),{recursive:true});
  cpSync(source,target,{recursive:true,verbatimSymlinks:true,filter:file=>{
   const relative=path.relative(source,file);
   if(relative.split(path.sep).some(part=>['node_modules','test','tests','docs'].includes(part)))return false;
   if(/^(license|licence|copying|notice)([.-]|$)/i.test(path.basename(file)))return true;
   return !/\.(?:map|md|ts|mts|cts)$/i.test(file);
  }});
  for(const dep of Object.keys(manifest.dependencies??{}))visit(dep,source,dep in (manifest.optionalDependencies??{}));
  for(const dep of Object.keys(manifest.optionalDependencies??{}))visit(dep,source,true);
  for(const dep of Object.keys(manifest.peerDependencies??{}))visit(dep,source,manifest.peerDependenciesMeta?.[dep]?.optional===true);
 }
 for(const name of roots)visit(name,desktopRoot);
 return visited.size;
}
