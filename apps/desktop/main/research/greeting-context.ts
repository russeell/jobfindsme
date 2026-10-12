import type {GreetingTarget} from '../../shared/contracts';
import type {DesktopApiClient} from '../backend/api-client';

export type GreetingContext = {company:string;title:string;description:string;resume:string};

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
  return {company:preparation.job.company,title:preparation.job.title,
    description:preparation.job.description.slice(0,4000),resume:resume?.text.slice(0,6000)||''};
}
