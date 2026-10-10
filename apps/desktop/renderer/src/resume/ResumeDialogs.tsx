import {useEffect,useId,useRef,useState,type ReactNode} from 'react';
import type {ResumeVersion,SearchResultItem} from '../../../shared/contracts';
import {ResumeDocument} from "./ResumeDocument";

type Job=SearchResultItem['job'];
export function ResumeModal({title,children,onClose,busy=false,wide=false}:{title:string;children:ReactNode;onClose():void;busy?:boolean;wide?:boolean}){
  const ref=useRef<HTMLDialogElement>(null),id=useId();
  useEffect(()=>{const previous=document.activeElement as HTMLElement|null;ref.current?.showModal();return()=>{ref.current?.close();if(previous?.isConnected)previous.focus();};},[]);
  return <dialog ref={ref} className={`resume-modal${wide?' resume-modal-wide':''}`} aria-labelledby={id} onCancel={e=>{e.preventDefault();if(!busy)onClose();}} onClick={e=>{if(e.target===e.currentTarget&&!busy)onClose();}}>
    <div className="resume-modal-shell"><header><h2 id={id}>{title}</h2><button type="button" className="resume-icon-close" aria-label={`关闭${title}`} disabled={busy} onClick={onClose}>×</button></header>{children}</div>
  </dialog>;
}

export function ResumePreview({workspaceId,version,onClose}:{workspaceId:string;version:ResumeVersion;onClose():void}){
  return <ResumeModal title={`简历预览 · v${version.version_number}`} onClose={onClose} wide><div className="resume-preview-scroll"><ResumeDocument workspaceId={workspaceId} version={version}/></div></ResumeModal>;
}

export function ResumeImproveDialog({jobs,onClose,onStart,initialTarget='general'}:{jobs:Job[];initialTarget?:'general'|'job';onClose():void;onStart(job:Job|undefined,instruction:string):void}){
  const [target,setTarget]=useState<'general'|'job'>(initialTarget),[query,setQuery]=useState(''),[selected,setSelected]=useState(''),[instruction,setInstruction]=useState(''),[audience,setAudience]=useState('通用');
  const job=jobs.find(item=>item.job_id===selected);
  const matches=jobs.filter(item=>`${item.title} ${item.company}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())).slice(0,8);
  return <ResumeModal title="AI 修改简历" onClose={onClose}>
    <div className="resume-improve-body"><p className="note">以已确认的基础简历为依据，每项修改由你审阅。</p>
      <div className="resume-choice" aria-label="修改目标"><button aria-pressed={target==='general'} onClick={()=>setTarget('general')}>通用优化</button><button aria-pressed={target==='job'} onClick={()=>setTarget('job')}>针对岗位</button></div>
      {target==='job'&&<div className="resume-job-picker"><input autoFocus aria-label="搜索目标岗位" placeholder="搜索已有岗位或公司" value={query} onChange={e=>setQuery(e.target.value)}/><div className="resume-job-options">{matches.map(item=><button key={item.job_id} aria-pressed={selected===item.job_id} onClick={()=>setSelected(item.job_id)}><strong>{item.title}</strong><small>{item.company} · {item.locations.join(' / ')||'地点未知'}</small></button>)}{!matches.length&&<p className="note">{jobs.length?'没有匹配的已有岗位，换个关键词试试。':'还没有岗位。可以先通用优化，或去找工作保存目标。'}</p>}</div>{job&&<p className="note">已选：{job.company} · {job.title}</p>}</div>}
      <div className="resume-audience"><span>求职阶段</span>{['通用','校招','社招'].map(value=><button key={value} aria-pressed={audience===value} onClick={()=>setAudience(value)}>{value}</button>)}</div>
      <div className="resume-quick-prompts" aria-label="常用修改要求">{['精简表达','突出个人贡献','梳理项目重点'].map(value=><button key={value} onClick={()=>setInstruction(value)}>{value}</button>)}</div>
      <label className="resume-improve-request">想重点改什么？<span>可选</span><textarea aria-label="简历修改要求" maxLength={1200} placeholder="例如：精简项目描述，让个人贡献更清楚" value={instruction} onChange={e=>setInstruction(e.target.value)}/></label>
    </div><footer><p>下一步确认模型与提问，发送后生成修改。</p><button className="primary-button" disabled={target==='job'&&!job} onClick={()=>onStart(target==='job'?job:undefined,[audience==='校招'?'按校招方向组织教育、项目和实习，缺少工作经历不编造':audience==='社招'?'按社招方向突出真实工作成果和个人职责':'',instruction].filter(Boolean).join('；'))}>前往修改 →</button></footer>
  </ResumeModal>;
}
