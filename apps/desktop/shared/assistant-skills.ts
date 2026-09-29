export const assistantSkills=[
 {id:"resume-tailor",title:"修改简历",description:"对照 JD 和真实经历，生成修改草稿"},
 {id:"interview-prep",title:"准备面试",description:"梳理重点、项目故事与逐题练习"},
 {id:"deep-research",title:"深度研究",description:"核对目标公司的业务、岗位与工作体验"},
] as const;
export type AssistantSkillId=typeof assistantSkills[number]["id"];
export const isAssistantSkillId=(value:unknown):value is AssistantSkillId=>assistantSkills.some(skill=>skill.id===value);
export const assistantSkill=(value:unknown)=>assistantSkills.find(skill=>skill.id===value);

export function skillDraft(id:AssistantSkillId|undefined,draft:string,selectedJob?:{company:string;title:string}):string{return id==="resume-tailor"&&selectedJob&&!draft.trim()?`请结合 ${selectedJob.company} 的「${selectedJob.title}」岗位要求，帮我修改简历。`:draft;}
