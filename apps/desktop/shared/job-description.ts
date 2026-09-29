/** Reading-only breaks: never rewrite or persist the source description. */
export function jobDescriptionParagraphs(text:string):string[]{
  return text.replace(/\r\n?/g,"\n")
    .replace(/[ \t]+(?=(?:[（(][一二三四五六七八九十]+[）)]|\d{1,2}[.．、](?!\d)|[一二三四五六七八九十]+、))/g,"\n")
    .replace(/(?<=[；;。])(?=\d{1,2}[.．、](?!\d)|[（(][一二三四五六七八九十]+[）)])/g,"\n")
    .replace(/[ \t]+(?=(?:岗位职责|工作职责|任职要求|岗位要求|职位要求|职位描述)(?:[：: \t]|[（(]))/g,"\n")
    .split(/\n+/).map(line=>line.trim()).filter(Boolean);
}
