import type {Editor} from '@tiptap/core';

// Reset only text styling and paragraph alignment. Structural sections and
// lists remain intact, and the complete change is one undoable transaction.
export function clearResumeTextFormatting(editor:Editor):boolean{
  return editor.chain().unsetAllMarks().updateAttributes('paragraph',{textAlign:null}).run();
}
