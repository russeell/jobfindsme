export const assistantSkills=[
 {id:"resume-tailor",title:"修改简历",description:"依据真实材料，生成可审阅修改稿"},
 {id:"interview-prep",title:"准备面试",description:"围绕岗位与经历，准备并模拟面试"},
 {id:"deep-research",title:"深度研究",description:"研究公司、行业与技术主题"},
] as const;
export type AssistantSkillId=typeof assistantSkills[number]["id"];
export const isAssistantSkillId=(value:unknown):value is AssistantSkillId=>assistantSkills.some(skill=>skill.id===value);
export const assistantSkill=(value:unknown)=>assistantSkills.find(skill=>skill.id===value);

export function skillDraft(id:AssistantSkillId|undefined,draft:string,selectedJob?:{company:string;title:string}):string{return id==="resume-tailor"&&selectedJob&&!draft.trim()?`请结合 ${selectedJob.company} 的「${selectedJob.title}」岗位要求，帮我修改简历。`:draft;}
