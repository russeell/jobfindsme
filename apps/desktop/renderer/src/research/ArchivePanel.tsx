import {useEffect,useRef,useState} from 'react';
import type {SavedResearchChat} from '../../../shared/research-chat-history';
import {userError} from '../../../shared/user-errors';
import {Icon} from '../shared/Icon';

type Props={items:SavedResearchChat[];disabled:boolean;onChange(ids:string[],action:'restore'|'delete'):Promise<{succeeded:string[];failed:number}>};
export function ArchivePanel({items,disabled,onChange}:Props){
 const [selected,setSelected]=useState<string[]>([]),[confirm,setConfirm]=useState<string[]>([]),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const lock=useRef(false),all=useRef<HTMLInputElement>(null);
 useEffect(()=>{const ids=new Set(items.map(x=>x.id));setSelected(old=>old.filter(id=>ids.has(id)));setConfirm(old=>old.filter(id=>ids.has(id)));},[items]);
 useEffect(()=>{if(all.current)all.current.indeterminate=selected.length>0&&selected.length<items.length;},[selected.length,items.length]);
 async function act(ids:string[],action:'restore'|'delete'){
  if(lock.current||disabled||!ids.length)return;lock.current=true;setBusy(true);setNotice('');setConfirm([]);
  try{const result=await onChange(ids,action);setSelected(old=>old.filter(id=>!result.succeeded.includes(id)));setNotice(`${action==='restore'?'已恢复':'已删除'} ${result.succeeded.length} 条对话${result.failed?`，${result.failed} 条未完成，请重试。`:'。'}`);}catch(e){setNotice(userError(e).message);}finally{lock.current=false;setBusy(false);}
 }
 const blocked=busy||disabled;
 return <div className="research-archive-settings"><div className="heading-row settings-heading"><div><h1>对话归档</h1><p>找回需要的对话，清理不再保留的记录。</p></div><span className="settings-count">{items.length} 条对话</span></div>
 {items.length>0&&<div className="archive-toolbar"><label><input ref={all} type="checkbox" aria-label="全选归档对话" checked={selected.length===items.length} disabled={blocked} onChange={e=>{setSelected(e.target.checked?items.map(x=>x.id):[]);setConfirm([]);}}/>全选{selected.length>0&&<span> · 已选 {selected.length}</span>}</label><div className="button-row"><button disabled={blocked||!selected.length} onClick={()=>void act([...selected],'restore')}>恢复所选</button><button disabled={blocked||!selected.length} onClick={()=>setConfirm([...selected])}>删除所选</button></div></div>}
 {confirm.length>0&&<div className="archive-confirm" role="alert"><div><strong>永久删除这 {confirm.length} 条对话？</strong><p>对话内容无法恢复。其余对话和简历不受影响。</p></div><div className="button-row"><button disabled={blocked} onClick={()=>setConfirm([])}>取消</button><button className="danger-button" disabled={blocked} onClick={()=>void act(confirm,'delete')}>确认删除 {confirm.length} 条</button></div></div>}
 {notice&&<p role="status" className="note">{notice}</p>}{busy&&<p role="status" className="note">正在处理所选对话…</p>}
 {items.length?<div className="research-archive-list">{items.map(item=><div className={`research-archive-item${selected.includes(item.id)?' is-selected':''}`} key={item.id}><input type="checkbox" aria-label={`选择归档对话：${item.title}`} disabled={blocked} checked={selected.includes(item.id)} onChange={e=>{setConfirm([]);setSelected(old=>e.target.checked?[...old,item.id]:old.filter(id=>id!==item.id));}}/><div className="research-archive-info"><strong title={item.title}>{item.title}</strong><time>{new Date(item.updatedAt).toLocaleString('zh-CN',{year:'numeric',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'})}</time></div><div className="button-row research-archive-actions"><button disabled={blocked} onClick={()=>void act([item.id],'restore')}>恢复</button><button className="archive-delete" aria-label={`删除归档对话：${item.title}`} disabled={blocked} onClick={()=>setConfirm([item.id])}><Icon name="trash"/></button></div></div>)}</div>:<div className="archive-empty">没有归档对话</div>}</div>;
}
