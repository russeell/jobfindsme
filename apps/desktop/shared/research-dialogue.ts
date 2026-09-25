import {researchScopeFromQuestion} from "./research-scope";

export type PendingResearch={question:string;missing:"company"|"role";company?:string};
export type ResearchDecision=
  | {kind:"chat"}
  | {kind:"clarify";reply:string;pending:PendingResearch}
  | {kind:"research";question:string;company:string;title?:string};

const researchCue=/(?:研究|查(?:一下|资料)?|调查|公开资料|公司|企业|岗位|职位|职责|招聘|JD|经营|上市|口碑|评价|员工|工作强度|加班|福利|待遇|薪资|发展|靠谱吗|怎么样)/iu;
const unknown=/^(?:这家|该公司|某公司|公司|未知|不知道|不清楚|这个|这份|该岗位|某个)$/u;
const bareName=/^[\p{Script=Han}\p{L}\p{N}· .-]{2,60}$/u;

function namedCompany(value:string):string|undefined{
  const scoped=researchScopeFromQuestion(value).company;
  if(scoped&&!/^(?:这个|这家|该|某|公司)/u.test(scoped)&&!/(?:岗位|职位|职责)/u.test(scoped))return scoped;
  const explicit=value.match(/^(?:帮我)?(?:研究|了解|查查|查一下|看看)\s*([\p{Script=Han}\p{L}\p{N}· .-]{2,40})\s*$/u)?.[1]?.trim();
  return explicit&&!unknown.test(explicit)?explicit:undefined;
}

export function decideResearchRequest(value:string,context:{company?:string;title?:string;hasJob:boolean;pending?:PendingResearch}):ResearchDecision{
  const question=value.trim();
  const pending=context.pending;
  if(pending){
    if(pending.missing==="company"){
      const company=(namedCompany(question)||question.replace(/^(?:公司(?:全称)?是|是)\s*/u,"").trim());
      if(!bareName.test(company)||unknown.test(company))return {kind:"clarify",reply:"请直接说公司全称，或提出新的问题。",pending};
      if(/(?:这个|这家|该公司|某公司)/u.test(company))return {kind:"clarify",reply:"还需要可核对的公司全称。",pending};
      return {kind:"research",question:pending.question,company,title:context.title};
    }
    const title=question.replace(/^(?:岗位|职位)(?:名称)?(?:是|[:：])\s*/u,"").trim();
    if(!bareName.test(title)||unknown.test(title))return {kind:"clarify",reply:"请直接说岗位名称，或提出新的问题。",pending};
    return {kind:"research",question:pending.question,company:pending.company!,title};
  }
  if(!researchCue.test(question))return {kind:"chat"};
  const scope=researchScopeFromQuestion(question);
  const explicitCompany=namedCompany(question);
  const company=explicitCompany||context.company;
  if(!company)return {kind:"clarify",reply:context.hasJob?"这条岗位没有可核对的公司全称。请直接说公司名称。":"想研究哪家公司？请直接说公司名称。",pending:{question,missing:"company"}};
  const title=explicitCompany&&context.company&&explicitCompany.toLocaleLowerCase()!==context.company.toLocaleLowerCase()?scope.title:context.title||scope.title;
  if(!title&&/(?:这个|这份|该|此)(?:岗位|职位)/u.test(question))return {kind:"clarify",reply:"具体是哪个岗位？请直接说岗位名称。",pending:{question,missing:"role",company}};
  return {kind:"research",question,company,title};
}
