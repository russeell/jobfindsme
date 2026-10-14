/** Model-facing excerpts only. Never read raw files or mutate stored materials. */
import type {ResumeAnalysisMaterial} from '../../shared/resume-contracts';
export type AnalysisResume = ResumeAnalysisMaterial;
export type PreparationJob = {title?:unknown;description?:unknown};
const sectionNames:Record<string,string>={experience:'工作经历',projects:'项目经历',skills:'技能描述',education:'教育经历'};
const generic = new Set(['the','and','with','for','you','your','this','that','have','will','from','work','job','experience','required','requirements','工程','程师','工作','经验','岗位','要求','负责','能力','相关','项目','技术','参与','开发']);

function terms(query:string):Array<[string,number]>{
 const values=new Map<string,number>();
 for(const word of query.normalize('NFKC').toLowerCase().match(/[a-z][a-z0-9+#.-]{1,63}|[\u4e00-\u9fff]{2,}/g)||[]){
  if(/^[a-z]/.test(word)){const term=word.replace(/[.-]+$/,'');if(term&&!generic.has(term))values.set(term,3);}
  else for(let i=0;i<word.length-1;i++){
   const term=word.slice(i,i+2);if(!generic.has(term))values.set(term,1);
  }
 }
 // Keep both ends of very large queries: requirements often appear after duties.
 const result=[...values];return result.length<=192?result:[...result.slice(0,96),...result.slice(-96)];
}

function paragraphs(text:string,budget:number):string[]{
 // The existing analysis API serializes redacted sections as JSON. Grouped
 // entries retain company/date/project context; ignore personal/unknown keys.
 try{
  const data=JSON.parse(text);
  if(data&&typeof data==='object'&&!Array.isArray(data)){
   const entries=Object.entries(data).flatMap(([key,values])=>sectionNames[key]&&Array.isArray(values)?values.filter((value):value is string=>typeof value==='string'&&!!value.trim()).map(value=>`${sectionNames[key]}\n${value}`):[]);
   if(entries.length)return entries.flatMap(value=>splitEntry(value,budget));
  }
 }catch{}
 return text.split(/\n\s*\n/).filter(value=>value.trim()).flatMap(value=>splitEntry(value,budget));
}

function splitEntry(value:string,budget:number):string[]{
 if(value.length<=budget)return [value];
 const lines=value.split(/\n+/),heading=lines.slice(0,2).join('\n');
 const prefix=lines.length>2&&heading.length<=Math.min(400,budget/3)?heading+'\n':'';
 // Large entries are subdivided by existing line/sentence boundaries. Carry
 // their short original heading so an isolated achievement keeps its identity.
 return value.split(/\n+|(?<=[。！？])|(?<=[.!?;])\s+/u).filter(part=>part.trim()).flatMap(part=>{
  const chunks:string[]=[];const size=Math.max(1,budget-prefix.length);
  for(let offset=0;offset<part.length;){
   const rest=part.slice(offset);let piece=boundedPrefix(rest,size);
   if(/[a-z0-9]/i.test(piece.slice(-1))&&/[a-z0-9]/i.test(rest[piece.length]||'')){
    const start=piece.search(/[a-z0-9+#.-]+$/i);if(start>0)piece=piece.slice(0,start);
   }
   if(piece)chunks.push((offset||!heading.includes(part)?prefix:'')+piece);
   offset+=piece.length||2;
  }
  return chunks;
 });
}

function boundedPrefix(text:string,budget:number):string{
 let end=Math.min(text.length,budget);
 if(end<text.length&&end>0&&/[\uD800-\uDBFF]/.test(text[end-1]))end--;
 return text.slice(0,end);
}

export function selectMaterialText(text:string,query:string,budget:number):{text:string;truncated:boolean}{
 if(!Number.isInteger(budget)||budget<1)throw new RangeError('Invalid material budget');
 if(text.length<=budget)return {text,truncated:false};
 const keywords=terms(query),entries=paragraphs(text,budget);
 const ranked=entries.map((value,index)=>{
  const normalized=value.normalize('NFKC').toLowerCase();
  return {value,index,score:keywords.reduce((sum,[term,weight])=>{
   const matches=/^[a-z]/.test(term)?new RegExp(`(?<![a-z0-9_])${term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}(?![a-z0-9_])`).test(normalized):normalized.includes(term);
   return sum+(matches?weight:0);
  },0)};
 }).sort((a,b)=>b.score-a.score||a.index-b.index);
 if(!ranked[0]?.score)return {text:boundedPrefix(text,budget),truncated:true};
 const selected:Array<{index:number;value:string}>=[];let remaining=budget;
 for(const entry of ranked){
  if(!entry.score)break;
  const separator=selected.length?2:0;
  if(entry.value.length+separator<=remaining){selected.push(entry);remaining-=entry.value.length+separator;}
  else if(!selected.length){selected.push({...entry,value:boundedPrefix(entry.value,remaining)});remaining=0;}
  if(remaining<=2)break;
 }
 return {text:selected.sort((a,b)=>a.index-b.index).map(item=>item.value).join('\n\n'),truncated:true};
}

export function preparationMaterials(job:PreparationJob|undefined,resume:AnalysisResume|undefined,budgets:{jd:number;resume:number;resumeOmitted?:boolean}){
 const title=String(job?.title||''),rawJD=String(job?.description||'');
 const jd=selectMaterialText(rawJD,title,budgets.jd);
 const copy=selectMaterialText(resume?.text||'',`${title}\n${rawJD}`,budgets.resume);
 return {description:jd.text,resume:copy.text,limitations:[
  ...(!job?['岗位材料未取得，可按目标方向准备。']:[]),
  ...(!resume?[budgets.resumeOmitted?'本岗位已选择暂不附简历，本轮不带入个人经历。':'简历材料未取得，不推测个人经历。']:[]),
  ...(resume?.limitations?[resume.limitations]:[]),
  ...(jd.truncated||copy.truncated?['材料过长，本轮按岗位相关性带入有限原文，未包含全部内容。']:[]),
 ]};
}
