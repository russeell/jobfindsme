export const assistantSkills=[
 {id:"resume-tailor",title:"针对岗位修改简历",description:"对照 JD 和真实经历，生成修改草稿",starter:"请根据目标岗位和我的已确认简历，给出针对性的修改草稿。"},
 {id:"interview-prep",title:"准备面试",description:"梳理重点、项目故事与逐题练习",starter:"请帮我准备目标岗位的面试，先梳理重点和最重要的练习题。"},
 {id:"deep-research",title:"深度研究",description:"核对目标公司的业务、岗位与工作体验",starter:"请深度研究目标公司，重点了解业务、岗位发展和工作体验。"},
] as const;
export type AssistantSkillId=typeof assistantSkills[number]["id"];
export const isAssistantSkillId=(value:unknown):value is AssistantSkillId=>assistantSkills.some(skill=>skill.id===value);
export const assistantSkill=(value:unknown)=>assistantSkills.find(skill=>skill.id===value);
