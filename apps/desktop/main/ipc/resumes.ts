import {writeFileSync} from 'node:fs';
import type {BrowserWindow,dialog} from 'electron';
import type {AnalysisPreviewInput,ResumeConfirmation,ResumeEditInput,ResumeExportInput,ResumeSourceInput} from '../../shared/contracts';
import type {DesktopApiClient} from '../backend/api-client';
import {createResumePreview} from '../resume-preview';
import type {DesktopHandlerRegister} from './register';

type Dependencies={client:()=>DesktopApiClient;window:()=>BrowserWindow;dialog:Pick<typeof dialog,'showOpenDialog'|'showSaveDialog'>};
const validId=(id:unknown):id is string=>typeof id==='string'&&id.length>0&&id.length<=200;

/** Keep native file access in main; renderer cannot choose arbitrary read paths. */
export function registerResumeHandlers(register:DesktopHandlerRegister,deps:Dependencies){
 const client=deps.client;
 register('desktop:get-resume-state',()=>client().resumeState());
 register('desktop:import-resume',async()=>{
  const api=client();
  const selection=await deps.dialog.showOpenDialog(deps.window(),{title:'选择简历',properties:['openFile'],filters:[{name:'简历',extensions:['pdf','docx','md','txt']}]});
  if(selection.canceled||!selection.filePaths[0])return undefined;
  return api.importResume(selection.filePaths[0]);
 });
 register('desktop:confirm-resume',(_event,input:ResumeConfirmation)=>client().confirmResume(input));
 register('desktop:abandon-resume',(_event,workspaceId:string,profileId:string)=>client().abandonResume(workspaceId,profileId));
 register('desktop:analysis-preview',(_event,input:AnalysisPreviewInput)=>client().previewAnalysisCopy(input));
 register('desktop:clear-current-resume',(_event,workspaceId:string)=>client().clearCurrentResume(workspaceId));
 register('desktop:list-resume-versions',(_event,workspaceId:string)=>client().listResumeVersions(workspaceId));
 register('desktop:get-resume-version',(_event,workspaceId:string,versionId:string)=>{
  if(!validId(workspaceId)||!validId(versionId))throw Error('invalid resume version');
  return client().getResumeVersion(workspaceId,versionId);
 });
 register('desktop:hide-resume-version',(_event,workspaceId:string,versionId:string)=>client().hideResumeVersion(workspaceId,versionId));
 register('desktop:save-resume-version',(_event,input:ResumeEditInput)=>client().saveResumeVersion(input));
 register('desktop:restore-resume-version',(_event,workspaceId:string,versionId:string)=>client().restoreResumeVersion(workspaceId,versionId));
 register('desktop:resume-source',(_event,input:ResumeSourceInput)=>client().resumeSource(input));
 register('desktop:use-original-resume',(_event,workspaceId:string,profileId:string)=>client().useOriginalResume(workspaceId,profileId));
 register('desktop:export-resume-source',async(_event,input:ResumeSourceInput)=>{
  const source=await client().resumeSource(input);
  const extension=source.file_name.split('.').pop()?.toLowerCase();
  if(!extension||!['pdf','docx','md','txt'].includes(extension))throw Error('原文件格式不支持');
  const selection=await deps.dialog.showSaveDialog(deps.window(),{title:'保存原文件',defaultPath:source.file_name,filters:[{name:'原始简历',extensions:[extension]}]});
  if(selection.canceled||!selection.filePath)return false;
  const destination=selection.filePath.toLowerCase().endsWith(`.${extension}`)?selection.filePath:`${selection.filePath}.${extension}`;
  writeFileSync(destination,Buffer.from(source.content_base64,'base64'),{mode:0o600});
  return true;
 });
 register('desktop:preview-resume',(_event,input:Omit<ResumeExportInput,'format'>)=>{
  const api=client();return createResumePreview(input,(value,destination)=>api.exportResume(value,destination));
 });
 register('desktop:export-resume',async(_event,input:ResumeExportInput)=>{
  const api=client(),extensions={pdf:['pdf'],docx:['docx'],md:['md']};
  if(!input||!validId(input.version_id)||!['pdf','docx','md'].includes(input.format))throw Error('invalid resume export');
  const selection=await deps.dialog.showSaveDialog(deps.window(),{title:'导出简历',defaultPath:`简历-v${input.version_id.slice(-6)}.${input.format}`,filters:[{name:input.format.toUpperCase(),extensions:extensions[input.format]}]});
  if(selection.canceled||!selection.filePath)return undefined;
  const destination=selection.filePath.toLowerCase().endsWith(`.${input.format}`)?selection.filePath:`${selection.filePath}.${input.format}`;
  return api.exportResume(input,destination);
 });
}
