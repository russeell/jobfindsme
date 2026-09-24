export type ResearchInput = {url?:string;question:string;error?:string};

export function splitResearchInput(raw:string):ResearchInput {
  const value=raw.trim();
  const matches=[...value.matchAll(/https?:\/\/[^\s<>"“”]+/gi)];
  if(matches.length>1)return {question:value,error:"一次只能读取一个岗位链接，请保留一个链接后重试。"};
  if(!matches.length){
    if(/(?:[a-z][a-z0-9+.-]*:\/\/|www\.|\b[\w-]+(?:\.[\w-]+)+\/[^\s]+)/i.test(value))return {question:value,error:"链接格式不完整，请粘贴以 https:// 开头的岗位详情链接。"};
    return {question:value};
  }
  const match=matches[0];
  const url=match[0].replace(/[，。；！？,.;!?）)\]]+$/u,"");
  const question=(value.slice(0,match.index)+value.slice(match.index!+match[0].length)).replace(/^[\s：:，,。；;]+|[\s：:，,。；;]+$/gu,"").trim();
  if(question.length>300)return {question,error:"问题最多 300 字，请缩短后重试。"};
  return {url,question};
}
