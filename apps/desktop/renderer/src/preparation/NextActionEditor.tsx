import {useEffect,useRef,useState} from 'react';
import type {TrackedJob} from '../../../shared/contracts';
import {reminderDay} from '../../../shared/job-follow-up';

type Props={item:TrackedJob;busy:boolean;error:string;onSave(action:string,date:string|null):Promise<boolean>;onClose():void};
export function NextActionEditor({item,busy,error,onSave,onClose}:Props){
 const dialog=useRef<HTMLDialogElement>(null);
 const [action,setAction]=useState(item.preparation?.next_action||'');
 const [date,setDate]=useState(item.preparation?.due_date||'');
 const [confirmClose,setConfirmClose]=useState(false);
 const dirty=action!==(item.preparation?.next_action||'')||date!==(item.preparation?.due_date||'');
 useEffect(()=>{const previous=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();if(previous?.isConnected)previous.focus();};},[]);
 function close(){if(busy)return;if(dirty)setConfirmClose(true);else onClose();}
 async function save(){if(busy||!dirty)return;if(await onSave(action.trim(),action.trim()?date||null:null))onClose();}
 return <dialog ref={dialog} className="next-action-dialog" aria-labelledby="next-action-title" onCancel={event=>{event.preventDefault();close();}} onClick={event=>{if(event.target===event.currentTarget)close();}}>
  <form onSubmit={event=>{event.preventDefault();void save();}}>
   <header><div><h2 id="next-action-title">{item.preparation?.next_action?'编辑下一步':'安排下一步'}</h2><p>{item.job.company} · {item.job.title}</p></div><button type="button" aria-label="关闭下一步编辑" disabled={busy} onClick={close}>×</button></header>
   <label>下一步<input autoFocus aria-label="下一步事项" maxLength={200} value={action} disabled={busy} placeholder="例如：准备项目介绍、周五跟进回复" onChange={event=>{setAction(event.target.value);setConfirmClose(false);}}/></label>
   <div className="next-action-presets" aria-label="常用下一步">{['修改简历','准备面试','跟进投递'].map(value=><button key={value} type="button" disabled={busy} aria-pressed={action===value} onClick={()=>{setAction(value);setConfirmClose(false);}}>{value}</button>)}</div>
   <label>日期<span className="note">可选</span><input type="date" aria-label="下一步日期" value={date} disabled={busy||!action.trim()} onChange={event=>{setDate(event.target.value);setConfirmClose(false);}}/></label>
   <div className="next-action-presets" aria-label="快捷日期">{[['今天',0],['明天',1],['三天后',3]].map(([label,offset])=><button type="button" key={label} disabled={busy||!action.trim()} aria-pressed={date===reminderDay(Number(offset))} onClick={()=>{setDate(reminderDay(Number(offset)));setConfirmClose(false);}}>{label}</button>)}<button type="button" disabled={busy||!date} onClick={()=>{setDate('');setConfirmClose(false);}}>不设日期</button></div>
   <p className="note">设置日期后会出现在今日待办；完成后可撤销。</p>
   {error&&<p className="preparation-error" role="alert">{error} 关闭后重新打开，可读取最新记录。</p>}
   {confirmClose?<footer className="next-action-leave" role="alert"><span>修改尚未保存</span><button type="button" onClick={()=>setConfirmClose(false)}>继续编辑</button><button type="button" className="danger-button" onClick={onClose}>放弃修改</button></footer>:<footer>{item.preparation?.next_action&&<button type="button" disabled={busy} onClick={()=>{setAction('');setDate('');}}>清除下一步</button>}<button type="button" disabled={busy} onClick={close}>取消</button><button type="submit" className="primary-button" disabled={busy||!dirty||!item.preparation?.next_action&&!action.trim()}>{busy?'保存中…':'保存'}</button></footer>}
  </form>
 </dialog>;
}
