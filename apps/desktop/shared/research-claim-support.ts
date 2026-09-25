import type {ResearchEvidence} from "./contracts.js";

export type SupportedResearchClaim={
  statement:string;quote:string;evidence_ids:string[];category:string;scope:string;
  source_type:"official_disclosure"|"personal_account"|"public_web"|"mixed";
  support_level:"direct"|"qualified";
};
const categories=new Set(["business","listing","positive","negative","workload","benefits","role","development"]);
const normalize=(value:string)=>value.toLocaleLowerCase().replace(/[^\p{Script=Han}\p{L}\p{N}]/gu,"");
const negative=(value:string)=>/(?:尚未|未曾|未|没有|无|不|否认)/u.test(value);
const current=(value:string)=>/(?:目前|现在|当前|至今|如今|仍然|仍在|现已)/u.test(value);
const status=(value:string)=>/(?:已|完成|成功)上市/u.test(value)?"listed":/(?:拟|计划|筹备|申请)上市/u.test(value)?"planned":/(?:未|尚未)上市/u.test(value)?"not_listed":"";
const numerals=(value:string)=>[...value.matchAll(/\d+(?:\.\d+)?%?|[一二三四五六七八九十百千万]+(?:年|月|日|人|倍|%)/gu)].map(match=>match[0]);
const geographic=/(?:上海|北京|深圳|广州|杭州|成都|全国|全球|海外|中国|美国|欧洲|华东|华南|华北)/gu;
function coverage(statement:string,quote:string):number{
  const a=normalize(statement),b=normalize(quote),grams=new Set<string>();
  for(let i=0;i<a.length-1;i++)grams.add(a.slice(i,i+2));
  if(!grams.size)return 0;
  return [...grams].filter(term=>b.includes(term)).length/grams.size;
}
export function checkResearchClaim(input:unknown,evidence:Map<string,ResearchEvidence>,company:string):SupportedResearchClaim|undefined{
  if(!input||typeof input!=="object")return;
  const value=input as Record<string,unknown>;
  const statement=String(value.statement||value.quote||"").trim(),quote=String(value.quote||"").trim();
  const ids=Array.isArray(value.evidence_ids)?value.evidence_ids.filter((id):id is string=>typeof id==="string"):[];
  if(statement.length<8||statement.length>180||quote.length<8||quote.length>360||ids.length!==1||!categories.has(String(value.category||"")))return;
  const row=evidence.get(ids[0]);
  if(!row||row.verification_status!=="independently_retrieved"||!row.excerpt.includes(quote)||!row.url?.startsWith("https://"))return;
  const body=row.excerpt;
  if(!company||!body.includes(company)||!statement.includes(company)||!quote.includes(company))return;
  if(negative(statement)!==negative(quote))return;
  if(current(statement))return;
  if(status(statement)&&status(statement)!==status(quote))return;
  if(numerals(statement).some(number=>!quote.includes(number)))return;
  if(([...statement.matchAll(geographic)]).some(match=>!quote.includes(match[0])))return;
  const direct=normalize(quote).includes(normalize(statement));
  if(!direct&&coverage(statement,quote)<0.85)return;
  const proposedScope=String(value.scope||"").trim();
  const scope=proposedScope.length>=2&&proposedScope.length<=60&&quote.includes(proposedScope)?proposedScope:"团队、地区或法律主体未核实";
  const sourceType=row.context?.source_type;
  return {statement,quote,evidence_ids:ids,category:String(value.category),scope,source_type:sourceType==="official_disclosure"?"official_disclosure":sourceType==="public_web"?"public_web":"personal_account",support_level:direct?"direct":"qualified"};
}
