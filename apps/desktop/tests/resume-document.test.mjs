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
