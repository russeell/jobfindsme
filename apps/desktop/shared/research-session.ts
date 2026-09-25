import {decideResearchRequest} from "./research-dialogue.js";
import type {SavedResearchChat} from "./research-chat-history.js";

const unknownCompanies=new Set(["公司未知","未知","BOSS直聘"]);
export function resolveResearchSession(value:string,prior:SavedResearchChat|undefined,job:{job_id:string;company:string;title:string}|undefined,context:{company?:string;title?:string}){
  const jobCompany=job&&!unknownCompanies.has(job.company)?job.company:undefined;
  const currentCompany=prior?.subjectCompany||jobCompany||context.company;
  const decision=decideResearchRequest(value,{company:currentCompany,title:prior?.subjectTitle||job?.title||context.title,hasJob:!!(prior?.jobId||job),pending:prior?.pendingResearch});
  const newSubject=decision.kind==="research"&&!!currentCompany&&decision.company.toLocaleLowerCase()!==currentCompany.toLocaleLowerCase();
  const current=newSubject?undefined:prior;
  const activeJobId=newSubject?undefined:(job?.job_id||current?.jobId);
  const sameJob=decision.kind==="research"&&!!activeJobId&&(!job||unknownCompanies.has(job.company)||decision.company.toLocaleLowerCase()===job.company.toLocaleLowerCase());
  return {decision,newSubject,current,currentCompany,activeJobId,sameJob};
}
