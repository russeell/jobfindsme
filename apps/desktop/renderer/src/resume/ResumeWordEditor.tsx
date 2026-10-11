import {PopoverButton} from '../shared/PopoverButton';
import {ResumeModal} from './ResumeDialogs';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {EditorContent,useEditor,useEditorState} from '@tiptap/react';
import {getSchema} from '@tiptap/core';
import {resumeEditorExtensions} from '../../../shared/resume-editor-schema';
import type {ResumeVersion,ResumeDocumentNode} from '../../../shared/contracts';
import {resumeDocument,resumeDocumentContent,resumeDocumentFingerprint} from '../../../shared/resume-document';
import {resumeTemplates,type ResumeTemplate} from '../../../shared/resume-library';
import {userError} from '../../../shared/user-errors';
import {ResumeDocument} from './ResumeDocument';
import {ResumeSelectionAI} from './ResumeSelectionAI';


export function ResumeWordEditor({workspaceId,version,onSaved,onDirty,onOrganize,onImprove}:{workspaceId:string;version:ResumeVersion;onSaved():Promise<void>;onDirty(dirty:boolean):void;onOrganize():void;onImprove?:(instruction?:string)=>void}){
 const toolbarRef=useRef<HTMLDivElement>(null);
 const preference=`jfm.resume.template.${workspaceId}`;
 const [template,setTemplate]=useState<ResumeTemplate>(()=>{try{const value=localStorage.getItem(preference);return resumeTemplates.some(t=>t.id===value)?value as ResumeTemplate:'professional';}catch{return 'professional';}});
 const [mode,setMode]=useState<'edit'|'preview'>('edit'),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[discard,setDiscard]=useState(false);
 const previousMode=useRef(mode);
 useLayoutEffect(()=>{if(previousMode.current===mode)return;previousMode.current=mode;const toolbar=toolbarRef.current;const content=toolbar?.closest<HTMLElement>('.content');if(toolbar&&content)content.scrollTop+=toolbar.parentElement!.getBoundingClientRect().top-content.getBoundingClientRect().top-16;},[mode]);
 const [templatesOpen,setTemplatesOpen]=useState(false),[showEmpty,setShowEmpty]=useState(false);
 const [base,setBase]=useState(version),[aiOpen,setAiOpen]=useState(false);
 const cacheKey=(id:string)=>`jfm.resume.document-draft.${workspaceId}.${id}`;
 const [loaded]=useState(()=>{
   const schema=getSchema(resumeEditorExtensions);
   const saved=schema.nodeFromJSON(resumeDocument(version.content,version.document,template)).toJSON();
   try{const text=localStorage.getItem(cacheKey(version.version_id));if(text){const cached=schema.nodeFromJSON(JSON.parse(text));cached.check();return {content:cached.toJSON(),baseline:resumeDocumentFingerprint(saved),restored:true,error:''};}}
   catch{return {content:saved,baseline:resumeDocumentFingerprint(saved),restored:false,error:'本机草稿未能恢复，已显示已保存版本；草稿副本仍保留。'};}
   return {content:saved,baseline:resumeDocumentFingerprint(saved),restored:false,error:''};
 });
 const initial=useRef(loaded.baseline),baseId=useRef(version.version_id);baseId.current=base.version_id;
 const editor=useEditor({immediatelyRender:false,shouldRerenderOnTransaction:false,extensions:resumeEditorExtensions,content:loaded.content,
   editorProps:{attributes:{class:'resume-word-content','aria-label':'简历文档编辑器',role:'textbox','aria-multiline':'true',spellcheck:'false'},handleDrop:(_view,event)=>{if(event.dataTransfer?.files.length){event.preventDefault();return true;}return false;}},
   onUpdate:({editor})=>{const changed=resumeDocumentFingerprint(editor.getJSON())!==initial.current;setDirty(changed);onDirty(changed);setNotice('');try{if(changed)localStorage.setItem(cacheKey(baseId.current),JSON.stringify(editor.getJSON()));else localStorage.removeItem(cacheKey(baseId.current));}catch{setError('本机草稿保存失败，请点击保存版本。');}},
 });
 const state=useEditorState({editor,selector:({editor})=>editor&&!editor.isDestroyed?{bold:editor.isActive('bold'),italic:editor.isActive('italic'),underline:editor.isActive('underline'),bullet:editor.isActive('bulletList'),ordered:editor.isActive('orderedList'),undo:editor.can().undo(),redo:editor.can().redo(),json:JSON.stringify(editor.getJSON()),selection:{empty:editor.state.selection.empty,from:editor.state.selection.from,to:editor.state.selection.to}}:null});
 const stale=base.version_id!==version.version_id;
 useEffect(()=>{if(!editor||editor.isDestroyed)return;const changed=resumeDocumentFingerprint(editor.getJSON())!==initial.current;setDirty(changed);onDirty(changed);if(loaded.restored&&changed)setNotice('已恢复本机未保存的草稿。');if(loaded.error)setError(loaded.error);},[editor]);
 useEffect(()=>{if(!editor||editor.isDestroyed||!stale||dirty||busy||version.version_number<base.version_number)return;setBase(version);editor.commands.setContent(resumeDocument(version.content,version.document,template),{emitUpdate:false});initial.current=resumeDocumentFingerprint(editor.getJSON());},[version.version_id,editor,dirty,busy]);
 useEffect(()=>{if(editor&&!editor.isDestroyed)editor.setEditable(!busy,false);},[busy,editor]);

 useEffect(()=>()=>onDirty(false),[]);
 async function save():Promise<ResumeVersion|undefined>{
   if(!editor||busy||stale)return;if(!dirty)return base;
   const document=editor.getJSON() as ResumeDocumentNode,content=resumeDocumentContent(document);
   if(!Object.values(content).some(values=>values.length)){setError('请保留至少一项简历内容。');return;}
   setBusy(true);setError('');
   try{const next=await window.jobfindsme!.saveResumeVersion({workspace_id:workspaceId,base_version_id:base.version_id,content,document});try{localStorage.removeItem(cacheKey(base.version_id));}catch{}initial.current=resumeDocumentFingerprint(document);setBase(next);setDirty(false);onDirty(false);setNotice('已保存新版本，原版本保留。');await onSaved();return next;}catch(e){setError(userError(e).message);}finally{setBusy(false);}
 }
 async function preview(){if(dirty){const next=await save();if(!next)return;}setMode('preview');}
 async function exportFile(format:'docx'|'pdf'){const next=dirty?await save():base;if(!next)return;setBusy(true);setError('');try{const result=await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:next.version_id,format,template});if(result)setNotice(format==='docx'?'已导出可继续编辑的 Word 文档。':'已导出 PDF。');}catch(e){setError(userError(e).message);}finally{setBusy(false);}}
 function reset(){if(!editor)return;editor.commands.setContent(resumeDocument(version.content,version.document,template),{emitUpdate:false});initial.current=resumeDocumentFingerprint(editor.getJSON());try{localStorage.removeItem(cacheKey(base.version_id));}catch{}setBase(version);setDirty(false);onDirty(false);setDiscard(false);setError('');setNotice('已恢复已保存版本。');}
 useEffect(()=>{const toolbar=toolbarRef.current;if(!toolbar)return;const measure=()=>toolbar.parentElement?.style.setProperty('--document-toolbar-height',`${toolbar.offsetHeight}px`);const observer=new ResizeObserver(measure);observer.observe(toolbar);measure();return()=>observer.disconnect();},[editor]);
 if(!editor)return <p role="status">正在打开文档…</p>;
 function applyTemplate(next:ResumeTemplate){setTemplate(next);try{localStorage.setItem(preference,next);}catch{}editor!.commands.setContent(resumeDocument(resumeDocumentContent(editor!.getJSON()),editor!.getJSON(),next));}
 const action=(fn:()=>unknown)=>()=>{setAiOpen(false);fn();};
 return <div className="resume-word-workspace">
   <div ref={toolbarRef} className="resume-word-toolbar" aria-label="文档工具栏">
     <div className="resume-word-modes"><button aria-pressed={mode==='edit'} disabled={busy} onClick={()=>setMode('edit')}>编辑</button><button aria-pressed={mode==='preview'} disabled={busy||stale} onClick={()=>void preview()}>{dirty?'保存并预览':'分页预览'}</button></div>
     <span className="resume-word-status">{busy?'处理中…':dirty?'有未保存的修改':'已保存'}</span>
     <button disabled={busy} onClick={()=>setTemplatesOpen(true)}>模板与排版</button>{onImprove&&<button disabled={busy||dirty} title={dirty?"保存后再修改整份简历":undefined} onClick={()=>onImprove()}>✦ AI 修改</button>}
     <PopoverButton title="导出简历" label={dirty?'保存并导出':'导出'} disabled={busy||stale} width={240}>{close=><><p className="note">{dirty?'先保存当前修改，再选择导出位置。':'导出当前版本和所选模板。'}</p><button className="status-option" onClick={()=>{close();void exportFile('pdf');}}>PDF · 用于投递</button><button className="status-option" onClick={()=>{close();void exportFile('docx');}}>Word · 继续编辑</button></>}</PopoverButton>
     <button className="primary-button" disabled={busy||stale||!dirty} onClick={()=>void save()}>保存</button>
   </div>
   {templatesOpen&&<ResumeModal title="选择简历模板" onClose={()=>setTemplatesOpen(false)}><div className="resume-template-body"><p className="note">只改变排版，不改动你的经历。导出沿用所选模板。</p><div className="resume-template-gallery">{resumeTemplates.map(t=><button className={`resume-template-card ${t.id}`} key={t.id} aria-pressed={template===t.id} onClick={()=>applyTemplate(t.id)}><span className="resume-template-thumb" aria-hidden="true"><b/><i/><i/><strong/><i/><i/><i/><strong/><i/><i/></span><b>{t.name}</b><small>{t.description}</small></button>)}</div><div className="resume-template-options"><button disabled={dirty} onClick={()=>{setTemplatesOpen(false);onOrganize();}}>调整内容归属</button><span>空章节自动隐藏，可在编辑栏添加。</span></div></div><footer><p>AI 按真实经历提出修改，审阅后保存。</p>{onImprove&&<button disabled={dirty} onClick={()=>{setTemplatesOpen(false);onImprove(`按“${resumeTemplates.find(t=>t.id===template)?.name}”模板组织内容；${template==='campus'?'教育、项目与实习优先':template==='compact'?'精简重复表达，保留关键事实':'突出真实工作成果'}。检查错分的章节，将项目与工作内容归回对应章节，不能遗漏原有经历`);}}>✦ AI 生成修改稿</button>}<button className="primary-button" onClick={()=>setTemplatesOpen(false)}>完成</button></footer></ResumeModal>}
   {error&&<p className="notice" role="alert">{error}</p>}{notice&&<p className="resume-feedback" role="status">{notice}</p>}
   {stale&&<p className="notice">基础简历已有新版本，当前草稿保留。请复制需要的内容，再放弃草稿以读取最新版本。</p>}
   {mode==='edit'?<>
     <div className="resume-word-format" aria-label="文字格式">
       <button title="撤销 ⌘Z" aria-label="撤销" disabled={busy||!state?.undo} onClick={action(()=>editor.chain().focus().undo().run())}>↶</button><button title="重做 ⇧⌘Z" aria-label="重做" disabled={busy||!state?.redo} onClick={action(()=>editor.chain().focus().redo().run())}>↷</button><span className="toolbar-divider"/>
       <button aria-label="加粗" aria-pressed={state?.bold} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleBold().run()}><b>B</b></button><button aria-label="斜体" aria-pressed={state?.italic} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleItalic().run()}><i>I</i></button><button aria-label="下划线" aria-pressed={state?.underline} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleUnderline().run()}><u>U</u></button>
       <button aria-label="项目符号列表" aria-pressed={state?.bullet} disabled={busy} onClick={()=>editor.chain().focus().toggleBulletList().run()}>• 列表</button><button aria-label="编号列表" aria-pressed={state?.ordered} disabled={busy} onClick={()=>editor.chain().focus().toggleOrderedList().run()}>1. 列表</button><span className="toolbar-divider"/>
       <button disabled={busy||!state||state.selection.empty} onMouseDown={e=>e.preventDefault()} onClick={()=>setAiOpen(v=>!v)}>✦ 修改选中文字</button>
       <button className="resume-sections-toggle" aria-pressed={showEmpty} onClick={()=>setShowEmpty(value=>!value)}>{showEmpty?'隐藏空章节':'＋ 添加章节'}</button>

     </div>
     {aiOpen&&<ResumeSelectionAI editor={editor} workspaceId={workspaceId} disabled={busy} onClose={()=>setAiOpen(false)}/>}
     <div className={`resume-word-surface ${template}${showEmpty?' show-empty-sections':''}`}><EditorContent editor={editor}/></div>
     <div className="resume-word-footer"><span>直接编辑 · 草稿仅存本机 · 导出分页请查看预览</span>{dirty&&<button disabled={busy} onClick={()=>setDiscard(true)}>放弃草稿</button>}</div>
     {discard&&<div className="notice" role="alert">放弃当前未保存的草稿？<button onClick={()=>setDiscard(false)}>继续编辑</button><button disabled={busy} onClick={reset}>放弃草稿并恢复</button></div>}
   </>:<ResumeDocument managedToolbar key={`${base.version_id}:${template}`} workspaceId={workspaceId} version={base} template={template} onTemplateChange={applyTemplate}/>}
 </div>;
}
