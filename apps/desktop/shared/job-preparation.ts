import type {AssistantSkillId} from './assistant-skills';
import type {PreparationStage,PromptSession,SearchResultItem} from './contracts';
import {canonicalJobUrl} from './research-reports';

export const preparationStages:Record<PreparationStage,string>={considering:'考虑中',applied:'已投递',interview:'面试中',offer:'Offer',closed:'已结束'};
export function proposalMatchesJob(session:PromptSession,job:SearchResultItem['job']):boolean {
  return session.target_job_id?session.target_job_id===job.job_id:!!session.target_url&&!!job.apply_url&&canonicalJobUrl(session.target_url)===canonicalJobUrl(job.apply_url);
}
export function preparationDraft(skill:AssistantSkillId,job:SearchResultItem['job']):string {
  const role=`目标公司：${job.company}；岗位：${job.title}。`;
  return skill==='resume-tailor'?`${role}请对照岗位要求和已确认简历，优先指出匹配与缺口，再提出有事实依据的修改。为这个岗位保留独立副本，不编造经历。`:skill==='interview-prep'?`${role}请帮我准备面试：先给出最重要的准备重点，再逐题练习。已有材料优先使用，缺少 JD 也可开始。`:`${role}请研究这个岗位：先核对岗位和公司原文，概括业务、要求及值得追问的问题。事实附来源，说明证据缺口。`;
}
