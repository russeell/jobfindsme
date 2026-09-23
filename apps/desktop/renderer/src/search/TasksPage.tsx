import {useEffect,useState,type FormEvent} from "react";
import type {BootstrapData,SearchFilters,ScheduledTask} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
type MatchingWeights=Record<"skills"|"projects"|"education"|"experience",number>;
export function TasksPage({data,snapshot}:{data?:BootstrapData;onError(message?:string):void;snapshot?:{intent:string;filters:SearchFilters;weights:MatchingWeights;source_ids:string[]}}){
 const workspaceId=data?.workspaces[0]?.workspace_id;
 const [tasks,setTasks]=useState<ScheduledTask[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const [name,setName]=useState("每日岗位更新"),[intent,setIntent]=useState("");
 const [frequency,setFrequency]=useState<"daily"|"weekly"|"interval">("daily"),[time,setTime]=useState("09:00"),[weekday,setWeekday]=useState(0);
 const [interval,setInterval]=useState(1),[unit,setUnit]=useState(60),[catchUp,setCatchUp]=useState<"once"|"skip">("once");
 const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone||"Asia/Shanghai";
 async function refresh(){if(workspaceId)setTasks(await window.jobfindsme!.listScheduledTasks(workspaceId));}
 useEffect(()=>{void refresh().catch(e=>setError(userError(e).message));},[workspaceId]);
 async function create(e:FormEvent){e.preventDefault();if(!workspaceId)return;setError("");
  const minutes=interval*unit;
  if(frequency==="interval"&&(!Number.isInteger(minutes)||minutes<15||minutes>10080)){setError("间隔须为 15 分钟至 7 天内的整分钟。");return;}
  if(!name.trim()||!(snapshot?.intent??intent).trim()){setError("请填写任务名称和岗位关键词。");return;}
  setBusy(true);try{await window.jobfindsme!.createScheduledTask({workspace_id:workspaceId,name:name.trim(),intent:snapshot?.intent??intent,source_ids:snapshot?.source_ids??data?.sources.filter(s=>s.live_search_enabled).map(s=>s.source_id)??[],filters:snapshot?.filters??{unknown_policy:"include",read:"any",salary_mode:"overlap"},frequency,timezone,local_time:frequency==="interval"?undefined:time,weekday:frequency==="weekly"?weekday:undefined,interval_minutes:frequency==="interval"?minutes:undefined,catch_up_policy:catchUp});await refresh();}catch(error){setError(userError(error).message);}finally{setBusy(false);}}
 async function toggle(task:ScheduledTask){setBusy(true);try{await window.jobfindsme!.setScheduledTaskPaused(task.task_id,task.status==="active");await refresh();}catch(error){setError(userError(error).message);}finally{setBusy(false);}}
 return <div className="schedule-content"><div className="heading-row"><div><h1>定时检索</h1><p>按当前筛选和已确认简历定时查找岗位。</p></div></div>
 <form className="task-form" onSubmit={e=>void create(e)}><label>任务名称<input value={name} onChange={e=>setName(e.target.value)} required maxLength={80}/></label>
 {snapshot?<div className="snapshot-summary"><strong>{snapshot.intent||"请先填写岗位关键词"}</strong><p>{snapshot.filters.cities?.join(" / ")||"城市不限"} · {snapshot.source_ids.length} 个来源</p><small>保存当前筛选、简历和匹配规则，后续修改不会改变此任务。</small></div>:<label>岗位关键词<input value={intent} onChange={e=>setIntent(e.target.value)} required/></label>}
 <fieldset className="frequency-field"><legend>检索频率</legend><div className="frequency-options">{([["daily","每日"],["weekly","每周"],["interval","固定间隔"]] as const).map(([value,label])=><button type="button" key={value} aria-pressed={frequency===value} className={frequency===value?"selected":""} onClick={()=>setFrequency(value)}>{label}</button>)}</div></fieldset>
 <div className="schedule-fields">{frequency==="weekly"&&<label>星期<select value={weekday} onChange={e=>setWeekday(Number(e.target.value))}>{["周一","周二","周三","周四","周五","周六","周日"].map((day,index)=><option key={day} value={index}>{day}</option>)}</select></label>}{frequency==="interval"?<><label>间隔数值<input type="number" min={1} max={10080} value={interval} onChange={e=>setInterval(Number(e.target.value))} required/></label><label>单位<select value={unit} onChange={e=>setUnit(Number(e.target.value))}><option value={1}>分钟</option><option value={60}>小时</option><option value={1440}>天</option></select></label></>:<label>执行时间<input type="time" value={time} onChange={e=>setTime(e.target.value)} required/></label>}</div>
 <label>错过执行时<select value={catchUp} onChange={e=>setCatchUp(e.target.value as typeof catchUp)}><option value="once">下次打开时补查一次</option><option value="skip">等待下个计划时间</option></select></label>
 {error&&<p className="error-message" role="alert">{error}</p>}<button className="primary-button" disabled={busy||!(snapshot?.intent??intent).trim()||!workspaceId||snapshot?.source_ids.length===0}>{busy?"保存中…":"创建定时检索"}</button><p className="note">时区：{timezone}。应用在后台时可执行；完全退出、关机或休眠时不会自动唤醒。</p></form>
 {tasks.length?<section className="scheduled-tasks"><h2>已创建任务 · {tasks.length}</h2>{tasks.map(task=><article key={task.task_id}><div><strong>{task.name}</strong><span>{task.status==="active"?"运行中":"已暂停"}</span></div><p>{task.intent} · 下次：{new Date(task.next_run_at).toLocaleString()}</p>{task.last_error&&<p className="note">{userError(task.last_error).message}</p>}<button disabled={busy} onClick={()=>void toggle(task)}>{task.status==="active"?"暂停":"恢复"}</button></article>)}</section>:<p className="note schedule-empty">暂无定时任务，创建后显示在这里。</p>}
 </div>;
}
