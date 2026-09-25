import {researchScopeFromQuestion} from "./research-scope";

export type PendingResearch={question:string;missing:"company"|"role"|"focus";company?:string}|{kind:"job_search";question:string;keyword:string};
export type ResearchDecision=
  | {kind:"chat"}
  | {kind:"clarify";reply:string;pending:PendingResearch}
  | {kind:"job_search";reply:string;query:string;company?:string;pending?:PendingResearch}
  | {kind:"research";question:string;company:string;title?:string};

const researchCue=/(?:研究|查(?:一下|资料)?|调查|公开资料|公司|企业|岗位|职位|职责|招聘|JD|经营|上市|口碑|评价|员工|工作强度|加班|福利|待遇|薪资|发展|股价|营收|财报|融资|靠谱吗|怎么样)/iu;
const unknown=/^(?:这家|该公司|某公司|公司|未知|不知道|不清楚|这个|这份|该岗位|某个)$/u;
const bareName=/^[\p{Script=Han}\p{L}\p{N}· .-]{2,60}$/u;

function namedCompany(value:string):string|undefined{
  const scoped=researchScopeFromQuestion(value).company;
  if(scoped&&!/^(?:这个|这家|该|某|公司)/u.test(scoped)&&!/(?:岗位|职位|职责)/u.test(scoped))return scoped;
  const explicit=value.match(/^(?:帮我)?(?:研究|了解|查查|查一下|看看)\s*([\p{Script=Han}\p{L}\p{N}· .-]{2,40})\s*$/u)?.[1]?.trim();
  return explicit&&!unknown.test(explicit)?explicit:undefined;
}

function jobKeyword(value:string):string|undefined{
  if(!/(?:岗位|职位|工作机会)/u.test(value)||/(?:职责|福利|发展|工作强度|薪资|待遇)/u.test(value)||/^(?:研究|调查)/u.test(value))return;
  const before=value.split(/(?:相关的?|方向的?)?(?:岗位|职位|工作机会)/u)[0]
    ?.replace(/^(?:我)?(?:想|希望)?(?:了解|找|看看|搜索|查找)?\s*/u,"").trim();
  if(!before||before.length>40||/(?:公司|企业|这个|这份|该|此)/u.test(before))return;
  return /^agent$/iu.test(before)?"Agent":before;
}

function optionalCompany(value:string):string|undefined{
  const name=value.replace(/^公司(?:全称)?(?:是|[:：])?\s*/u,"").trim();
  return bareName.test(name)&&!unknown.test(name)&&!/(?:你|我|谁|什么|怎么|如何|想|了解|找|岗位|职位|搜索|继续)/u.test(name)?name:undefined;
}

export function decideResearchRequest(value:string,context:{company?:string;title?:string;hasJob:boolean;pending?:PendingResearch}):ResearchDecision{
  const question=value.trim();
  const pending=context.pending;
  if(pending&&"kind" in pending){
      const company=optionalCompany(question);
      if(company){const query=`${company} ${pending.keyword}`;return {kind:"job_search",company,query,reply:`明白，你想看 ${company} 的 ${pending.keyword} 相关岗位。可以用下方入口把“${query}”填进找工作；选择来源后再发起检索。`};}
  }else if(pending){
    if(pending.missing==="company"){
      const company=(namedCompany(question)||question.replace(/^(?:公司(?:全称)?是|是)\s*/u,"").trim());
      if(!bareName.test(company)||unknown.test(company))return {kind:"clarify",reply:"请直接说公司全称，或提出新的问题。",pending};
      if(/(?:这个|这家|该公司|某公司)/u.test(company))return {kind:"clarify",reply:"还需要可核对的公司全称。",pending};
      return {kind:"research",question:pending.question,company,title:context.title};
    }else if(pending.missing==="focus"){
      const focus=question.replace(/[?？。！!]+$/u,"").trim();
      if(!focus||focus.length>60||/^(?:你|我|谁|什么)/u.test(focus))return {kind:"clarify",reply:"可以说想了解经营、岗位机会、工作体验或福利中的哪一方面；也可以直接提出新问题。",pending};
      return {kind:"research",question:`${pending.company}的${focus}怎么样？`,company:pending.company!,title:context.title};
    }else{
      const title=question.replace(/^(?:岗位|职位)(?:名称)?(?:是|[:：])\s*/u,"").trim();
      if(!bareName.test(title)||unknown.test(title))return {kind:"clarify",reply:"请直接说岗位名称，或提出新的问题。",pending};
      return {kind:"research",question:pending.question,company:pending.company!,title};
    }
  }
  const keyword=!context.company&&!context.hasJob?jobKeyword(question):undefined;
  if(keyword)return {kind:"job_search",query:keyword,reply:`可以从 ${keyword} 相关岗位开始。下方入口会把“${keyword}”填进找工作；选择来源后再发起检索。有目标公司也可以直接告诉我。`,pending:{kind:"job_search",question,keyword}};
  if(!researchCue.test(question))return {kind:"chat"};
  const scope=researchScopeFromQuestion(question);
  const explicitCompany=namedCompany(question);
  const company=explicitCompany||context.company;
  if(!company)return {kind:"clarify",reply:context.hasJob?"这条岗位没有可核对的公司全称。请直接说公司名称。":"想研究哪家公司？请直接说公司名称。",pending:{question,missing:"company"}};
  if(/^(?:公司)?(?:怎么样|如何|靠谱吗)[?？。！!]*$/u.test(question.replace(company,"").replace(/^的/u,"").trim()))return {kind:"clarify",reply:`${company}涉及多个业务和团队。你更想了解经营与产品、岗位机会、工作体验，还是福利？我可以按具体范围核对公开来源。`,pending:{question,missing:"focus",company}};
  const title=explicitCompany&&context.company&&explicitCompany.toLocaleLowerCase()!==context.company.toLocaleLowerCase()?scope.title:context.title||scope.title;
  if(!title&&/(?:这个|这份|该|此)(?:岗位|职位)/u.test(question))return {kind:"clarify",reply:"具体是哪个岗位？请直接说岗位名称。",pending:{question,missing:"role",company}};
  return {kind:"research",question,company,title};
}
