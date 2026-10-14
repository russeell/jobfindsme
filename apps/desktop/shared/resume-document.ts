import type {ResumeContent,ResumeDocumentNode as Node} from './contracts';
import {resumeSections,resumeTemplateSections,type ResumeTemplate} from './resume-library';

export function resumeParagraph(text:string,marks?:Node['marks']):Node {
  return {type:'paragraph',content:text.split('\n').flatMap((line,i)=>[...(i?[{type:'hardBreak'}]:[]),...(line?[{type:'text',text:line,...(marks?.length?{marks}:{} )}]:[])])};
}
export function resumeDocument(content:ResumeContent,saved?:Node|null,template:ResumeTemplate='professional'):Node {
  const sections=new Map(saved?.content?.map(s=>[s.attrs?.section,s]));
  return {type:'doc',attrs:{template},content:resumeTemplateSections(template).map(key=>sections.get(key)||{type:'resumeSection',attrs:{section:key},content:content[key]?.length?content[key].map(value=>resumeParagraph(value)):[resumeParagraph('')]})};
}
export function resumeDocumentTemplate(document?:Node|null):ResumeTemplate|undefined {
 const value=document?.attrs?.template;
 return value==='classic'||value==='professional'||value==='campus'||value==='compact'?value:undefined;
}
export function resumeNodeText(node:Node):string {
  if(node.type==='text')return node.text||'';
  if(node.type==='hardBreak')return '\n';
  const children=node.content||[];
  if(node.type==='bulletList'||node.type==='orderedList')return children.map((child,i)=>(node.type==='bulletList'?'• ':`${Number(node.attrs?.start||1)+i}. `)+resumeNodeText(child)).join('\n');
  return children.map(resumeNodeText).join(node.type==='listItem'?'\n':'');
}
export function resumeDocumentContent(document:Node):ResumeContent {
  const content=Object.fromEntries(Object.keys(resumeSections).map(k=>[k,[]])) as unknown as ResumeContent;
  for(const section of document.content||[]){const key=section.attrs?.section as keyof ResumeContent;if(key in content)content[key]=(section.content||[]).map(resumeNodeText).map(t=>t.trim()).filter(Boolean);}
  return content;
}

// Section serialization order alone is not an edit. The chosen template is
// versioned document metadata and must participate in draft/save detection.
export function resumeDocumentFingerprint(document:Node):string {
 return JSON.stringify({...document,content:[...(document.content||[])].sort((a,b)=>String(a.attrs?.section).localeCompare(String(b.attrs?.section)))});
}
