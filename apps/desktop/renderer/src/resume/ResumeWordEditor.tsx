import {PopoverButton} from '../shared/PopoverButton';
import {ResumeModal} from './ResumeDialogs';
import {useEffect,useLayoutEffect,useRef,useState,type KeyboardEvent as ReactKeyboardEvent} from 'react';
import {EditorContent,useEditor,useEditorState} from '@tiptap/react';
import {getSchema} from '@tiptap/core';
import {resumeEditorExtensions} from '../../../shared/resume-editor-schema';
import type {ResumeVersion,ResumeDocumentNode} from '../../../shared/contracts';
import {resumeDocument,resumeDocumentContent,resumeDocumentFingerprint,resumeDocumentTemplate} from '../../../shared/resume-document';
import {resumeTemplates,type ResumeTemplate} from '../../../shared/resume-library';
import {userError} from '../../../shared/user-errors';
import {ResumeDocument} from './ResumeDocument';
import {ResumeSelectionAI} from './ResumeSelectionAI';
import {Icon} from '../shared/Icon';
import {clearResumeTextFormatting,setResumeEditorDocument} from '../../../shared/resume-editor-actions';


export function ResumeWordEditor({workspaceId,version,onSaved,onDirty,onOrganize,onImprove}:{workspaceId:string;version:ResumeVersion;onSaved():Promise<void>;onDirty(dirty:boolean):void;onOrganize():void;onImprove?:(instruction?:string)=>void}){
 const toolbarRef=useRef<HTMLDivElement>(null);
 const workspaceRef=useRef<HTMLDivElement>(null),formatRef=useRef<HTMLDivElement>(null),focusButton=useRef<HTMLButtonElement>(null);
 const [focused,setFocused]=useState(false),[draftStored,setDraftStored]=useState(true);
 const [selectionRun,setSelectionRun]=useState(0);
 const preference=`jfm.resume.template.${workspaceId}`;
 const [mode,setMode]=useState<'edit'|'preview'>('edit'),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[discard,setDiscard]=useState(false);
 const previousMode=useRef(mode);
 useLayoutEffect(()=>{if(previousMode.current===mode)return;previousMode.current=mode;const toolbar=toolbarRef.current;const content=focused?workspaceRef.current:toolbar?.closest<HTMLElement>('.content');if(toolbar&&content)content.scrollTop+=toolbar.parentElement!.getBoundingClientRect().top-content.getBoundingClientRect().top-(focused?0:16);},[mode,focused]);
 const [templatesOpen,setTemplatesOpen]=useState(false),[showEmpty,setShowEmpty]=useState(false);
 const [base,setBase]=useState(version),[aiOpen,setAiOpen]=useState(false),[selectionOpen,setSelectionOpen]=useState(false);
 const cacheKey=(id:string)=>`jfm.resume.document-draft.${workspaceId}.${id}`;
 const [loaded]=useState(()=>{
   const schema=getSchema(resumeEditorExtensions);
   let savedTemplate=resumeDocumentTemplate(version.document);
   if(!savedTemplate){try{const value=localStorage.getItem(preference);if(resumeTemplates.some(t=>t.id===value))savedTemplate=value as ResumeTemplate;}catch{}}
   savedTemplate??='professional';
   const saved=schema.nodeFromJSON(resumeDocument(version.content,version.document,savedTemplate)).toJSON();
   try{const text=localStorage.getItem(cacheKey(version.version_id));if(text){const cached=schema.nodeFromJSON(JSON.parse(text));cached.check();const content=cached.toJSON(),template=resumeDocumentTemplate(content)||savedTemplate;content.attrs={template};return {content,baseline:resumeDocumentFingerprint(saved),restored:true,error:'',template,savedTemplate};}}
   catch{return {content:saved,baseline:resumeDocumentFingerprint(saved),restored:false,error:'本机草稿未能恢复，已显示已保存版本；草稿副本仍保留。',template:savedTemplate,savedTemplate};}
   return {content:saved,baseline:resumeDocumentFingerprint(saved),restored:false,error:'',template:savedTemplate,savedTemplate};
 });
 const [template,setTemplate]=useState<ResumeTemplate>(loaded.template);
 const layoutUnsaved=!resumeDocumentTemplate(base.document);
 useEffect(()=>{try{localStorage.setItem(preference,template);}catch{}},[template,preference]);
 const initial=useRef(loaded.baseline),baseId=useRef(version.version_id);baseId.current=base.version_id;
 const editor=useEditor({immediatelyRender:false,shouldRerenderOnTransaction:false,extensions:resumeEditorExtensions,content:loaded.content,
   editorProps:{attributes:{class:'resume-word-content','aria-label':'简历文档编辑器',role:'textbox','aria-multiline':'true',spellcheck:'false'},handleDrop:(_view,event)=>{if(event.dataTransfer?.files.length){event.preventDefault();return true;}return false;}},
   onUpdate:({editor})=>{setTemplate(resumeDocumentTemplate(editor.getJSON())||loaded.savedTemplate);const changed=resumeDocumentFingerprint(editor.getJSON())!==initial.current;setDirty(changed);onDirty(changed);setNotice('');try{if(changed)localStorage.setItem(cacheKey(baseId.current),JSON.stringify(editor.getJSON()));else localStorage.removeItem(cacheKey(baseId.current));setDraftStored(true);}catch{setDraftStored(false);}},
 });
 const state=useEditorState({editor,selector:({editor})=>editor&&!editor.isDestroyed?{textStyle:editor.getAttributes('textStyle'),align:editor.getAttributes('paragraph').textAlign||'left',bold:editor.isActive('bold'),italic:editor.isActive('italic'),underline:editor.isActive('underline'),bullet:editor.isActive('bulletList'),ordered:editor.isActive('orderedList'),undo:editor.can().undo(),redo:editor.can().redo(),characters:editor.state.doc.textContent.replace(/\s/g,'').length,selection:{empty:editor.state.selection.empty,from:editor.state.selection.from,to:editor.state.selection.to}}:null});
 const stale=base.version_id!==version.version_id;
 useEffect(()=>{if(!editor||editor.isDestroyed)return;const changed=resumeDocumentFingerprint(editor.getJSON())!==initial.current;setDirty(changed);onDirty(changed);if(loaded.restored&&changed)setNotice('已恢复本机未保存的草稿。');if(loaded.error)setError(loaded.error);},[editor]);
 useEffect(()=>{if(!editor||editor.isDestroyed||!stale||dirty||busy||version.version_number<base.version_number)return;const next=resumeDocumentTemplate(version.document)||loaded.savedTemplate;setBase(version);setTemplate(next);setResumeEditorDocument(editor,resumeDocument(version.content,version.document,next),false);initial.current=resumeDocumentFingerprint(editor.getJSON());},[version.version_id,editor,dirty,busy]);
 useEffect(()=>{if(editor&&!editor.isDestroyed)editor.setEditable(!busy,false);},[busy,editor]);

 useEffect(()=>()=>onDirty(false),[]);
 async function save(restoreFocus=false):Promise<ResumeVersion|undefined>{
   if(!editor||busy||stale)return;if(!dirty&&!layoutUnsaved)return base;
   const document=editor.getJSON() as ResumeDocumentNode,content=resumeDocumentContent(document);
   if(!Object.values(content).some(values=>values.length)){setError('请保留至少一项简历内容。');return;}
   setBusy(true);setError('');
   try{const next=await window.jobfindsme!.saveResumeVersion({workspace_id:workspaceId,base_version_id:base.version_id,content,document});try{localStorage.removeItem(cacheKey(base.version_id));}catch{}initial.current=resumeDocumentFingerprint(document);setBase(next);setDirty(false);setDraftStored(true);onDirty(false);setNotice('修改已保存。');await onSaved();return next;}catch(e){setError(userError(e).message);}finally{setBusy(false);if(restoreFocus)requestAnimationFrame(()=>{if(!editor.isDestroyed&&workspaceRef.current?.getBoundingClientRect().width)editor.commands.focus(undefined,{scrollIntoView:false});});}
 }
 async function preview(){if(dirty||layoutUnsaved){const next=await save();if(!next)return;}setMode('preview');}
 async function exportFile(format:'docx'|'pdf'){const next=dirty||layoutUnsaved?await save():base;if(!next)return;setBusy(true);setError('');setNotice('');try{const result=await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:next.version_id,format});if(result)setNotice(format==='docx'?'已导出可继续编辑的 Word 文档。':'已导出 PDF。');}catch(e){setError(userError(e).message);}finally{setBusy(false);}}
 async function improve(instruction?:string){if(!onImprove||dirty||busy)return;if(layoutUnsaved&&!await save())return;if(focused)leaveFocus();onImprove(instruction);}
 function reset(){if(!editor)return;const next=resumeDocumentTemplate(version.document)||loaded.savedTemplate;setTemplate(next);setResumeEditorDocument(editor,resumeDocument(version.content,version.document,next),false);initial.current=resumeDocumentFingerprint(editor.getJSON());try{localStorage.removeItem(cacheKey(base.version_id));}catch{}setBase(version);setDirty(false);setDraftStored(true);onDirty(false);setDiscard(false);setError('');setNotice('已恢复已保存版本。');}
 useEffect(()=>{const toolbar=toolbarRef.current,format=formatRef.current,root=workspaceRef.current;if(!toolbar||!root)return;const measure=()=>{root.style.setProperty('--document-toolbar-height',`${toolbar.offsetHeight}px`);root.style.setProperty('--document-format-height',`${format?.offsetHeight||0}px`);};const observer=new ResizeObserver(measure);observer.observe(toolbar);if(format)observer.observe(format);measure();return()=>observer.disconnect();},[editor,mode]);
 useEffect(()=>{const shortcut=(event:KeyboardEvent)=>{if(!(event.metaKey||event.ctrlKey)||event.altKey||event.key.toLowerCase()!=='s'||!(event.target instanceof Node)||!workspaceRef.current?.contains(event.target))return;event.preventDefault();if(mode==='edit')void save(true);};window.addEventListener('keydown',shortcut);return()=>window.removeEventListener('keydown',shortcut);},[editor,dirty,busy,stale,base,mode,layoutUnsaved]);
 useLayoutEffect(()=>{if(focused)editor?.commands.focus();},[focused]);
 useEffect(()=>{
   const root=workspaceRef.current;if(!focused||!root)return;
   const siblings:Array<[HTMLElement,boolean]>=[];
   let branch:HTMLElement=root;
   while(branch.parentElement){
     const parent=branch.parentElement;
     for(const sibling of Array.from(parent.children)){if(sibling!==branch&&sibling instanceof HTMLElement){siblings.push([sibling,sibling.inert]);sibling.inert=true;}}
     if(parent===document.body)break;branch=parent;
   }
   return()=>{for(const [node,previous] of siblings)node.inert=previous;};
 },[focused]);
 function leaveFocus(){setFocused(false);requestAnimationFrame(()=>focusButton.current?.focus());}
 function focusKeys(event:ReactKeyboardEvent<HTMLDivElement>){
   if(!focused||!(event.target instanceof HTMLElement)||event.target.closest('dialog[open],[data-popover-panel]'))return;
   if(event.key==='Escape'&&!event.target.matches('select')){event.preventDefault();event.stopPropagation();leaveFocus();return;}
   if(event.key!=='Tab')return;
   const fields=Array.from(workspaceRef.current!.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[contenteditable=true],[tabindex="0"]')).filter(node=>!node.closest('[hidden]')&&node.getBoundingClientRect().width>0&&node.getBoundingClientRect().height>0);
   const first=fields[0],last=fields.at(-1);if(first&&last&&(event.shiftKey&&document.activeElement===first||!event.shiftKey&&document.activeElement===last)){event.preventDefault();(event.shiftKey?last:first).focus();}
 }
 if(!editor)return <p role="status">正在打开文档…</p>;
 function applyTemplate(next:ResumeTemplate){setTemplate(next);try{localStorage.setItem(preference,next);}catch{}setResumeEditorDocument(editor!,resumeDocument(resumeDocumentContent(editor!.getJSON()),editor!.getJSON(),next));}
 function modifySelection(){setSelectionRun(value=>value+1);setSelectionOpen(true);setAiOpen(true);}
 return <div ref={workspaceRef} className={`resume-word-workspace${focused?' is-focused':''}${aiOpen?' assistant-open':''}`} data-browser-overlay={focused?'modal':undefined} data-popover-boundary={focused?'':undefined} role={focused?'dialog':undefined} aria-modal={focused?true:undefined} aria-label={focused?'专注简历编辑':undefined} onKeyDown={focusKeys}>
   <div ref={toolbarRef} className="resume-word-toolbar" aria-label="文档工具栏">
     <div className="resume-word-modes"><button aria-pressed={mode==='edit'} disabled={busy} onClick={()=>setMode('edit')}>编辑</button><button aria-pressed={mode==='preview'} disabled={busy||stale} title={dirty?'保存当前修改并打开分页预览':undefined} onClick={()=>void preview()}>分页预览</button></div>
     <span className={`resume-word-status${dirty?' has-draft':''}`}>{busy?'处理中…':dirty?draftStored?'草稿已存本机':'草稿保存失败':layoutUnsaved?'排版待保存':'已保存'}</span>
     <button disabled={busy} onClick={()=>setTemplatesOpen(true)}>模板与排版</button><button className="resume-assistant-toggle" aria-pressed={aiOpen} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>setAiOpen(value=>!value)}><Icon name="sparkles"/>简历助手</button>
     <PopoverButton title="导出简历" label="导出" disabled={busy||stale} width={240}>{close=><><p className="note">{dirty?'先保存当前修改，再选择导出位置。':'导出当前版本和所选模板。'}</p><button className="status-option" onClick={()=>{close();void exportFile('pdf');}}>PDF · 用于投递</button><button className="status-option" onClick={()=>{close();void exportFile('docx');}}>Word · 继续编辑</button></>}</PopoverButton>
     <button className="primary-button" title="保存修改 · ⌘S / Ctrl+S" disabled={busy||stale||!dirty&&!layoutUnsaved} onClick={()=>void save(true)}>保存</button><button ref={focusButton} className="resume-focus-toggle" title={focused?'退出专注编辑 · Esc':'专注编辑'} aria-label={focused?'退出专注编辑':'专注编辑'} aria-pressed={focused} onClick={()=>focused?leaveFocus():setFocused(true)}><Icon name="expand"/></button>
   </div>
   {templatesOpen&&<ResumeModal title="选择简历模板" onClose={()=>setTemplatesOpen(false)}><div className="resume-template-body"><p className="note">只改变排版，不改动你的经历。导出沿用所选模板。</p><div className="resume-template-gallery">{resumeTemplates.map(t=><button className={`resume-template-card ${t.id}`} key={t.id} aria-pressed={template===t.id} onClick={()=>applyTemplate(t.id)}><span className="resume-template-thumb" aria-hidden="true"><b/><i/><i/><strong/><i/><i/><i/><strong/><i/><i/></span><b>{t.name}</b><small>{t.description}</small></button>)}</div><div className="resume-template-options"><button disabled={dirty} onClick={()=>{setTemplatesOpen(false);onOrganize();}}>调整内容归属</button><span>空章节自动隐藏，可在编辑栏添加。</span></div></div><footer><p>AI 按真实经历提出修改，审阅后保存。</p>{onImprove&&<button disabled={dirty} onClick={()=>{setTemplatesOpen(false);void improve(`按“${resumeTemplates.find(t=>t.id===template)?.name}”模板组织内容；${template==='campus'?'教育、项目与实习优先':template==='compact'?'精简重复表达，保留关键事实':'突出真实工作成果'}。检查错分的章节，将项目与工作内容归回对应章节，不能遗漏原有经历`);}}>✦ AI 生成修改稿</button>}<button className="primary-button" onClick={()=>setTemplatesOpen(false)}>完成</button></footer></ResumeModal>}
   {error&&<p className="notice" role="alert">{error}</p>}{notice&&<p className="resume-feedback" role="status">{notice}</p>}{!draftStored&&<p className="notice" role="alert">本机草稿保存失败，请点击保存，避免丢失修改。</p>}
   {stale&&<p className="notice">基础简历已有新版本，当前草稿保留。请复制需要的内容，再放弃草稿以读取最新版本。</p>}
   {mode==='edit'?<>
     <div ref={formatRef} className="resume-word-format" aria-label="文字格式">
       <div className="resume-format-group" role="group" aria-label="编辑历史"><button title="撤销 · ⌘Z / Ctrl+Z" aria-label="撤销" disabled={busy||!state?.undo} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().undo().run()}><Icon name="undo"/></button><button title="重做 · ⇧⌘Z / Ctrl+Shift+Z" aria-label="重做" disabled={busy||!state?.redo} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().redo().run()}><Icon name="redo"/></button></div>
       <div className="resume-format-group" role="group" aria-label="文字样式">
       <button title="加粗 · ⌘B / Ctrl+B" aria-label="加粗" aria-pressed={state?.bold} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleBold().run()}><b>B</b></button><button title="斜体 · ⌘I / Ctrl+I" aria-label="斜体" aria-pressed={state?.italic} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleItalic().run()}><i>I</i></button><button title="下划线 · ⌘U / Ctrl+U" aria-label="下划线" aria-pressed={state?.underline} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleUnderline().run()}><u>U</u></button>
       <label className="resume-font-size"><select aria-label="字号" disabled={busy} value={state?.textStyle.fontSize||''} onChange={e=>editor.chain().focus().setMark('textStyle',{fontSize:e.target.value?Number(e.target.value):null}).run()}><option value="">字号</option>{[...new Set([8,9,10,11,12,14,16,20,24,Number(state?.textStyle.fontSize)||10])].sort((a,b)=>a-b).map(size=><option key={size} value={size}>{size}</option>)}</select></label>
       <PopoverButton title="文字颜色" label={<span className="resume-color-indicator" style={{borderColor:state?.textStyle.color||'#303944'}}>A</span>} disabled={busy} width={220}>{close=><div className="resume-color-palette" aria-label="文字颜色">{[['#303944','正文'],['#17324d','深蓝'],['#1769aa','蓝色'],['#0f766e','绿色'],['#68717d','灰色'],['#983b3b','红色']].map(([color,name])=><button key={color} aria-label={name} title={name} aria-pressed={state?.textStyle.color===color} style={{background:color}} onMouseDown={e=>e.preventDefault()} onClick={()=>{editor.chain().focus().setMark('textStyle',{color}).run();close();}}/>)}<button className="resume-color-reset" onClick={()=>{editor.chain().focus().setMark('textStyle',{color:null}).run();close();}}>默认颜色</button></div>}</PopoverButton>
       <button title="清除所选文字的样式与段落对齐，保留内容和列表" aria-label="清除格式" disabled={busy||!state||state.selection.empty} onMouseDown={e=>e.preventDefault()} onClick={()=>{editor.commands.focus();clearResumeTextFormatting(editor);}}><Icon name="clearFormat"/></button></div>
       <div className="resume-format-group" role="group" aria-label="段落排版">
       <select className="resume-text-align" aria-label="段落对齐" disabled={busy} value={state?.align||'left'} onChange={e=>editor.chain().focus().updateAttributes('paragraph',{textAlign:e.target.value}).run()}><option value="left">左对齐</option><option value="center">居中</option><option value="right">右对齐</option><option value="justify">两端对齐</option></select>
       <button aria-label="项目符号列表" title="项目符号列表" aria-pressed={state?.bullet} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleBulletList().run()}><Icon name="bulletList"/></button><button aria-label="编号列表" title="编号列表" aria-pressed={state?.ordered} disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>editor.chain().focus().toggleOrderedList().run()}><Icon name="orderedList"/></button></div>
       <button className="resume-selection-trigger" aria-label="修改选中文字" title="修改选中文字" disabled={busy||!state||state.selection.empty} onMouseDown={e=>e.preventDefault()} onClick={modifySelection}><Icon name="sparkles"/></button>
       <button className="resume-sections-toggle" aria-label={showEmpty?'隐藏空章节':'添加章节'} title={showEmpty?'隐藏空章节':'显示空章节以添加内容'} aria-pressed={showEmpty} onClick={()=>setShowEmpty(value=>!value)}><Icon name="add"/></button>

     </div>
     <div className="resume-editor-body"><div className={`resume-word-surface ${template}${showEmpty?' show-empty-sections':''}`}><EditorContent editor={editor}/></div>
       {aiOpen&&<aside className="resume-editor-assistant" aria-label="简历助手"><header><strong><Icon name="sparkles"/>简历助手</strong><button aria-label="关闭简历助手" title="关闭简历助手" onClick={()=>setAiOpen(false)}>×</button></header>
         {selectionOpen?<ResumeSelectionAI key={selectionRun} editor={editor} workspaceId={workspaceId} disabled={busy} onClose={()=>setSelectionOpen(false)}/>:<div className="resume-assistant-home"><p>选中一段文字，先看修改建议，再决定是否替换。</p><button disabled={busy||!state||state.selection.empty} onMouseDown={e=>e.preventDefault()} onClick={modifySelection}><strong>修改选中文字</strong><span>清晰表达、精简内容、纠正措辞</span></button>{state?.selection.empty&&<small>在正文中选中文字后即可使用。</small>}{onImprove&&<button disabled={busy||dirty} onClick={()=>void improve()}><strong>优化整份简历</strong><span>根据真实经历或目标岗位生成修改稿</span></button>}{dirty&&onImprove&&<small>先保存当前修改，再优化整份简历。</small>}<p className="resume-assistant-privacy">点击生成时才发送内容给所选模型，修改由你审阅。</p></div>}
       </aside>}
     </div>
     <div className="resume-word-footer"><span>{state?.characters??editor.state.doc.textContent.replace(/\s/g,'').length} 字 · {dirty?draftStored?'本机草稿，点击保存后用于匹配与投递':'请保存当前修改':layoutUnsaved?'保存当前排版后供投递复用':'修改已保存'} · 导出排版请查看预览</span>{dirty&&<button disabled={busy} onClick={()=>setDiscard(true)}>放弃草稿</button>}</div>
     {discard&&<div className="notice" role="alert">放弃当前未保存的草稿？<button onClick={()=>setDiscard(false)}>继续编辑</button><button disabled={busy} onClick={reset}>放弃草稿并恢复</button></div>}
   </>:<ResumeDocument managedToolbar key={`${base.version_id}:${template}`} workspaceId={workspaceId} version={base} template={template} onTemplateChange={applyTemplate}/>}
 </div>;
}
