import test from 'node:test';
import assert from 'node:assert/strict';
import {writeFile,access,stat} from 'node:fs/promises';
import path from 'node:path';
import {createResumePreview} from '../dist-electron/main/resume-preview.js';
const input={workspace_id:'synthetic',version_id:'v1',template:'campus'};
test('preview uses the export pipeline and removes its private file',async()=>{
 let destination;
 const bytes=await createResumePreview(input,async(value,file)=>{
  destination=file;assert.deepEqual(value,{...input,format:'pdf'});
  // Windows uses the user-profile ACL; POSIX permission bits are not available.
  if(process.platform!=='win32')assert.equal((await stat(path.dirname(file))).mode&0o777,0o700);
  await writeFile(file,'%PDF-1.4\nsynthetic');
 });
 assert.equal(Buffer.from(bytes).toString(),'%PDF-1.4\nsynthetic');
 await assert.rejects(access(path.dirname(destination)));
});
test('preview removes temporary files on backend failure and invalid output',async()=>{
 for(const fail of [true,false]){
  let destination;
  await assert.rejects(createResumePreview(input,async(_,file)=>{destination=file;await writeFile(file,'invalid');if(fail)throw Error('offline');}));
  await assert.rejects(access(path.dirname(destination)));
 }
});
