import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,existsSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {copyRuntimeDependencies} from '../scripts/runtime-dependencies.mjs';
test('runtime closure preserves nested versions and licenses, excludes build packages',()=>{
 const root=mkdtempSync(path.join(tmpdir(),'jfm-deps-'));
 function pkg(relative,data){const dir=path.join(root,'node_modules',relative);mkdirSync(dir,{recursive:true});writeFileSync(path.join(dir,'package.json'),JSON.stringify(data));writeFileSync(path.join(dir,'LICENSE.txt'),'license');}
 try{
  pkg('agent',{dependencies:{sdk:'1'},optionalDependencies:{absent:'1'}});pkg('agent/node_modules/sdk',{version:'1'});pkg('sdk',{version:'2'});pkg('vite',{});
  const out=path.join(root,'out');assert.equal(copyRuntimeDependencies(root,out,['agent']),2);
  assert.equal(existsSync(path.join(out,'agent/node_modules/sdk/package.json')),true);assert.equal(existsSync(path.join(out,'agent/LICENSE.txt')),true);
  assert.equal(existsSync(path.join(out,'vite')),false);assert.equal(existsSync(path.join(out,'sdk')),false);
  assert.throws(()=>copyRuntimeDependencies(root,out,['missing']),/Missing runtime/);
 }finally{rmSync(root,{recursive:true,force:true});}
});
