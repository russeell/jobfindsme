export const assistantSkills=[
 {id:"resume-tailor",title:"修改简历",description:"依据真实材料，生成可审阅修改稿"},
 {id:"interview-prep",title:"模拟面试",description:"逐题练习，针对回答追问并反馈"},
 {id:"deep-research",title:"深度研究",description:"研究公司、行业与技术主题"},
] as const;
export type AssistantSkillId=typeof assistantSkills[number]["id"];
// Internal capabilities are loadable by the Agent, without adding another
// user-facing mode to the three job skills.
export const bundledSkills=[...assistantSkills,{id:"web-retrieval",title:"联网检索",description:"按任务选择搜索来源、读取原文并核对引用"}] as const;
export type BundledSkillId=typeof bundledSkills[number]["id"];
export const isBundledSkillId=(value:unknown):value is BundledSkillId=>bundledSkills.some(skill=>skill.id===value);
export const isAssistantSkillId=(value:unknown):value is AssistantSkillId=>assistantSkills.some(skill=>skill.id===value);
export const assistantSkill=(value:unknown)=>assistantSkills.find(skill=>skill.id===value);

export function skillDraft(id:AssistantSkillId|undefined,draft:string,selectedJob?:{company:string;title:string}):string{return id==="resume-tailor"&&selectedJob&&!draft.trim()?`请结合 ${selectedJob.company} 的「${selectedJob.title}」岗位要求，帮我修改简历。`:draft;}
