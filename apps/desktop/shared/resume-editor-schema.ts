import {Node,mergeAttributes} from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import {ListItem} from '@tiptap/extension-list';
import {Plugin} from '@tiptap/pm/state';
import type {ResumeContent} from './contracts.js';
import {resumeSections} from './resume-library.js';
const Section=Node.create({
 name:'resumeSection',group:'block',content:'(paragraph | bulletList | orderedList)+',isolating:true,defining:true,
 addAttributes(){return {section:{default:'experience'}};},
 parseHTML(){return [{tag:'section[data-resume-section]',getAttrs:element=>({section:(element as HTMLElement).dataset.resumeSection})}];},
 renderHTML({node,HTMLAttributes}){const key=node.attrs.section as keyof ResumeContent;return ['section',mergeAttributes(HTMLAttributes,{'data-resume-section':key}),['h2',{contenteditable:'false'},resumeSections[key]],['div',0]];},
 addProseMirrorPlugins(){return [new Plugin({filterTransaction:tr=>{if(!tr.docChanged)return true;const keys:string[]=[];tr.doc.forEach(node=>keys.push(node.type.name==='resumeSection'?node.attrs.section:''));return keys.length===5&&new Set(keys).size===5&&keys.every(key=>key in resumeSections);}})];},
});

export const resumeEditorExtensions=[StarterKit.configure({document:false,heading:false,blockquote:false,code:false,codeBlock:false,link:false,horizontalRule:false,dropcursor:false,trailingNode:false,listItem:false}),ListItem.extend({content:'paragraph (paragraph | bulletList | orderedList)*'}),Node.create({name:'doc',topNode:true,content:'resumeSection+'}),Section];
