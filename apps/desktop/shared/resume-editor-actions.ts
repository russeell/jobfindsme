import type {Editor} from '@tiptap/core';
import type {ResumeDocumentNode} from './contracts';
import {resumeDocumentTemplate} from './resume-document';

// ProseMirror replaces top-level content without replacing document attrs.
// Keep both in one transaction so layout changes also survive one undo.
export function setResumeEditorDocument(editor:Editor,document:ResumeDocumentNode,emitUpdate=true):boolean {
 return editor.chain().setContent(document,{emitUpdate}).command(({tr})=>{
  tr.setDocAttribute('template',resumeDocumentTemplate(document)??null);return true;
 }).run();
}

// Reset only text styling and paragraph alignment. Structural sections and
// lists remain intact, and the complete change is one undoable transaction.
export function clearResumeTextFormatting(editor:Editor):boolean{
  return editor.chain().unsetAllMarks().updateAttributes('paragraph',{textAlign:null}).run();
}
