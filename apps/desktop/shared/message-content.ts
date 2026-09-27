export type MessageBlock=
  |{kind:"paragraph"|"quote";text:string}
  |{kind:"heading";level:number;text:string}
  |{kind:"list";ordered:boolean;items:string[]}
  |{kind:"code";text:string}
  |{kind:"table";rows:string[][]};
export type InlinePart={kind:"text"|"strong"|"em"|"code"|"link"|"citation";text:string;url?:string;number?:number};

export function safeMessageUrl(value:string):string|undefined{
  try{const url=new URL(value);return url.protocol==="https:"||url.protocol==="http:"?url.href:undefined;}catch{return undefined;}
}

export function tokenizeMessageInline(text:string):InlinePart[]{
  const parts:InlinePart[]=[];
  const pattern=/\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s]+)\)|\[(\d+)\]/gu;
  let cursor=0;for(const match of text.matchAll(pattern)){
    if(match.index>cursor)parts.push({kind:"text",text:text.slice(cursor,match.index)});
    if(match[1])parts.push({kind:"strong",text:match[1]});
    else if(match[2])parts.push({kind:"em",text:match[2]});
    else if(match[3])parts.push({kind:"code",text:match[3]});
    else if(match[4]){const number=/^\d+$/u.test(match[4])?Number(match[4]):0;const url=safeMessageUrl(match[5]);parts.push(number?{kind:"citation",text:`[${number}]`,number}:url?{kind:"link",text:match[4],url}:{kind:"text",text:match[0]});}
    else parts.push({kind:"citation",text:match[0],number:Number(match[6])});
    cursor=match.index+match[0].length;
  }
  if(cursor<text.length)parts.push({kind:"text",text:text.slice(cursor)});
  return parts;
}

export function parseMessageBlocks(text:string):MessageBlock[]{
  const lines=text.replace(/\r\n?/gu,"\n").split("\n"),blocks:MessageBlock[]=[];
  const isTable=(index:number)=>index+1<lines.length&&lines[index].includes("|")&&/^\s*\|?\s*:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)*\s*\|?\s*$/u.test(lines[index+1]);
  const cells=(line:string)=>line.trim().replace(/^\|/u,"").replace(/\|$/u,"").split("|").map(cell=>cell.trim());
  let i=0;while(i<lines.length){const line=lines[i];if(!line.trim()){i++;continue;}
    if(/^\s*```/u.test(line)){i++;const body:string[]=[];while(i<lines.length&&!/^\s*```/u.test(lines[i]))body.push(lines[i++]);if(i<lines.length)i++;blocks.push({kind:"code",text:body.join("\n")});continue;}
    if(isTable(i)){const rows=[cells(line)];i+=2;while(i<lines.length&&lines[i].includes("|")&&lines[i].trim())rows.push(cells(lines[i++]));blocks.push({kind:"table",rows});continue;}
    const heading=/^(#{1,3})\s+(.+)$/u.exec(line);if(heading){blocks.push({kind:"heading",level:heading[1].length,text:heading[2]});i++;continue;}
    if(/^\s*>\s?/u.test(line)){const body:string[]=[];while(i<lines.length&&/^\s*>\s?/u.test(lines[i]))body.push(lines[i++].replace(/^\s*>\s?/u,""));blocks.push({kind:"quote",text:body.join("\n")});continue;}
    const list=/^\s*(?:([-*])|(\d+)\.)\s+(.+)$/u.exec(line);if(list){const ordered=Boolean(list[2]),items:string[]=[];while(i<lines.length){const next=/^\s*(?:([-*])|(\d+)\.)\s+(.+)$/u.exec(lines[i]);if(!next||Boolean(next[2])!==ordered)break;items.push(next[3]);i++;}blocks.push({kind:"list",ordered,items});continue;}
    const body=[line];i++;while(i<lines.length&&lines[i].trim()&&!/^\s*```|^#{1,3}\s|^\s*>|^\s*(?:[-*]|\d+\.)\s/u.test(lines[i])&&!isTable(i))body.push(lines[i++]);blocks.push({kind:"paragraph",text:body.join("\n")});
  }
  return blocks;
}
