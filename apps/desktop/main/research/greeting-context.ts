import type {GreetingTarget} from '../../shared/contracts';
import type {DesktopApiClient} from '../backend/api-client';
import {preparationMaterials} from './preparation-materials';

export type GreetingContext = {company:string;title:string;description:string;resume:string;limitations?:string[]};

export function validGreetingTarget(value:unknown):value is GreetingTarget {
  if(!value||typeof value!=='object')return false;
  const target=value as GreetingTarget;
  const id=(value:unknown)=>typeof value==='string'&&value.length>0&&value.length<=200;
  return id(target.workspaceId)&&id(target.jobId)&&(target.resumeVersionId===null||id(target.resumeVersionId));
}

export async function loadGreetingContext(api:Pick<DesktopApiClient,'getJobPreparation'|'agentResume'>,target:GreetingTarget):Promise<GreetingContext>{
  const [preparation,resume]=await Promise.all([
    api.getJobPreparation(target.workspaceId,target.jobId),
    target.resumeVersionId?api.agentResume(target.workspaceId,undefined,target.resumeVersionId):undefined,
  ]);
  if(resume&&resume.source_version_id!==target.resumeVersionId)throw Error('所选简历材料不一致，请重新读取。');
  return {company:preparation.job.company,title:preparation.job.title,
    ...preparationMaterials(preparation.job,resume,{jd:4000,resume:6000,resumeOmitted:target.resumeVersionId===null})};
}
