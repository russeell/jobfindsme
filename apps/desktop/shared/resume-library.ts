import type {ResumeContent,SearchResultItem,PromptSession} from './contracts';

export const resumeSections:Record<keyof ResumeContent,string>={
  basic_information:'基本信息',experience:'工作经历',projects:'项目经历',education:'教育经历',skills:'专业技能',
};

export function resumeContentChanged(before:ResumeContent,after:ResumeContent):boolean {
  const normalized=(content:ResumeContent)=>Object.keys(resumeSections).map(key=>content[key as keyof ResumeContent].map(line=>line.trim()).filter(Boolean));
  return JSON.stringify(normalized(before))!==JSON.stringify(normalized(after));
}

export function resumeImprovementDraft(instruction:string,job?:SearchResultItem['job']):string {
  const target=job?`目标公司：${job.company}；岗位：${job.title}。请读取这个岗位的已保存 JD，按岗位要求修改简历。`:'请优化我的基础简历，优先改善结构、清晰度与表达。';
  return `${target}请读取已确认简历，以真实经历为依据，生成可逐项审阅和保存的修改提案。${instruction.trim()?`我的要求：${instruction.trim()}。`:''}只修改有依据的内容，不增加未经确认的技能、职责或数字；缺少事实单列为待确认。${job?'为此岗位保存独立副本，保留基础简历。':'保存前由我逐项决定。'}`;
}

export function resumeReviewCounts(session:PromptSession){
  return {accepted:session.patches.filter(p=>p.status==='accepted').length,pending:session.patches.filter(p=>p.status==='proposed').length,needsInput:session.patches.filter(p=>p.needs_user_input.length>0).length};
}

export type ResumeTemplate='classic'|'compact'|'campus'|'professional';
export const resumeTemplates=[
 {id:'professional',name:'社招',description:'工作成果在前，突出职责与贡献'},
 {id:'campus',name:'校招',description:'教育与项目在前，突出实践能力'},
 {id:'compact',name:'紧凑',description:'更小间距，适合内容较多的简历'},
] as const;
export function resumeTemplateSections(template:ResumeTemplate):Array<keyof ResumeContent>{
 if(template==='campus')return ['basic_information','education','projects','experience','skills'];
 if(template==='classic')return ['basic_information','education','experience','projects','skills'];
 return ['basic_information','experience','projects','skills','education'];
}
