import type {ApplicationRecordInput,JobPreparationInput,NextActionInput} from '../../shared/contracts';
import type {DesktopApiClient} from '../backend/api-client';
import type {DesktopHandlerRegister} from './register';

export function registerPreparationHandlers(register:DesktopHandlerRegister,client:()=>DesktopApiClient){
 register('desktop:list-application-records',(_event,workspaceId:string,jobId?:string,deleted=false)=>client().listApplicationRecords(workspaceId,jobId,deleted));
 register('desktop:set-application-deleted',(_event,workspaceId:string,jobId:string,recordId:string,deleted:boolean)=>{
  if(typeof deleted!=='boolean')throw Error('invalid record action');
  return client().setApplicationDeleted(workspaceId,jobId,recordId,deleted);
 });
 register('desktop:save-application-record',(_event,input:ApplicationRecordInput)=>client().saveApplicationRecord(input));
 register('desktop:update-next-action',(_event,input:NextActionInput)=>client().updateNextAction(input));
 register('desktop:get-job-preparation',(_event,workspaceId:string,jobId:string)=>client().getJobPreparation(workspaceId,jobId));
 register('desktop:save-job-preparation',(_event,input:JobPreparationInput)=>client().saveJobPreparation(input));
}
