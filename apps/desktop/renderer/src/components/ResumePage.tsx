import {useEffect, useState} from "react";
import type {ResumeContent, ResumeDraft, ResumeState, ResumeVersion} from "../../../shared/contracts";

const sections: Array<[keyof ResumeContent,string]> = [
  ["basic_information","基本信息"], ["education","教育经历"],
  ["experience","工作经历"], ["projects","项目经历"], ["skills","专业技能"],
];
const emptyContent = (): ResumeContent => ({basic_information:[],education:[],experience:[],projects:[],skills:[]});
const lines = (value:string) => value.split("\n").map(line=>line.trim()).filter(Boolean);
const errorText = (error:unknown) => String(error instanceof Error ? error.message : error);

export function ResumePage() {
  const [state,setState] = useState<ResumeState>();
  const [versions,setVersions] = useState<ResumeVersion[]>([]);
  const [content,setContent] = useState<ResumeContent>(emptyContent);
  const [accepted,setAccepted] = useState<Set<string>>(new Set());
  const [corrections,setCorrections] = useState<Record<string,string>>({});
  const [viewId,setViewId] = useState("");
  const [hideId,setHideId] = useState("");
  const [editing,setEditing] = useState(false);
  const [template,setTemplate] = useState<"classic"|"compact">("classic");
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState("");
  const [error,setError] = useState("");
  const draft:ResumeDraft|null|undefined = state?.active_draft;
  const current = versions.find(version=>version.is_current);
  const viewed = versions.find(version=>version.version_id===viewId) || current;
  const dirty = !!current && JSON.stringify(content)!==JSON.stringify(current.content);
  async function reload(){
    const next = await window.jobfindsme!.getResumeState();
    setState(next);
    if(next.active_draft){
      setAccepted(new Set(next.active_draft.facts.map(fact=>fact.fact_id)));
      setCorrections(Object.fromEntries(next.active_draft.facts.map(fact=>[fact.fact_id,fact.value])));
    }
    const list = next.workspace_id ? await window.jobfindsme!.listResumeVersions(next.workspace_id) : [];
    setVersions(list);
    setContent(list.find(version=>version.is_current)?.content || emptyContent());
    setViewId(list.find(version=>version.is_current)?.version_id || "");
    setEditing(false);
  }
  useEffect(()=>{let alive=true;void reload().catch(reason=>{if(alive)setError(errorText(reason));});return()=>{alive=false;};},[]);
  async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(reason){setError(errorText(reason));}finally{setBusy(false);}}
  async function importResume(){await run(async()=>{const imported=await window.jobfindsme!.chooseAndImportResume();if(imported){await reload();setMessage("请核对解析内容，确认后才会成为检索使用的当前简历。");}});}
  async function confirm(){if(!draft)return;await run(async()=>{
    await window.jobfindsme!.confirmResume({workspace_id:draft.workspace_id,profile_id:draft.profile_id,accepted_fact_ids:[...accepted],corrections:Object.fromEntries([...accepted].map(id=>[id,corrections[id]??""]))});
    await reload();setMessage("已确认当前简历；下次岗位检索会使用这一版本。");
  });}
  async function save(){if(!state?.workspace_id||!current||!dirty)return;await run(async()=>{
    const value=await window.jobfindsme!.saveResumeVersion({workspace_id:state.workspace_id!,base_version_id:current.version_id,content});
    await reload();setMessage(`已另存为 v${value.version_number}；原文件和旧版本保留。`);
  });}
  async function restore(version:ResumeVersion){if(!state?.workspace_id)return;await run(async()=>{
    const value=await window.jobfindsme!.restoreResumeVersion(state.workspace_id!,version.version_id);
    await reload();setMessage(`已基于 v${version.version_number} 创建当前版本 v${value.version_number}。`);
  });}
  async function hide(version:ResumeVersion){if(!state?.workspace_id||version.is_current)return;await run(async()=>{
    await window.jobfindsme!.hideResumeVersion(state.workspace_id!,version.version_id);
    await reload();setHideId("");setMessage(`v${version.version_number} 已从历史列表移除；本机快照和已有引用保留。`);
  });}
  async function exportFile(format:"pdf"|"docx"|"md"){if(!state?.workspace_id||!viewed)return;await run(async()=>{
    const saved=await window.jobfindsme!.exportResume({workspace_id:state.workspace_id!,version_id:viewed.version_id,format,template});
    if(saved)setMessage(`已导出 v${viewed.version_number} · ${format.toUpperCase()}。`);
  });}
  return <div className="resume-page resume-maintenance">
    <div className="heading-row resume-heading"><div><h1>简历维护</h1><p>导入、核对和维护当前版本；已确认简历参与岗位检索。</p></div><button disabled={busy} onClick={()=>void importResume()}>{current?"替换 / 导入简历":"导入简历"}</button></div>
    {error&&<p className="notice" role="alert">{error}</p>}{message&&<p className="note" role="status">{message}</p>}
    {!current&&!draft&&<section className="panel section resume-empty"><h2>先导入一份简历</h2><p>支持 PDF、DOCX、MD 和 TXT；解析后逐项核对再确认。</p><button className="primary-button" disabled={busy} onClick={()=>void importResume()}>选择文件并解析</button><p className="note">{state?.capabilities.detail||"扫描 PDF 暂不支持 OCR。"}</p></section>}
    {draft&&<section className="panel section resume-confirm"><h2>核对解析结果</h2><p className="note">{draft.file_name} · {draft.facts.length} 条候选事实。未确认内容不会参与检索。</p><div className="fact-list">{draft.facts.map(fact=><label className="fact-row" key={fact.fact_id}><input type="checkbox" checked={accepted.has(fact.fact_id)} onChange={event=>setAccepted(old=>{const next=new Set(old);event.target.checked?next.add(fact.fact_id):next.delete(fact.fact_id);return next;})}/><span>{fact.fact_type}</span><textarea value={corrections[fact.fact_id]??fact.value} disabled={!accepted.has(fact.fact_id)||busy} onChange={event=>setCorrections(old=>({...old,[fact.fact_id]:event.target.value}))}/></label>)}</div><div className="button-row"><button className="primary-button" disabled={busy||!accepted.size} onClick={()=>void confirm()}>确认当前简历</button><button disabled={busy} onClick={()=>void run(async()=>{await window.jobfindsme!.abandonResume(draft.workspace_id,draft.profile_id);await reload();})}>放弃本次导入</button></div></section>}
    {current&&<><section className="panel section resume-current"><div className="heading-row"><div><h2>当前简历 · v{current.version_number}</h2><p className="note">{new Date(current.created_at).toLocaleString()} · 已确认并用于下次岗位检索</p></div><div className="button-row"><button onClick={()=>{setViewId(current.version_id);setEditing(false);}}>查看</button><button className="primary-button" disabled={busy} onClick={()=>{setContent(current.content);setEditing(true);}}>维护内容</button></div></div>
      {editing?<div className="resume-editor">{sections.map(([key,label])=><label className="editor-section" key={key}>{label}<textarea value={content[key].join("\n")} disabled={busy} onChange={event=>setContent(old=>({...old,[key]:lines(event.target.value)}))}/></label>)}<div className="button-row"><button className="primary-button" disabled={busy||!dirty} onClick={()=>void save()}>保存为新版本</button><button disabled={busy} onClick={()=>{setContent(current.content);setEditing(false);}}>取消</button></div><p className="note">每行一条内容；保存前不会改变当前版本，原文件仍保留。</p></div>:<div className="resume-summary">{sections.map(([key,label])=><section key={key}><h3>{label}</h3>{current.content[key].length?current.content[key].map((line,index)=><p key={index}>{line}</p>):<p className="muted">暂无内容</p>}</section>)}</div>}
    </section><details className="panel section resume-history"><summary>版本历史 · {versions.length}</summary><div className="version-list">{versions.map(version=><div key={version.version_id}><span>v{version.version_number} · {new Date(version.created_at).toLocaleString()} {version.is_current&&<em>当前</em>}</span><div className="button-row"><button onClick={()=>setViewId(version.version_id)}>查看</button>{!version.is_current&&<><button disabled={busy} onClick={()=>void restore(version)}>恢复为新版本</button><button disabled={busy} onClick={()=>setHideId(version.version_id)}>移除记录</button></>}</div>{hideId===version.version_id&&<div className="history-confirm" role="alert"><p>从简历历史列表移除 v{version.version_number}？本机快照及已有引用保留，不会物理清除。当前版本不能移除。</p><div className="button-row"><button disabled={busy} onClick={()=>void hide(version)}>确认移除</button><button disabled={busy} onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div><p className="note">恢复会创建新版本；移除只隐藏历史入口，已有搜索和任务引用仍可追溯。当前版本需先切换后才能移除。</p></details><details className="panel section resume-export"><summary>查看与导出已保存版本</summary><label>版本 <select value={viewed?.version_id||""} onChange={event=>setViewId(event.target.value)}>{versions.map(version=><option key={version.version_id} value={version.version_id}>v{version.version_number}{version.is_current?" · 当前":""}</option>)}</select></label><label>排版 <select value={template} onChange={event=>setTemplate(event.target.value as "classic"|"compact")}><option value="classic">经典</option><option value="compact">紧凑</option></select></label><div className={`resume-preview ${template}`}><h2>简历 · v{viewed?.version_number}</h2>{sections.map(([key,label])=><section key={key}><h4>{label}</h4>{viewed?.content[key].map((line,index)=><p key={index}>{line}</p>)}</section>)}</div><div className="button-row">{(["pdf","docx","md"] as const).map(format=><button key={format} disabled={busy} onClick={()=>void exportFile(format)}>导出 {format.toUpperCase()}</button>)}</div></details></>}
  </div>;
}
