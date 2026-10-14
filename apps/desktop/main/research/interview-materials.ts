/** Run-local cache: failed reads can retry; never share personal materials across tasks. */
export function interviewMaterialReader<T>(read:()=>Promise<T>):()=>Promise<T>{
  let pending:Promise<T>|undefined;
  return ()=>pending??(pending=Promise.resolve().then(read).catch(error=>{pending=undefined;throw error;}));
}
export async function loadInterviewMaterials(readJob:undefined|(()=>Promise<unknown>),readResume:undefined|(()=>Promise<AnalysisResume>)){
  const [job,resume]=await Promise.allSettled([readJob?.(),readResume?.()]);
  const raw=job.status==='fulfilled'&&job.value&&typeof job.value==='object'?job.value as Record<string,unknown>:undefined;
  const copy=resume.status==='fulfilled'?resume.value:undefined;
  const materials=preparationMaterials(raw,copy,{jd:16000,resume:12000,resumeOmitted:resume.status==='rejected'&&String(resume.reason).includes('no resume selected for job')});
  return {
    job:raw?{job_id:raw.job_id,title:raw.title,company:raw.company,description:materials.description,source:raw.source,apply_url:raw.apply_url}:null,
    resume:copy?{source_version_id:copy.source_version_id,text:materials.resume,limitations:copy.limitations}:null,
    limitations:materials.limitations,
  };
}
import {preparationMaterials,type AnalysisResume} from './preparation-materials';
