import {useEffect,useState} from 'react';
import type {ResumeSource,ResumeVersion} from '../../../shared/contracts';
import {userError} from '../../../shared/user-errors';
import {ResumeDocument} from './ResumeDocument';

export function ResumeOriginal({workspaceId,documentId,version,onEdit,onImprove}:{workspaceId:string;documentId:string;version?:ResumeVersion;onEdit?:()=>void;onImprove?:()=>void}){
  const [source,setSource]=useState<ResumeSource>(),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[retry,setRetry]=useState(0);
  useEffect(()=>{let alive=true;setSource(undefined);setError('');void window.jobfindsme!.resumeSource({workspace_id:workspaceId,document_id:documentId}).then(value=>{if(alive)setSource(value);}).catch(reason=>{if(alive)setError(userError(reason).message);});return()=>{alive=false;};},[workspaceId,documentId,retry]);
  const indexed=version&&Object.values(version.content).some(lines=>lines.length);
  const displayVersion=version??{version_id:documentId,parent_version_id:null,version_number:0,content:{basic_information:[],education:[],experience:[],projects:[],skills:[]},is_current:false,created_at:''};
  async function download(){setBusy(true);setError('');try{if(await window.jobfindsme!.exportResumeSource({workspace_id:workspaceId,document_id:documentId}))setNotice('原文件已保存。');}catch(reason){setError(userError(reason).message);}finally{setBusy(false);}}
  return <section className="resume-original">
    <header className="resume-document-bar"><div><strong>{source?.file_name||'原始简历'}</strong><small>{version?`v${version.version_number} · `:''}原文件保留</small></div><div className="button-row"><button disabled={!source||busy} onClick={()=>void download()}>下载原文件</button>{onEdit&&<button disabled={!source} onClick={onEdit}>编辑副本</button>}{onImprove&&<button className="primary-button" disabled={!source||!indexed} onClick={onImprove}>AI 修改</button>}</div></header>
    {version&&<p className="note">{indexed?'已在本机提取文字，用于岗位匹配和面试准备；原文件未改动。':'原文件已保存，但未提取到可用文字。可继续按关键词找工作；AI 准备需要文字版简历。'}</p>}
    {error&&<p role="alert" className="notice">{error} <button onClick={()=>setRetry(value=>value+1)}>重试</button></p>}{notice&&<p role="status">{notice}</p>}
    {!source&&!error&&<p role="status">正在读取原文件…</p>}
    {source&&(source.media_type==='application/pdf'?<ResumeDocument original={source} workspaceId={workspaceId} version={displayVersion}/>:<><p className="note">文字预览 · 下载保留原始文件格式和版式。</p><pre className="resume-original-text">{source.text||'此文件没有可显示的文字。'}</pre></>)}
  </section>;
}
