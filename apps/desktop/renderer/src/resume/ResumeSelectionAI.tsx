import {useEffect,useRef,useState} from 'react';
import type {Editor} from '@tiptap/react';
import type {ModelConnection} from '../../../shared/contracts';
import {getCurrentModel} from '../settings/current-model';
import {userError} from '../../../shared/user-errors';
import {resumeParagraph} from '../../../shared/resume-document';

export function ResumeSelectionAI({editor,workspaceId,disabled,onClose}:{editor:Editor;workspaceId:string;disabled:boolean;onClose():void}){
 const [selection]=useState(()=>{const {from,to}=editor.state.selection;return {from,to,text:editor.state.doc.textBetween(from,to,'\n'),document:JSON.stringify(editor.getJSON())};});
 const [models,setModels]=useState<ModelConnection[]>([]),[model,setModel]=useState(''),[action,setAction]=useState<'resume_rewrite'|'resume_shorten'|'resume_proofread'>('resume_rewrite');
 const [suggestion,setSuggestion]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[stale,setStale]=useState(false);
 const request=useRef(''),alive=useRef(true);
 useEffect(()=>{const update=()=>setStale(JSON.stringify(editor.getJSON())!==selection.document);editor.on('update',update);return()=>{editor.off('update',update);};},[editor]);
 useEffect(()=>{alive.current=true;void window.jobfindsme!.listModelConnections().then(rows=>{if(!alive.current)return;const verified=rows.filter(m=>m.status==='verified');setModels(verified);setModel(verified.find(m=>m.connection_id===getCurrentModel(workspaceId))?.connection_id||verified[0]?.connection_id||'');}).catch(e=>{if(alive.current)setError(userError(e).message);});return()=>{alive.current=false;if(request.current)void window.jobfindsme!.cancelGreeting(request.current);};},[]);
 async function generate(){if(busy||!model)return;const id=crypto.randomUUID();request.current=id;setBusy(true);setError('');setSuggestion('');try{const result=await window.jobfindsme!.polishGreeting({requestId:id,connectionId:model,message:selection.text,purpose:action});if(alive.current&&request.current===id)setSuggestion(result);}catch(e){if(alive.current)setError(userError(e).message);}finally{request.current='';if(alive.current)setBusy(false);}}
 function accept(){if(stale||disabled)return;const marks=editor.state.doc.resolve(selection.from).marks().map(m=>m.toJSON());editor.chain().focus().insertContentAt({from:selection.from,to:selection.to},resumeParagraph(suggestion,marks).content||[]).run();onClose();}
 const invalid=!selection.text.trim()||selection.text.length>3000||editor.state.doc.resolve(selection.from).parent!==editor.state.doc.resolve(selection.to).parent;
 return <aside className="resume-selection-ai" aria-label="AI 修改选中文字"><header><strong>✦ 修改选中文字</strong><button aria-label="关闭选段修改" onClick={onClose}>×</button></header><p>仅发送选中内容给所选模型，可能产生费用；生成后由你决定是否替换。</p><blockquote>{selection.text}</blockquote>
   <div className="button-row"><select aria-label="修改方式" disabled={busy} value={action} onChange={e=>setAction(e.target.value as typeof action)}><option value="resume_rewrite">清晰表达</option><option value="resume_shorten">精简表达</option><option value="resume_proofread">纠正措辞</option></select><select aria-label="简历选段模型" value={model} disabled={busy} onChange={e=>setModel(e.target.value)}><option value="">选择模型</option>{models.map(m=><option key={m.connection_id} value={m.connection_id}>{m.provider} · {m.model_id}</option>)}</select><button disabled={disabled||busy||stale||invalid||!model} onClick={()=>void generate()}>生成建议</button>{busy&&<button onClick={()=>void window.jobfindsme!.cancelGreeting(request.current)}>停止</button>}</div>
   {invalid&&<p>请在同一段落内选择 1–3000 个字符；整份优化可使用上方“AI 修改”。</p>}{!models.length&&<p>请先在模型设置中添加并测试连接，仍可直接编辑文档。</p>}
   {suggestion&&<><label>建议稿<textarea aria-label="简历选段建议稿" value={suggestion} onChange={e=>setSuggestion(e.target.value)} maxLength={3000}/></label><div className="button-row"><button disabled={disabled||stale||!suggestion.trim()} onClick={accept}>替换选中文字</button><button onClick={onClose}>保留原文</button></div></>}
   {stale&&<p role="status">文档已有修改，请关闭后重新选择文字，避免覆盖新的编辑。</p>}{error&&<p role="alert">{error}</p>}
 </aside>;
}
