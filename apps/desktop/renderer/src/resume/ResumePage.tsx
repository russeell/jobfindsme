import {useEffect,useState} from "react";
import type {ResumeDraft,ResumeState,ResumeVersion,SearchPreferences} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";

const factLabels:Record<string,string>={skill:"专业技能",project:"项目经历",experience:"工作经历",education:"教育经历"};
const blank=(workspace_id:string):SearchPreferences=>({workspace_id,target_role:"",cities:[],salary_min_k:null,salary_max_k:null});

export function ResumePage(){
  const [state,setState]=useState<ResumeState>();
  const [current,setCurrent]=useState<ResumeVersion>();
  const [preferences,setPreferences]=useState<SearchPreferences>();
  const [cityText,setCityText]=useState("");
  const [accepted,setAccepted]=useState<Set<string>>(new Set());
  const [corrections,setCorrections]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[confirmClear,setConfirmClear]=useState(false);
  const draft:ResumeDraft|null|undefined=state?.active_draft;
  async function reload(){
    const next=await window.jobfindsme!.getResumeState();setState(next);
    if(next.active_draft){setAccepted(new Set(next.active_draft.facts.map(f=>f.fact_id)));setCorrections(Object.fromEntries(next.active_draft.facts.map(f=>[f.fact_id,f.value])));}
    const workspace=next.workspace_id;
    const versions=workspace?await window.jobfindsme!.listResumeVersions(workspace):[];
    setCurrent(versions.find(version=>version.is_current));
    if(workspace){const saved=await window.jobfindsme!.getSearchPreferences(workspace);setPreferences(saved);setCityText(saved.cities.join("、"));}
  }
  useEffect(()=>{void reload().catch(reason=>setError(userError(reason).message));},[]);
  async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(reason){setError(userError(reason).message);}finally{setBusy(false);}}
  async function importResume(){await run(async()=>{const value=await window.jobfindsme!.chooseAndImportResume();if(value){await reload();setMessage("请核对解析内容。确认前，新导入内容不会参与检索。");}});}
  async function confirm(){if(!draft)return;await run(async()=>{await window.jobfindsme!.confirmResume({workspace_id:draft.workspace_id,profile_id:draft.profile_id,accepted_fact_ids:[...accepted],corrections:Object.fromEntries([...accepted].map(id=>[id,corrections[id]??""]))});await reload();setMessage("简历已确认，下一次检索可使用其中的技能和经历。");});}
  async function abandon(){if(!draft)return;await run(async()=>{await window.jobfindsme!.abandonResume(draft.workspace_id,draft.profile_id);await reload();setMessage("本次导入已放弃。");});}
  async function clearResume(){if(!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.clearCurrentResume(state.workspace_id!);await reload();setConfirmClear(false);setMessage("当前简历已清除；现在可不使用简历搜索。已有检索和调查快照保留。");});}
  async function savePreferences(){if(!preferences)return;await run(async()=>{const input={...preferences,cities:[...new Set(cityText.split(/[,，、\n]+/).map(value=>value.trim()).filter(Boolean))]};const saved=await window.jobfindsme!.saveSearchPreferences(input);setPreferences(saved);setCityText(saved.cities.join("、"));setMessage("求职偏好已保存，将用于下次岗位检索；你仍可在找工作页调整条件。");});}
  return <div className="resume-page resume-maintenance simple-profile">
    <div className="heading-row resume-heading"><div><h1>我的求职资料</h1><p>简历提供技能和经历证据；岗位、城市与薪资由你明确设置。</p></div><button disabled={busy} onClick={()=>void importResume()}>{current?"替换简历":"上传简历"}</button></div>
    {error&&<p className="notice" role="alert">{error}</p>}{message&&<p className="note" role="status">{message}</p>}
    {draft&&<section className="panel section resume-confirm"><h2>核对新导入的简历</h2><p className="note">{draft.file_name} · {draft.facts.length} 条候选事实。确认前不会用于检索。</p><div className="fact-list">{draft.facts.map(fact=><label className="fact-row" key={fact.fact_id}><input type="checkbox" checked={accepted.has(fact.fact_id)} onChange={event=>setAccepted(previous=>{const next=new Set(previous);event.target.checked?next.add(fact.fact_id):next.delete(fact.fact_id);return next;})}/><span>{factLabels[fact.fact_type]??"简历信息"}</span><textarea value={corrections[fact.fact_id]??fact.value} disabled={!accepted.has(fact.fact_id)||busy} onChange={event=>setCorrections(previous=>({...previous,[fact.fact_id]:event.target.value}))}/></label>)}</div><div className="button-row"><button className="primary-button" disabled={busy||!accepted.size} onClick={()=>void confirm()}>确认简历事实</button><button disabled={busy} onClick={()=>void abandon()}>放弃本次导入</button></div></section>}
    {current?<section className="panel section resume-current"><div className="heading-row"><div><h2>已确认简历</h2><p className="note">下一次检索会使用已确认的技能与经历；原始文件和旧快照保存在本机。</p></div><button disabled={busy} onClick={()=>setConfirmClear(value=>!value)}>清除当前简历</button></div><div className="resume-summary">{([['skills','专业技能'],['experience','工作经历'],['projects','项目经历'],['education','教育经历']] as const).filter(([key])=>current.content[key]?.some(line=>line.trim())).map(([key,label])=><section key={key}><h3>{label}</h3>{current.content[key].map((line,index)=><p key={index}>{line}</p>)}</section>)}</div>{confirmClear&&<div className="history-confirm" role="alert"><p>清除当前简历？之后可不使用简历搜索；已有检索和报告快照保留。</p><div className="button-row"><button autoFocus disabled={busy} onClick={()=>void clearResume()}>确认清除</button><button disabled={busy} onClick={()=>setConfirmClear(false)}>取消</button></div></div>}</section>:!draft&&<section className="panel section resume-empty"><h2>可选：上传简历</h2><p>不上传也能按岗位关键词搜索。上传后请逐项核对，再确认参与匹配。</p><button className="primary-button" disabled={busy} onClick={()=>void importResume()}>选择简历文件</button><p className="note">{state?.capabilities.detail||"支持 PDF、DOCX、MD 和 TXT；扫描 PDF 暂不支持 OCR。"}</p></section>}
    {preferences&&<section className="panel section profile-preferences"><h2>求职偏好</h2><p className="note">这些条件由你填写，不从简历自动猜测。保存后用于下次检索，也可在找工作页临时调整。</p><div className="profile-preference-fields"><label>期望岗位<input aria-label="期望岗位" value={preferences.target_role} maxLength={120} onChange={event=>setPreferences(previous=>previous&&({...previous,target_role:event.target.value}))} placeholder="例如 Python 工程师"/></label><label>城市<input aria-label="偏好城市" value={cityText} onChange={event=>setCityText(event.target.value)} placeholder="例如 上海、杭州；留空不限"/></label><label>月薪下限（K）<input aria-label="偏好月薪下限" type="number" min="0" max="1000" value={preferences.salary_min_k??""} onChange={event=>setPreferences(previous=>previous&&({...previous,salary_min_k:event.target.value===""?null:Number(event.target.value)}))}/></label><label>月薪上限（K）<input aria-label="偏好月薪上限" type="number" min="0" max="1000" value={preferences.salary_max_k??""} onChange={event=>setPreferences(previous=>previous&&({...previous,salary_max_k:event.target.value===""?null:Number(event.target.value)}))}/></label></div><button className="primary-button" disabled={busy||preferences.salary_min_k!=null&&preferences.salary_max_k!=null&&preferences.salary_min_k>preferences.salary_max_k} onClick={()=>void savePreferences()}>保存求职偏好</button></section>}
  </div>;
}
