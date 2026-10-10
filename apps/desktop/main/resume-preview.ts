import {mkdtemp,readFile,rm,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import type {ResumeExportInput} from '../shared/contracts';

// Render using the same backend and template as export. Never return file paths
// or leave a second copy of a private resume in an application cache directory.
export async function createResumePreview(
  input:Omit<ResumeExportInput,'format'>,
  render:(input:ResumeExportInput,destination:string)=>Promise<unknown>,
):Promise<Uint8Array>{
  const folder=await mkdtemp(path.join(tmpdir(),'jfm-resume-preview-'));
  const destination=path.join(folder,'resume.pdf');
  try{
    await render({...input,format:'pdf'},destination);
    if((await stat(destination)).size>12*1024*1024)throw Error('简历预览过大，请精简内容后重试。');
    const bytes=await readFile(destination);
    if(bytes.subarray(0,5).toString()!=='%PDF-')throw Error('简历预览生成失败，请重试。');
    return new Uint8Array(bytes);
  }finally{await rm(folder,{recursive:true,force:true});}
}
