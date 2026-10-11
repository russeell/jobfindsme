import {ResumeOriginal} from "./ResumeOriginal";
import {useEffect,useId,useRef,useState,type ReactNode} from 'react';
import {getCurrentModel,setCurrentModel} from '../settings/current-model';
import type {ModelConnection,ResumeVersion,SearchResultItem} from '../../../shared/contracts';
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
  return <ResumeModal title={`简历预览 · v${version.version_number}`} onClose={onClose} wide><div className="resume-preview-scroll">{version.original_file&&version.source_document_id?<ResumeOriginal workspaceId={workspaceId} documentId={version.source_document_id} version={version}/>:<ResumeDocument workspaceId={workspaceId} version={version}/>}</div></ResumeModal>;
}

export function ResumeImproveDialog({jobs,onClose,onStart,workspaceId,initialTarget='general',initialInstruction='',initialJob}:{workspaceId:string;jobs:Job[];initialJob?:Job;initialInstruction?:string;initialTarget?:'general'|'job';onClose():void;onStart(job:Job|undefined,instruction:string,connectionId?:string):void}){
  const [target,setTarget]=useState<'general'|'job'>(initialTarget),[query,setQuery]=useState(''),[selected,setSelected]=useState(initialJob?.job_id||''),[instruction,setInstruction]=useState(initialInstruction);
  const [models,setModels]=useState<ModelConnection[]>([]),[model,setModel]=useState(''),[modelError,setModelError]=useState(''),[loadingModels,setLoadingModels]=useState(true);
  useEffect(()=>{let alive=true;void window.jobfindsme!.listModelConnections().then(rows=>{if(!alive)return;const valid=rows.filter(m=>m.status==='verified');setModels(valid);setModel(valid.find(m=>m.connection_id===getCurrentModel(workspaceId))?.connection_id||valid[0]?.connection_id||'');}).catch(()=>{if(alive)setModelError('模型列表读取失败，请关闭后重试。');}).finally(()=>{if(alive)setLoadingModels(false);});return()=>{alive=false;};},[workspaceId]);
  const candidates=initialJob?[initialJob,...jobs.filter(item=>item.job_id!==initialJob.job_id)]:jobs;
  const job=candidates.find(item=>item.job_id===selected);
  const matches=candidates.filter(item=>`${item.title} ${item.company}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())).slice(0,8);
  return <ResumeModal title="AI 修改简历" onClose={onClose}>
    <div className="resume-improve-body"><p className="note">以已确认的基础简历为依据，每项修改由你审阅。</p>
      <div className="resume-choice" aria-label="修改目标"><button aria-pressed={target==='general'} onClick={()=>setTarget('general')}>通用优化</button><button aria-pressed={target==='job'} onClick={()=>setTarget('job')}>针对岗位</button></div>
      {target==='job'&&<div className="resume-job-picker"><input autoFocus aria-label="搜索目标岗位" placeholder="搜索已有岗位或公司" value={query} onChange={e=>setQuery(e.target.value)}/><div className="resume-job-options">{matches.map(item=><button key={item.job_id} aria-pressed={selected===item.job_id} onClick={()=>setSelected(item.job_id)}><strong>{item.title}</strong><small>{item.company} · {item.locations.join(' / ')||'地点未知'}</small></button>)}{!matches.length&&<p className="note">{jobs.length?'没有匹配的已有岗位，换个关键词试试。':'还没有岗位。可以先通用优化，或去找工作保存目标。'}</p>}</div>{job&&<p className="note">已选：{job.company} · {job.title}</p>}</div>}

      <div className="resume-quick-prompts" aria-label="常用修改要求">{['精简表达','突出个人贡献','梳理项目重点'].map(value=><button key={value} onClick={()=>setInstruction(value)}>{value}</button>)}</div>
      <label className="resume-improve-request">想重点改什么？<span>可选</span><textarea aria-label="简历修改要求" maxLength={1200} placeholder="例如：精简项目描述，让个人贡献更清楚" value={instruction} onChange={e=>setInstruction(e.target.value)}/></label>
    <p className="note" role="status">{loadingModels?'正在读取模型…':modelError||(!models.length?'没有可用模型，请先到设置中添加并测试连接。':'生成和审阅都在本页完成。')}</p><label className="resume-improve-request">生成模型<select aria-label="简历生成模型" value={model} onChange={e=>setModel(e.target.value)}><option value="">选择已测试模型</option>{models.map(m=><option key={m.connection_id} value={m.connection_id}>{m.provider} · {m.model_id}</option>)}</select></label></div><footer><p>点击后发送已确认简历的脱敏经历给所选模型，按模型计费；修改需审阅，不覆盖原稿。</p><button className="primary-button" disabled={!model||target==='job'&&!job} onClick={()=>{setCurrentModel(workspaceId,model);onStart(target==='job'?job:undefined,instruction,model);}}>生成修改稿 →</button></footer>
  </ResumeModal>;
}
