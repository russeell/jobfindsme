import {useEffect,useId,useRef,useState,type ReactNode} from 'react';
import type {ResumeVersion,SearchResultItem} from '../../../shared/contracts';
import {resumeSections,resumeTemplates,resumeTemplateSections,type ResumeTemplate} from '../../../shared/resume-library';
import {userError} from '../../../shared/user-errors';

type Job=SearchResultItem['job'];
export function ResumeModal({title,children,onClose,busy=false,wide=false}:{title:string;children:ReactNode;onClose():void;busy?:boolean;wide?:boolean}){
  const ref=useRef<HTMLDialogElement>(null),id=useId();
  useEffect(()=>{const previous=document.activeElement as HTMLElement|null;ref.current?.showModal();return()=>{ref.current?.close();if(previous?.isConnected)previous.focus();};},[]);
  return <dialog ref={ref} className={`resume-modal${wide?' resume-modal-wide':''}`} aria-labelledby={id} onCancel={e=>{e.preventDefault();if(!busy)onClose();}} onClick={e=>{if(e.target===e.currentTarget&&!busy)onClose();}}>
    <div className="resume-modal-shell"><header><h2 id={id}>{title}</h2><button type="button" className="resume-icon-close" aria-label={`关闭${title}`} disabled={busy} onClick={onClose}>×</button></header>{children}</div>
  </dialog>;
}

export function ResumePreview({workspaceId,version,onClose}:{workspaceId:string;version:ResumeVersion;onClose():void}){
  const preference=`jfm.resume.template.${workspaceId}`;
  const [template,setTemplate]=useState<ResumeTemplate>(()=>{try{const saved=localStorage.getItem(preference);return resumeTemplates.some(item=>item.id===saved)?saved as ResumeTemplate:'professional';}catch{return 'professional';}});
  const previewScroll=useRef<HTMLDivElement>(null);
  useEffect(()=>{previewScroll.current?.scrollTo({top:0});try{localStorage.setItem(preference,template);}catch{/* Export remains available without local preferences. */}},[template,preference]);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  async function exportFile(format:'pdf'|'docx'){
    setBusy(true);setNotice('');setError('');
    try{const result=await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:version.version_id,format,template});if(result)setNotice('已导出到所选位置。');}
    catch(e){setError(userError(e).message);}finally{setBusy(false);}
  }
  return <ResumeModal title={`简历预览 · v${version.version_number}`} onClose={onClose} busy={busy} wide>
    <div className="resume-preview-tools"><div className="resume-template-picker" aria-label="简历模板">{resumeTemplates.map(item=><button key={item.id} disabled={busy} aria-pressed={template===item.id} onClick={()=>setTemplate(item.id)}><strong>{item.name}</strong><small>{item.description}</small></button>)}</div><div className="resume-export-actions"><span>切换模板只调整排版，保留全部经历。</span><button disabled={busy} onClick={()=>void exportFile('docx')}>Word</button><button className="primary-button" disabled={busy} onClick={()=>void exportFile('pdf')}>导出 PDF</button></div></div>
    {error&&<p className="notice" role="alert">{error}</p>}{notice&&<p className="resume-feedback" role="status">{notice}</p>}
    <div ref={previewScroll} className="resume-preview-scroll"><article className={`resume-paper ${template}`} aria-label="简历内容预览">{resumeTemplateSections(template).map(key=>version.content[key as keyof typeof version.content].some(line=>line.trim())&&<section key={key}><h3>{resumeSections[key]}</h3>{version.content[key as keyof typeof version.content].filter(line=>line.trim()).map((line,i)=><p key={i}>{line}</p>)}</section>)}</article></div>
  </ResumeModal>;
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
