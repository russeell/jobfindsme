/** Run-local cache: failed reads can retry; never share personal materials across tasks. */
export function interviewMaterialReader<T>(read:()=>Promise<T>):()=>Promise<T>{
  let pending:Promise<T>|undefined;
  return ()=>pending??(pending=Promise.resolve().then(read).catch(error=>{pending=undefined;throw error;}));
}
export async function loadInterviewMaterials(readJob:undefined|(()=>Promise<unknown>),readResume:undefined|(()=>Promise<{source_version_id:string;text:string;limitations:string}>)){
  const [job,resume]=await Promise.allSettled([readJob?.(),readResume?.()]);
  const raw=job.status==='fulfilled'&&job.value&&typeof job.value==='object'?job.value as Record<string,unknown>:undefined;
  const copy=resume.status==='fulfilled'?resume.value:undefined;
  return {
    job:raw?{job_id:raw.job_id,title:raw.title,company:raw.company,description:String(raw.description||'').slice(0,16000),source:raw.source,apply_url:raw.apply_url}:null,
    resume:copy?{source_version_id:copy.source_version_id,text:copy.text.slice(0,12000),limitations:copy.limitations}:null,
    limitations:[...(!raw?['岗位材料未取得，可按目标方向准备。']:[]),...(!copy?['已确认简历未取得，不推测个人经历。']:[]),...(String(raw?.description||'').length>16000||Number(copy?.text.length)>12000?['材料过长，本轮只带入有限文本。']:[])],
  };
}
