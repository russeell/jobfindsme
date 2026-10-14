import {dueJobs,localDay} from "../../../shared/job-follow-up";
import {useEffect,useRef,useState} from 'react';
import type {BootstrapData,SearchResultItem,TrackedJob,NextActionInput,ApplicationRecord} from '../../../shared/contracts';
import {preparationStages} from '../../../shared/job-preparation';
import {applicationResults,matchesRecordFilter,recordStage,recordsPageSize,selectRecords,type RecordsFilter,type RecordsSort} from '../../../shared/records-view';
import {isAllowedSourceUrl,sourceBrowserSpecs,type SourceBrowserId} from '../../../shared/source-browser-policy';
import {userError} from '../../../shared/user-errors';
import {JobActions} from '../search/JobActions';
import {formatSalary} from '../search/salary';
import {Icon} from '../shared/Icon';
import {useOriginalBrowser} from '../shared/Workbench';
import {NextActionEditor} from './NextActionEditor';

const tabs:Array<[RecordsFilter,string]>=[['all','全部'],['saved','收藏'],['applied','已投递']];
type Props={active:boolean;data?:BootstrapData;onPrepare(job:SearchResultItem['job'],apply?:boolean,view?:'materials'|'records'):void;onDiscover():void};
export function RecordsPage({active,data,onPrepare,onDiscover}:Props){
  const [items,setItems]=useState<TrackedJob[]>([]);
  const [applications,setApplications]=useState<ApplicationRecord[]>([]);
  const [loaded,setLoaded]=useState(false);
  const [loadError,setLoadError]=useState('');
  const [reloadNonce,setReloadNonce]=useState(0);
  const [filter,setFilter]=useState<RecordsFilter>('all');
  const [query,setQuery]=useState('');
  const [sort,setSort]=useState<RecordsSort>('recent');
  const [limit,setLimit]=useState(recordsPageSize);
  const workspaceId=data?.workspaces[0]?.workspace_id;
  const openBrowser=useOriginalBrowser();
  const results=applicationResults(workspaceId||'',applications);
  const selected=selectRecords(items,filter,query,'',sort);
  const [today,setToday]=useState(localDay),[showAllTodos,setShowAllTodos]=useState(false);
  const [actionBusy,setActionBusy]=useState(false),[actionError,setActionError]=useState('');
  const [undo,setUndo]=useState<NextActionInput>();
  const [editingAction,setEditingAction]=useState<TrackedJob>();
  const actionRun=useRef(false),workspaceRef=useRef(workspaceId);workspaceRef.current=workspaceId;
  useEffect(()=>{if(!active)return;const refresh=()=>setToday(localDay());refresh();const timer=window.setInterval(refresh,60_000);return()=>window.clearInterval(timer);},[active]);
  useEffect(()=>{setUndo(undefined);setEditingAction(undefined);setActionError('');setShowAllTodos(false);},[workspaceId]);
  const todos=dueJobs(items,today);
  async function changeAction(input:NextActionInput,previous?:TrackedJob){
    if(actionRun.current)return false;actionRun.current=true;setActionBusy(true);setActionError('');
    try{
      const value=await window.jobfindsme!.updateNextAction(input);
      if(workspaceRef.current!==input.workspace_id)return false;
      setItems(rows=>rows.map(row=>row.job.job_id===input.job_id?{...row,preparation:value.preparation}:row));
      setUndo(previous?{workspace_id:input.workspace_id,job_id:input.job_id,expected_updated_at:value.preparation.updated_at!,next_action:previous.preparation!.next_action,due_date:previous.preparation!.due_date}:undefined);
      window.dispatchEvent(new Event('jfm:job-updated'));
      return true;
    }catch(reason){if(workspaceRef.current===input.workspace_id){setActionError(userError(reason).message);setReloadNonce(value=>value+1);}return false;}
    finally{actionRun.current=false;setActionBusy(false);}
  }
  function complete(item:TrackedJob){if(!workspaceId||!item.preparation?.updated_at)return;void changeAction({workspace_id:workspaceId,job_id:item.job.job_id,expected_updated_at:item.preparation.updated_at,next_action:'',due_date:null},item);}
  function editAction(item:TrackedJob){if(actionBusy)return;setActionError('');setEditingAction(item);}

  const upcoming=selectRecords(items,'following','','','next').find(item=>item.preparation?.next_action);
  useEffect(()=>setLimit(recordsPageSize),[filter,query,sort]);
  useEffect(()=>{setItems([]);setApplications([]);setLoaded(false);setQuery('');setFilter('all');},[workspaceId]);
  useEffect(()=>{
    if(!workspaceId||!active)return;let cancelled=false,sequence=0;
    const load=()=>{const request=++sequence;setLoadError('');void Promise.all([window.jobfindsme!.listJobTracking(workspaceId),window.jobfindsme!.listApplicationRecords(workspaceId)]).then(([rows,records])=>{if(!cancelled&&request===sequence){setItems(rows);setApplications(records);setLoaded(true);}}).catch(error=>{if(!cancelled&&request===sequence)setLoadError(userError(error).message);});};
    load();window.addEventListener('jfm:job-updated',load);
    return()=>{cancelled=true;window.removeEventListener('jfm:job-updated',load);};
  },[workspaceId,active,reloadNonce]);
  async function update(item:TrackedJob,event_type:'read'|'saved'|'applied'|'apply_opened',enabled=true){
    if(!workspaceId)return;setActionError('');
    await window.jobfindsme!.setJobTracking({workspace_id:workspaceId,job_id:item.job.job_id,event_type,enabled});
    setItems(await window.jobfindsme!.listJobTracking(workspaceId));
    if(event_type==='apply_opened'){
      const sourceId=(Object.keys(sourceBrowserSpecs) as SourceBrowserId[]).find(id=>isAllowedSourceUrl(id,item.job.apply_url))||'web';
      openBrowser({sourceId,url:item.job.apply_url,title:item.job.title});
    }
  }
  function clearFilters(){setQuery('');}
  return <section className="records-page">
    <div className="records-heading"><div><h1>岗位管理</h1><p>收藏、准备与投递记录，都在这里继续。</p></div><button type="button" className="records-find" onClick={onDiscover}>找更多岗位 <span aria-hidden="true">↗</span></button></div>
    {undo&&<div className="records-completed" role="status"><span>已完成：{undo.next_action}</span><button disabled={actionBusy} onClick={()=>void changeAction(undo)}>撤销完成</button></div>}
    {actionError&&<p className="records-load-error" role="alert">{actionError}</p>}
    {todos.length>0&&<section className="records-today"><div className="heading-row"><h2>今日待办 <small>{todos.length}</small></h2><span className="note">按你设置的下一步与日期</span></div>{todos.slice(0,showAllTodos?undefined:3).map(item=><div className="records-todo-row" key={item.job.job_id}><button type="button" className="records-todo" onClick={()=>onPrepare(item.job)}><span><strong>{item.preparation!.next_action}</strong><small>{item.job.company} · {item.job.title}</small></span><span>{item.preparation!.due_date!<today?'已逾期':'今天'} →</span></button><button type="button" className="records-todo-edit" disabled={actionBusy} aria-label={`修改待办：${item.preparation!.next_action}`} title="编辑或改期" onClick={()=>editAction(item)}><Icon name="calendar"/></button><button className="records-todo-complete" disabled={actionBusy} aria-label={`完成待办：${item.preparation!.next_action}`} onClick={()=>complete(item)}>完成</button></div>)}{todos.length>3&&<button className="records-todo-more" onClick={()=>setShowAllTodos(value=>!value)}>{showAllTodos?'收起':`查看全部 ${todos.length} 项`}</button>}</section>}
    {!todos.length&&upcoming&&<section className="records-next"><div><span className="preparation-eyebrow">接下来{upcoming.preparation?.due_date&&` · ${upcoming.preparation.due_date}`}</span><strong>{upcoming.preparation!.next_action}</strong><p>{upcoming.job.company} · {upcoming.job.title}</p></div><button type="button" onClick={()=>onPrepare(upcoming.job)}>继续准备 →</button></section>}
    <div className="records-controls">
      <nav className="records-tabs" aria-label="岗位记录分类">{tabs.map(([key,label])=><button type="button" key={key} aria-current={filter===key?'page':undefined} className={filter===key?'active':''} onClick={()=>setFilter(key)}>{label}<small>{items.filter(item=>matchesRecordFilter(item,key)).length}</small></button>)}</nav>
      <div className="records-tools"><label className="records-search"><Icon name="discover"/><input aria-label="搜索岗位管理" placeholder="搜索岗位、公司或城市" value={query} onChange={event=>setQuery(event.target.value)}/>{query&&<button type="button" aria-label="清空岗位搜索" onClick={()=>setQuery('')}>×</button>}</label><select aria-label="岗位排列方式" value={sort} onChange={event=>setSort(event.target.value as RecordsSort)}><option value="recent">最近记录</option><option value="next">下一步日期</option></select></div>
    </div>
    {loadError&&<p className="records-load-error" role="alert">{loadError} <button type="button" onClick={()=>setReloadNonce(value=>value+1)}>重新读取</button></p>}
    {!loaded?<p className="records-loading" role="status">{loadError?'已有记录保留在本机，可重试读取。':'正在读取本地岗位…'}</p>:selected.length?<>
      <div className="records-table-wrap"><table className="records-table"><thead><tr><th scope="col">岗位 / 公司</th><th scope="col">薪资</th><th scope="col">地点 / 来源</th><th scope="col">进度</th><th scope="col">操作</th></tr></thead><tbody>{selected.slice(0,limit).map(item=>{const status=recordStage(item),applied=matchesRecordFilter(item,'applied'),result=results.get(item.job.job_id),hasResult=applied||!!result,statusLabel=(!status||status==='considering')&&!applied&&result?(result==='uncertain'?'待核对':'已沟通'):status?preparationStages[status]:item.tracking.read?'已查看':'未查看';return <tr key={item.job.job_id}>
        <td className="record-main"><button type="button" className="record-title" onClick={()=>onPrepare(item.job,false,hasResult?'records':'materials')}>{item.job.title}</button><span className="record-company">{item.job.company}</span><span className="record-narrow-stage">{statusLabel}</span>
        {status!=='closed'?<button type="button" className={`record-next-action${item.preparation?.next_action?' has-action':''}`} disabled={actionBusy} aria-label={`${item.preparation?.next_action?'编辑':'安排'}下一步：${item.job.title}`} onClick={()=>editAction(item)}><Icon name="calendar"/><span>{item.preparation?.next_action||'安排下一步'}</span>{item.preparation?.due_date&&<time dateTime={item.preparation.due_date}>{item.preparation.due_date}</time>}</button>:null}
        </td><td className="record-pay">{formatSalary(item.job)}</td><td className="record-location">{item.job.locations.join(' / ')||'地点未知'}<small>{item.job.source.source_name}</small></td><td><span className={`record-stage ${status||'none'}`}>{statusLabel}</span></td><td className="record-actions-cell"><JobActions applicationComplete={hasResult} applicationLabel={!applied&&result?(result==='uncertain'?'核对结果':'沟通记录'):undefined} onApply={()=>onPrepare(item.job,true,hasResult?'records':'materials')} compact tracking={item.tracking} onTrack={(event,enabled)=>update(item,event,enabled)} onOpen={()=>update(item,'apply_opened')} onResearch={()=>onPrepare(item.job,false,hasResult?'records':'materials')} onError={message=>setActionError(message?userError(message).message:'')}/></td>
      </tr>;})}</tbody></table></div>
      <div className="records-pagination"><span>显示 {Math.min(limit,selected.length)} / {selected.length} 条岗位</span>{limit<selected.length&&<button type="button" onClick={()=>setLimit(value=>value+recordsPageSize)}>再显示 {Math.min(recordsPageSize,selected.length-limit)} 条</button>}</div>
    </>:<div className="records-empty"><Icon name="records"/><h2>{query?'没有匹配的岗位':filter==='saved'?'还没有收藏岗位':filter==='applied'?'还没有已投递岗位':'这里还没有岗位'}</h2><p>{query?'试试其他关键词，或清空筛选。':filter==='saved'?'点击岗位上的星标，喜欢的机会就会留在这里。':filter==='applied'?'投递后在岗位上标记，不会把打开原页当作已投递。':'历史记录会保留，收藏和投递状态分别记录。'}</p><div>{query?<button type="button" onClick={clearFilters}>清空筛选</button>:<><button type="button" onClick={onDiscover}>去找工作 →</button>{filter!=='all'&&items.length>0&&<button type="button" onClick={()=>setFilter('all')}>查看全部岗位</button>}</>}</div></div>}
    {editingAction&&workspaceId&&<NextActionEditor key={`${workspaceId}:${editingAction.job.job_id}`} item={editingAction} busy={actionBusy} error={actionError} onClose={()=>setEditingAction(undefined)} onSave={(next_action,due_date)=>changeAction({workspace_id:workspaceId,job_id:editingAction.job.job_id,expected_updated_at:editingAction.preparation?.updated_at??null,next_action,due_date})}/>}
  </section>;
}
