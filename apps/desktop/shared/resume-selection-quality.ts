export type ResumeSelectionPurpose='resume_rewrite'|'resume_shorten'|'resume_proofread';
export type ResumeSelectionQuality='ok'|'unchanged'|'facts_changed';

// Deterministic checks for explicit facts only. This is not a verification of
// every factual meaning; the original and suggestion still require review.
function quantitativeFacts(text:string):string[]{
 const facts:string[]=[];
 let remaining=text.normalize('NFKC').replace(/\bk8s\b/giu,'kubernetes');
 remaining=remaining.replace(/(?<!\d)((?:19|20)\d{2})\s*[-/.年]\s*(0?[1-9]|1[0-2])(?:(?:\s*[-/.月]\s*(0?[1-9]|[12]\d|3[01]))|月)?(?!\d)/gu,(_match,year,month,day)=>{
  facts.push(`date:${year}-${Number(month)}${day?`-${Number(day)}`:''}`);return ' ';
 });
 remaining=remaining.replace(/(?<![\d.])(\d+(?:\.\d+)?)\s*(年|个月|月)(?!\d)/gu,(match,number,unit)=>{
  if(Number(number)>120)return match;
  facts.push(`duration:${Number(number)*(unit==='年'?12:1)}`);return ' ';
 });
 remaining=remaining.replace(/(?<=\d),(?=\d{3}(?:\D|$))/gu,'');
 for(const match of remaining.matchAll(/\d+(?:\.\d+)?\s*%?/gu)){
  facts.push(`number:${Number.parseFloat(match[0])}${match[0].includes('%')?'%':''}`);
 }
 return [...new Set(facts)].sort();
}
const explicitFacts:Array<[string,RegExp]>=[
 ['python',/\bpython\b/iu],['fastapi',/\bfastapi\b/iu],['java',/\bjava\b/iu],
 ['javascript',/\b(?:javascript|js)\b/iu],['typescript',/\b(?:typescript|ts)\b/iu],
 ['pytorch',/\bpytorch\b/iu],['tensorflow',/\btensorflow\b/iu],
 ['docker',/\bdocker\b/iu],['kubernetes',/\b(?:kubernetes|k8s)\b/iu],
 ['redis',/\bredis\b/iu],['mysql',/\bmysql\b/iu],['postgresql',/\b(?:postgresql|postgres)\b/iu],
 ['langchain',/\blangchain\b/iu],['langgraph',/\blanggraph\b/iu],['rag',/\brag\b/iu],
 ['bachelor',/本科|\bbachelor(?:'s)?\b/iu],['master',/硕士|\bmaster(?:'s)?\b/iu],
 ['doctor',/博士|\bph\.?d\.?\b|\bdoctorate\b/iu],['college',/大专|专科/iu],
 ['lead',/主导/u],['independent',/独立完成/u],['proficient',/精通/u],['expert',/专家级/u],
];
export function resumeSelectionQuality(before:string,after:string,purpose:ResumeSelectionPurpose):ResumeSelectionQuality{
 const original=before.normalize('NFKC'),candidate=after.normalize('NFKC');
 if(JSON.stringify(quantitativeFacts(original))!==JSON.stringify(quantitativeFacts(candidate))||explicitFacts.some(([,pattern])=>pattern.test(candidate)&&!pattern.test(original))||['{公司}','{岗位}'].some(token=>candidate.includes(token)&&!original.includes(token)))return 'facts_changed';
 const normalize=(value:string)=>{
  let text=value.normalize('NFKC').replace(/\s/gu,'');
  if(purpose!=='resume_proofread')text=text.replace(/[，。！？；：、,.!?;:“”‘’"'（）()\[\]{}]/gu,'');
  return text;
 };
 return normalize(before)===normalize(after)?'unchanged':'ok';
}
