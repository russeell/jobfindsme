import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resumeDocument,resumeDocumentContent,resumeNodeText,resumeDocumentFingerprint} from '../dist-electron/shared/resume-document.js';
const content={basic_information:['虚构样例'],education:[],experience:['第一行\n第二行'],projects:[],skills:['Python']};
test('legacy resume becomes editable without altering facts and keeps rich marks across templates',()=>{
 const doc=resumeDocument(content);assert.deepEqual(resumeDocumentContent(doc),content);
 const skills=doc.content.find(s=>s.attrs.section==='skills');skills.content[0].content[0].marks=[{type:'bold'}];
 const campus=resumeDocument(content,doc,'campus');assert.equal(campus.content[1].attrs.section,'education');assert.deepEqual(campus.content.find(s=>s.attrs.section==='skills'),skills);assert.deepEqual(resumeDocumentContent(campus),content);assert.equal(resumeDocumentFingerprint(campus),resumeDocumentFingerprint(doc));
});
test('lists, blank paragraphs and hard breaks produce the same plain facts as exports',()=>{
 assert.equal(resumeNodeText({type:'orderedList',attrs:{start:3},content:[{type:'listItem',content:[{type:'paragraph',content:[{type:'text',text:'one'},{type:'hardBreak'},{type:'text',text:'two'}]}]}]}),'3. one\ntwo');
 const doc=resumeDocument(content);doc.content[0].content.push({type:'paragraph'});assert.deepEqual(resumeDocumentContent(doc),content);
});
import {Editor,getSchema} from '@tiptap/core';
import {resumeEditorExtensions} from '../dist-electron/shared/resume-editor-schema.js';
test('document schema restores serialized drafts, applies local replacements and preserves empty sections',()=>{
 const editor=new Editor({element:null,extensions:resumeEditorExtensions,content:resumeDocument(content)});
 const original=editor.getJSON();editor.commands.setTextSelection({from:2,to:4});
 editor.commands.insertContentAt({from:2,to:4},[{type:'text',text:'修改'}]);
 const draft=JSON.parse(JSON.stringify(editor.getJSON()));getSchema(resumeEditorExtensions).nodeFromJSON(draft).check();
 const restored=new Editor({element:null,extensions:resumeEditorExtensions,content:original});
 restored.commands.setContent(draft,{errorOnInvalidContent:true});assert.deepEqual(JSON.parse(JSON.stringify(restored.getJSON())),draft);
 assert.equal(restored.getJSON().content.length,5);assert.equal(resumeDocumentContent(restored.getJSON()).education.length,0);
 editor.destroy();restored.destroy();
});
test('imported typography survives editor serialization, template changes and local edits',()=>{
 const doc=resumeDocument(content);
 doc.content[0].attrs={section:'basic_information',headingHidden:true};
 const skills=doc.content.find(s=>s.attrs.section==='skills');
 skills.attrs.headingColor='#17324d';skills.attrs.headingSize=12;
 skills.content[0].attrs={textAlign:'center'};
 skills.content[0].content[0].marks=[{type:'bold'},{type:'textStyle',attrs:{color:'#0f766e',fontSize:14}}];
 const editor=new Editor({element:null,extensions:resumeEditorExtensions,content:doc});
 const saved=editor.getJSON(),node=saved.content.find(s=>s.attrs.section==='skills');
 assert.equal(node.attrs.headingColor,'#17324d');assert.equal(saved.content[0].attrs.headingHidden,true);
 assert.equal(node.content[0].attrs.textAlign,'center');
 assert.deepEqual({...node.content[0].content[0].marks.find(m=>m.type==='textStyle').attrs},{color:'#0f766e',fontSize:14});
 assert.deepEqual(resumeDocumentContent(saved),content);
 const campus=resumeDocument(content,saved,'campus');assert.deepEqual(campus.content.find(s=>s.attrs.section==='skills'),node);
 let position;editor.state.doc.descendants((n,pos)=>{if(n.type.name==='text'&&n.text==='Python')position=pos;});
 editor.commands.setTextSelection({from:position,to:position+6});
 editor.commands.setMark('textStyle',{color:'#1769aa',fontSize:16});editor.commands.updateAttributes('paragraph',{textAlign:'right'});
 const changed=editor.getJSON().content.find(s=>s.attrs.section==='skills');
 assert.equal(changed.content[0].attrs.textAlign,'right');assert.equal(changed.content[0].content[0].marks.find(m=>m.type==='textStyle').attrs.fontSize,16);
 editor.commands.undo();editor.commands.undo();assert.deepEqual(resumeDocumentContent(editor.getJSON()),content);
 editor.destroy();
});
