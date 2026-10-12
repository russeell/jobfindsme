import {Node,Mark,Extension,mergeAttributes} from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import {ListItem} from '@tiptap/extension-list';
import {Decoration,DecorationSet} from '@tiptap/pm/view';
import {Plugin} from '@tiptap/pm/state';
import type {ResumeContent} from './contracts.js';
import {resumeSections} from './resume-library.js';
function safeColor(value:unknown):string|null {
 if(typeof value!=='string')return null;
 if(/^#[\da-f]{6}$/i.test(value))return value.toLowerCase();
 const rgb=value.match(/^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/i);
 return rgb&&rgb.slice(1).every(c=>Number(c)<=255)?'#'+rgb.slice(1).map(c=>Number(c).toString(16).padStart(2,'0')).join(''):null;
}
function safeSize(value:unknown):number|null {const size=typeof value==='number'?value:Number.NaN;return Number.isFinite(size)&&size>=6&&size<=72?Math.round(size*100)/100:null;}
const TextStyle=Mark.create({
 name:'textStyle',
 addAttributes(){return {
   color:{default:null,parseHTML:el=>safeColor(el.style.color),renderHTML:attrs=>safeColor(attrs.color)?{style:`color:${safeColor(attrs.color)}`}:{ }},
   fontSize:{default:null,parseHTML:el=>{const size=el.style.fontSize;return /^(?:\d+(?:\.\d+)?)(?:pt|px)$/.test(size)?safeSize(parseFloat(size)*(size.endsWith('px')?.75:1)):null;},renderHTML:attrs=>safeSize(attrs.fontSize)?{style:`font-size:${safeSize(attrs.fontSize)}pt`}:{ }},
 };},
 parseHTML(){return [{tag:'span',getAttrs:el=>(el as HTMLElement).style.color||(el as HTMLElement).style.fontSize?{}:false}];},
 renderHTML({HTMLAttributes}){return ['span',HTMLAttributes,0];},
});
const Alignment=Extension.create({name:'resumeAlignment',addGlobalAttributes(){return [{types:['paragraph'],attributes:{textAlign:{default:null,parseHTML:el=>['left','center','right','justify'].includes(el.style.textAlign)?el.style.textAlign:null,renderHTML:attrs=>['left','center','right','justify'].includes(attrs.textAlign)?{style:`text-align:${attrs.textAlign}`}:{}}}}];}});
const Section=Node.create({
 name:'resumeSection',group:'block',content:'(paragraph | bulletList | orderedList)+',isolating:true,defining:true,
 addAttributes(){return {section:{default:'experience'},headingColor:{default:null,renderHTML:()=>({})},headingSize:{default:null,renderHTML:()=>({})},headingHidden:{default:null,renderHTML:()=>({})}};},
 parseHTML(){return [{tag:'section[data-resume-section]',getAttrs:element=>({section:(element as HTMLElement).dataset.resumeSection})}];},
 renderHTML({node,HTMLAttributes}){const key=node.attrs.section as keyof ResumeContent;const color=safeColor(node.attrs.headingColor),size=safeSize(node.attrs.headingSize);const style=[color?`color:${color}`:'',size?`font-size:${size}pt`:''].filter(Boolean).join(';');return ['section',mergeAttributes(HTMLAttributes,{'data-resume-section':key}),...(!node.attrs.headingHidden?[['h2',{contenteditable:'false',style},resumeSections[key]]]:[]),['div',0]];},
 addProseMirrorPlugins(){return [new Plugin({props:{decorations(state){const decorations:Decoration[]=[];state.doc.forEach((node,pos)=>{if(!node.textContent.trim())decorations.push(Decoration.node(pos,pos+node.nodeSize,{'class':'resume-empty-section'}));});return DecorationSet.create(state.doc,decorations);}},filterTransaction:tr=>{if(!tr.docChanged)return true;const keys:string[]=[];tr.doc.forEach(node=>keys.push(node.type.name==='resumeSection'?node.attrs.section:''));return keys.length===5&&new Set(keys).size===5&&keys.every(key=>key in resumeSections);}})];},
});

export const resumeEditorExtensions=[StarterKit.configure({document:false,heading:false,blockquote:false,code:false,codeBlock:false,link:false,horizontalRule:false,dropcursor:false,trailingNode:false,listItem:false}),ListItem.extend({content:'paragraph (paragraph | bulletList | orderedList)*'}),Node.create({name:'doc',topNode:true,content:'resumeSection+'}),Section,TextStyle,Alignment];
