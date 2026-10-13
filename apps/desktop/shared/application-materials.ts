import type {ApplicationRecord,ApplicationRecordInput,ResumeVersion} from './contracts';
import {renderGreeting} from './application-greeting';

export function applicationDraft(input:{workspaceId:string;job:{job_id:string;title:string;company:string};resumeId?:string|null;versions:ResumeVersion[];records:ApplicationRecord[];greeting:string;recordId:string}):ApplicationRecordInput {
 const {workspaceId,job,resumeId,versions,records,greeting,recordId}=input;
 const previous=records.filter(row=>row.workspace_id===workspaceId&&row.job_id===job.job_id&&(row.status==='prepared'||row.status==='opened'))
  .sort((a,b)=>b.updated_at.localeCompare(a.updated_at)||b.created_at.localeCompare(a.created_at))[0];
 // A saved material is an explicit choice, including choosing no attachment.
 // Background job associations and a newer base resume must not replace it.
 if(previous)return {workspace_id:workspaceId,job_id:job.job_id,record_id:previous.record_id,resume_version_id:previous.resume_version_id,message:previous.message,status:previous.status};
 return {workspace_id:workspaceId,job_id:job.job_id,record_id:recordId,resume_version_id:resumeId??versions.find(row=>row.is_current)?.version_id??null,message:renderGreeting(greeting,job),status:'prepared'};
}
