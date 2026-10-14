import type {DesktopBridge} from './contracts';

type ExportBridge=Pick<DesktopBridge,'getResumeVersion'|'exportResumeSource'|'exportResume'>;

/** Resolve the selected version directly: archived originals still export their source bytes. */
export async function exportSelectedResume(bridge:ExportBridge,workspaceId:string,versionId:string):Promise<boolean>{
  const version=await bridge.getResumeVersion(workspaceId,versionId);
  if(version.original_file){
    if(!version.source_document_id)throw Error('所选简历的原文件不可用，请在我的简历中重新导入。');
    return bridge.exportResumeSource({workspace_id:workspaceId,document_id:version.source_document_id});
  }
  return !!await bridge.exportResume({workspace_id:workspaceId,version_id:versionId,format:'pdf'});
}
