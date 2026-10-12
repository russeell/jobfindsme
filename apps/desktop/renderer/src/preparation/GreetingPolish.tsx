import {useEffect,useRef,useState} from 'react';
import type {GreetingTarget,ModelConnection} from '../../../shared/contracts';
import {userError} from '../../../shared/user-errors';
import {getCurrentModel} from '../settings/current-model';

export function GreetingPolish({workspaceId,value,target,disabled,onAccept,onBusy}:{workspaceId:string;value:string;target?:GreetingTarget;disabled:boolean;onAccept(value:string):void;onBusy(value:boolean):void}){
 const [models,setModels]=useState<ModelConnection[]>([]),[model,setModel]=useState(''),[options,setOptions]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [style,setStyle]=useState<'natural'|'concise'|'direct'>('natural');
 const [undo,setUndo]=useState<{before:string;after:string}>();
 const request=useRef(''),alive=useRef(true),latest=useRef(value);latest.current=value;
 useEffect(()=>{alive.current=true;void window.jobfindsme!.listModelConnections().then(rows=>{if(!alive.current)return;const verified=rows.filter(x=>x.status==='verified');setModels(verified);const current=getCurrentModel(workspaceId);setModel(verified.find(x=>x.connection_id===current)?.connection_id||verified[0]?.connection_id||'');}).catch(()=>{if(alive.current)setError('模型列表读取失败，请关闭材料后重试。');});return()=>{alive.current=false;if(request.current)void window.jobfindsme!.cancelGreeting(request.current);};},[workspaceId]);
 async function generate(){
  if(request.current||disabled||!value.trim())return;
  if(!model){setOptions(true);setError('请先在设置中添加并测试模型。');return;}
  const id=crypto.randomUUID(),before=value;request.current=id;setBusy(true);onBusy(true);setError('');setOptions(false);
  try{
   const result=await window.jobfindsme!.polishGreeting({requestId:id,connectionId:model,message:before,style,target});
   if(alive.current&&request.current===id){
    if(latest.current!==before){setError('文字已修改，请重新润色。');return;}
    setUndo({before,after:result});onAccept(result);
   }
  }catch(e){if(alive.current&&request.current===id)setError(userError(e).message);}
  finally{if(request.current===id)request.current='';if(alive.current){setBusy(false);onBusy(false);}}
 }
 return <div className="greeting-polish greeting-inline">
  <div className="greeting-inline-actions"><button type="button" disabled={disabled||busy||!value.trim()} onClick={()=>void generate()}>{busy?'正在润色…':'✦ AI 润色'}</button>
   {busy?<button type="button" onClick={()=>void window.jobfindsme!.cancelGreeting(request.current)}>停止</button>:<button type="button" className="greeting-options-toggle" aria-label="AI 润色设置" aria-expanded={options} title="润色方向与模型" onClick={()=>setOptions(v=>!v)} disabled={disabled}>⌄</button>}
   {undo&&value===undo.after&&!busy&&<button type="button" disabled={disabled} onClick={()=>{onAccept(undo.before);setUndo(undefined);setError('');}}>撤销润色</button>}
   <span className="note">{target?(target.resumeVersionId?'使用岗位与所选简历的脱敏经历':'使用当前岗位'):'仅使用当前话术'} · 按模型计费</span>
  </div>
  {options&&<div className="greeting-inline-options"><select aria-label="润色方向" value={style} onChange={e=>setStyle(e.target.value as typeof style)} disabled={busy}><option value="natural">自然表达</option><option value="concise">更简洁</option><option value="direct">更直接</option></select><select aria-label="招呼语润色模型" value={model} disabled={busy} onChange={e=>setModel(e.target.value)}><option value="">选择模型</option>{models.map(m=><option key={m.connection_id} value={m.connection_id}>{m.provider} · {m.model_id}</option>)}</select></div>}
  {undo&&value===undo.after&&<p role="status" className="note">已润色，可直接编辑或撤销。</p>}
  {error&&<p role="alert" className="greeting-error">{error}</p>}
 </div>;
}
