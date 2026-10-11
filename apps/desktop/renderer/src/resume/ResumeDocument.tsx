import {useEffect,useRef,useState} from 'react';
import type {PDFDocumentProxy,PDFDocumentLoadingTask,RenderTask} from 'pdfjs-dist/legacy/build/pdf.mjs';
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';
import type {ResumeVersion} from '../../../shared/contracts';
import {resumeSections,resumeTemplates,type ResumeTemplate} from '../../../shared/resume-library';
import {userError} from '../../../shared/user-errors';



function Paper({pdf,number,width,onRetry}:{pdf:PDFDocumentProxy;number:number;width:number;onRetry:()=>void}){
  const canvas=useRef<HTMLCanvasElement>(null),frame=useRef<HTMLElement>(null);
  const [visible,setVisible]=useState(false),[error,setError]=useState('');
  useEffect(()=>{const observer=new IntersectionObserver(entries=>setVisible(entries.some(entry=>entry.isIntersecting)),{rootMargin:'800px'});if(frame.current)observer.observe(frame.current);return()=>observer.disconnect();},[]);
  useEffect(()=>{
    if(!visible)return;
    let cancelled=false,render:RenderTask|undefined;
    setError('');
    void pdf.getPage(number).then(async page=>{
      if(cancelled||!canvas.current)return;
      const ratio=Math.min(window.devicePixelRatio||1,2);
      const viewport=page.getViewport({scale:width/page.getViewport({scale:1}).width*ratio});
      const target=canvas.current;
      target.width=Math.ceil(viewport.width);target.height=Math.ceil(viewport.height);
      target.style.aspectRatio=`${viewport.width} / ${viewport.height}`;
      render=page.render({canvas:target,viewport});
      await render.promise;
    }).catch(reason=>{if(!cancelled){console.warn('PDF preview render:',reason instanceof Error?reason.message:'unknown');setError('此页未能显示，请重新加载预览。');}});
    return()=>{cancelled=true;render?.cancel();};
  },[pdf,number,width,visible]);
  return <figure ref={frame} className="resume-pdf-page" style={{width}}>
    <canvas ref={canvas} aria-label={`简历第 ${number} 页`} role="img"/>
    {error&&<p role="alert">{error} <button onClick={onRetry}>重试</button></p>}
    <figcaption>{number} / {pdf.numPages}</figcaption>
  </figure>;
}

export function ResumeDocument({original,managedToolbar=false,workspaceId,version,template:controlledTemplate,onTemplateChange}:{original?:import("../../../shared/contracts").ResumeSource;managedToolbar?:boolean;workspaceId:string;version:ResumeVersion;template?:ResumeTemplate;onTemplateChange?:(value:ResumeTemplate)=>void}){
  const preference=`jfm.resume.template.${workspaceId}`;
  const [localTemplate,setLocalTemplate]=useState<ResumeTemplate>(()=>{try{const saved=localStorage.getItem(preference);return resumeTemplates.some(t=>t.id===saved)?saved as ResumeTemplate:'professional';}catch{return 'professional';}});
  const template=controlledTemplate??localTemplate;
  function setTemplate(value:ResumeTemplate){setLocalTemplate(value);onTemplateChange?.(value);}
  const [pdf,setPdf]=useState<PDFDocumentProxy>(),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[available,setAvailable]=useState(680),[zoom,setZoom]=useState<'fit'|'actual'>('fit');
  const surface=useRef<HTMLDivElement>(null);
  const width=zoom==='actual'?794:Math.min(794,Math.max(220,available-40));
  useEffect(()=>{const element=surface.current;if(!element)return;const observer=new ResizeObserver(()=>setAvailable(element.clientWidth));observer.observe(element);return()=>observer.disconnect();},[]);
  useEffect(()=>{
    let cancelled=false,loading:PDFDocumentLoadingTask|undefined;
    setPdf(undefined);setError('');setNotice('');
    try{localStorage.setItem(preference,template);}catch{/* Preferences are optional. */}
    void (original?Promise.resolve(Uint8Array.from(atob(original.content_base64),char=>char.charCodeAt(0))):window.jobfindsme!.previewResume({workspace_id:workspaceId,version_id:version.version_id,template})).then(async bytes=>{
      if(cancelled)return;
      const {getDocument,GlobalWorkerOptions}=await import('pdfjs-dist/legacy/build/pdf.mjs');
      if(cancelled)return;
      GlobalWorkerOptions.workerSrc=workerUrl;
      loading=getDocument({data:new Uint8Array(bytes),
        cMapUrl:new URL("pdfjs/cmaps/",document.baseURI).href,
        standardFontDataUrl:new URL("pdfjs/standard_fonts/",document.baseURI).href,
        wasmUrl:new URL("pdfjs/wasm/",document.baseURI).href,
        useWorkerFetch:false,stopAtErrors:true,
      });
      const loaded=await loading.promise;
      if(!cancelled)setPdf(loaded);
    }).catch(reason=>{if(!cancelled)setError(userError(reason).message);});
    return()=>{cancelled=true;void loading?.destroy();};
  },[workspaceId,version.version_id,template,retry,original]);
  async function exportFile(format:'pdf'|'docx'){
    setBusy(true);setNotice('');setError('');
    try{const result=await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:version.version_id,format,template});if(result)setNotice('已导出到所选位置。');}
    catch(reason){setError(userError(reason).message);}finally{setBusy(false);}
  }
  return <div className="resume-document">
    <div className="resume-paper-toolbar">
      {!managedToolbar&&!original&&<div className="resume-paper-templates" aria-label="简历模板">{resumeTemplates.map(t=><button key={t.id} disabled={busy} aria-pressed={template===t.id} title={t.description} onClick={()=>setTemplate(t.id)}>{t.name}</button>)}</div>}
      <span className="resume-paper-meta">{original?'原文件':'A4'}{pdf?` · ${pdf.numPages} 页`:''}</span>
      <button disabled={busy} title={zoom==='fit'?'按实际纸张宽度显示':'适合窗口宽度'} onClick={()=>setZoom(zoom==='fit'?'actual':'fit')}>{zoom==='fit'?'100%':'适合宽度'}</button>
      {!managedToolbar&&!original&&<div className="resume-paper-download"><button disabled={busy} onClick={()=>void exportFile('docx')}>Word</button><button disabled={busy||!pdf} onClick={()=>void exportFile('pdf')}>{busy?'导出中…':'导出 PDF'}</button></div>}
    </div>
    {error&&<p className="notice" role="alert">{error} <button onClick={()=>setRetry(value=>value+1)}>重新加载</button></p>}
    {notice&&<p className="resume-feedback" role="status">{notice}</p>}
    <div ref={surface} className="resume-paper-surface" aria-label="连续分页简历">
      {!pdf&&!error&&<p className="resume-preview-loading" role="status">正在加载页面…</p>}
      {pdf&&Array.from({length:pdf.numPages},(_,index)=><Paper key={`${version.version_id}:${template}:${retry}:${index}`} pdf={pdf} number={index+1} width={width} onRetry={()=>setRetry(value=>value+1)}/>)}
    </div>
    {!original&&<details className="resume-text-access"><summary>查看可复制文本</summary>{Object.entries(resumeSections).map(([key,label])=><section key={key}><h3>{label}</h3>{version.content[key as keyof typeof version.content].map((line,i)=><p key={i}>{line}</p>)}</section>)}</details>}
  </div>;
}
