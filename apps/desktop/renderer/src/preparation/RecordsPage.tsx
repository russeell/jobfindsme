import {useEffect,useState} from 'react';
import type {BootstrapData,PreparationStage,SearchResultItem,TrackedJob} from '../../../shared/contracts';
import {preparationStages} from '../../../shared/job-preparation';
import {matchesRecordFilter,recordStage,recordsPageSize,selectRecords,type RecordsFilter,type RecordsSort} from '../../../shared/records-view';
import {isAllowedSourceUrl,sourceBrowserSpecs,type SourceBrowserId} from '../../../shared/source-browser-policy';
import {userError} from '../../../shared/user-errors';
import {JobActions} from '../search/JobActions';
import {formatSalary} from '../search/salary';
import {Icon} from '../shared/Icon';
import {useOriginalBrowser} from '../shared/Workbench';

const tabs:Array<[RecordsFilter,string]>=[['following','在跟进'],['saved','收藏'],['applied','已投递'],['read','已看过'],['all','全部']];
type Props={active:boolean;data?:BootstrapData;onError(message?:string):void;onPrepare(job:SearchResultItem['job']):void;onDiscover():void};
export function RecordsPage({active,data,onError,onPrepare,onDiscover}:Props){
  const [items,setItems]=useState<TrackedJob[]>([]);
  const [loaded,setLoaded]=useState(false);
  const [loadError,setLoadError]=useState('');
  const [reloadNonce,setReloadNonce]=useState(0);
  const [filter,setFilter]=useState<RecordsFilter>('following');
  const [query,setQuery]=useState('');
  const [stage,setStage]=useState<PreparationStage|''>('');
  const [sort,setSort]=useState<RecordsSort>('recent');
  const [limit,setLimit]=useState(recordsPageSize);
  const workspaceId=data?.workspaces[0]?.workspace_id;
  const openBrowser=useOriginalBrowser();
  const selected=selectRecords(items,filter,query,stage,sort);
  const upcoming=selectRecords(items,'following','','','next').find(item=>item.preparation?.next_action);
  useEffect(()=>setLimit(recordsPageSize),[filter,query,stage,sort]);
  useEffect(()=>{setItems([]);setLoaded(false);setQuery('');setStage('');setFilter('following');},[workspaceId]);
  useEffect(()=>{
    if(!workspaceId||!active)return;let cancelled=false;
    const load=()=>{setLoadError('');void window.jobfindsme!.listJobTracking(workspaceId).then(rows=>{if(!cancelled){setItems(rows);setLoaded(true);}}).catch(error=>{if(!cancelled)setLoadError(userError(error).message);});};
    load();window.addEventListener('jfm:job-updated',load);
    return()=>{cancelled=true;window.removeEventListener('jfm:job-updated',load);};
  },[workspaceId,active,reloadNonce]);
  async function update(item:TrackedJob,event_type:'read'|'saved'|'applied'|'apply_opened',enabled=true){
    if(!workspaceId)return;onError(undefined);
    await window.jobfindsme!.setJobTracking({workspace_id:workspaceId,job_id:item.job.job_id,event_type,enabled});
    setItems(await window.jobfindsme!.listJobTracking(workspaceId));
    if(event_type==='apply_opened'){
      const sourceId=(Object.keys(sourceBrowserSpecs) as SourceBrowserId[]).find(id=>isAllowedSourceUrl(id,item.job.apply_url))||'web';
      openBrowser({sourceId,url:item.job.apply_url,title:item.job.title});
    }
  }
  function clearFilters(){setQuery('');setStage('');}
  return <section className="records-page">
    <div className="records-heading"><div><span className="preparation-eyebrow">机会与进度</span><h1>我的岗位</h1><p>收藏值得继续的机会，把下一步留在这里。</p></div><button type="button" className="records-find" onClick={onDiscover}>找更多岗位 <span aria-hidden="true">↗</span></button></div>
    {upcoming&&<section className="records-next"><div><span className="preparation-eyebrow">接下来{upcoming.preparation?.due_date&&` · ${upcoming.preparation.due_date}`}</span><strong>{upcoming.preparation!.next_action}</strong><p>{upcoming.job.company} · {upcoming.job.title}</p></div><button type="button" onClick={()=>onPrepare(upcoming.job)}>继续准备 →</button></section>}
    <div className="records-controls">
      <nav className="records-tabs" aria-label="岗位记录分类">{tabs.map(([key,label])=><button type="button" key={key} aria-current={filter===key?'page':undefined} className={filter===key?'active':''} onClick={()=>{setFilter(key);setStage('');}}>{label}<small>{items.filter(item=>matchesRecordFilter(item,key)).length}</small></button>)}</nav>
      <div className="records-tools"><label className="records-search"><Icon name="discover"/><input aria-label="搜索我的岗位" placeholder="搜索岗位、公司或城市" value={query} onChange={event=>setQuery(event.target.value)}/>{query&&<button type="button" aria-label="清空岗位搜索" onClick={()=>setQuery('')}>×</button>}</label><select aria-label="筛选岗位进度" value={stage} onChange={event=>{const next=event.target.value as typeof stage;setStage(next);if(next==='closed'&&filter==='following')setFilter('all');}}><option value="">所有进度</option>{Object.entries(preparationStages).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select><select aria-label="岗位排列方式" value={sort} onChange={event=>setSort(event.target.value as RecordsSort)}><option value="recent">最近记录</option><option value="next">下一步日期</option></select></div>
    </div>
    {loadError&&<p className="records-load-error" role="alert">{loadError} <button type="button" onClick={()=>setReloadNonce(value=>value+1)}>重新读取</button></p>}
    {!loaded?<p className="records-loading" role="status">{loadError?'已有记录保留在本机，可重试读取。':'正在读取本地岗位…'}</p>:selected.length?<>
      <div className="records-job-list">{selected.slice(0,limit).map(item=>{const status=recordStage(item);return <article className="record-card" key={item.job.job_id}>
        <div className="record-card-heading"><button type="button" className="record-title" onClick={()=>onPrepare(item.job)}>{item.job.title}</button>{(status||item.tracking.saved)&&<span className={`record-stage ${status||'saved'}`}>{status?preparationStages[status]:'已收藏'}</span>}</div>
        <div className="record-meta"><span>{item.job.company}</span><span>{item.job.locations.join(' / ')||'地点未知'}</span>{item.job.source.source_name!==item.job.company&&<span className="record-source">{item.job.source.source_name}</span>}</div>
        <p className="record-salary">{formatSalary(item.job)}</p>
        {item.preparation?.next_action&&<p className="records-action"><span>下一步</span>{item.preparation.next_action}{item.preparation.due_date&&<time>{item.preparation.due_date}</time>}</p>}
        <JobActions compact tracking={item.tracking} onTrack={(event,enabled)=>update(item,event,enabled)} onOpen={()=>update(item,'apply_opened')} onResearch={()=>onPrepare(item.job)} onError={onError}/>
      </article>;})}</div>
      <div className="records-pagination"><span>显示 {Math.min(limit,selected.length)} / {selected.length} 条岗位</span>{limit<selected.length&&<button type="button" onClick={()=>setLimit(value=>value+recordsPageSize)}>再显示 {Math.min(recordsPageSize,selected.length-limit)} 条</button>}</div>
    </>:<div className="records-empty"><Icon name="records"/><h2>{query||stage?'没有匹配的岗位':filter==='following'?'还没有正在跟进的机会':'这里还没有岗位'}</h2><p>{query||stage?'试试其他关键词，或清空筛选。':filter==='following'?'收藏感兴趣的岗位，或在岗位准备中记录进度。':'历史记录会保留，收藏和投递状态分别记录。'}</p><div>{query||stage?<button type="button" onClick={clearFilters}>清空筛选</button>:<><button type="button" onClick={onDiscover}>去找工作 →</button>{filter==='following'&&items.length>0&&<button type="button" onClick={()=>setFilter('read')}>查看已看过的岗位</button>}</>}</div></div>}
  </section>;
}
