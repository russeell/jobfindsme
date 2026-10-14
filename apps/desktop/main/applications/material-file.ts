import {createHash} from 'node:crypto';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import type {DesktopApiClient} from '../backend/api-client';

export type ApplicationFile={path:string;name:string;originalName:string|null;hash:string;label:string;dispose():Promise<void>};
export async function applicationFile(api:Pick<DesktopApiClient,'getResumeVersion'|'resumeSource'|'exportResume'>,workspaceId:string,versionId:string):Promise<ApplicationFile>{
  const version=await api.getResumeVersion(workspaceId,versionId);
  const folder=await mkdtemp(path.join(tmpdir(),'jfm-application-'));
  const dispose=()=>rm(folder,{recursive:true,force:true});
  try{
    let bytes:Buffer,extension='pdf',originalName:string|null=null;
    if(version.original_file&&version.source_document_id){
      const source=await api.resumeSource({workspace_id:workspaceId,document_id:version.source_document_id});
      originalName=source.file_name;extension=path.extname(source.file_name).slice(1).toLowerCase();
      if(!['pdf','docx'].includes(extension))throw Error('本次所选原件不是 PDF 或 Word，请在我的简历中导出后使用。');
      bytes=Buffer.from(source.content_base64,'base64');
    }else{
      const destination=path.join(folder,'export.pdf');
      await api.exportResume({workspace_id:workspaceId,version_id:versionId,format:'pdf'},destination);
      bytes=await readFile(destination);await rm(destination);
    }
    if(!bytes.length||bytes.length>20*1024*1024||extension==='pdf'&&bytes.subarray(0,5).toString()!=='%PDF-'||extension==='docx'&&bytes.subarray(0,2).toString()!=='PK')throw Error('简历文件无效或超过 BOSS 的 20 MB 限制。');
    const hash=createHash('sha256').update(bytes).digest('hex'),name=`简历-${hash.slice(0,16)}.${extension}`,destination=path.join(folder,name);
    await writeFile(destination,bytes,{mode:0o600});
    return {path:destination,name,originalName,hash,label:version.original_file?'所选原始简历':`所选编辑简历 · ${new Date(version.created_at).toLocaleDateString('zh-CN')}`,dispose};
  }catch(error){await dispose();throw error;}
}
