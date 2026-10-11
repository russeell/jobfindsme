import {useLayoutEffect,useRef} from 'react';
import type {ResumeDraft} from '../../../shared/contracts';

const labels:Record<string,string>={basic_information:'基本信息与补充内容',experience:'工作经历',project:'项目经历',education:'教育经历',skill_detail:'专业技能'};

function DocumentText({value,label,disabled,onChange}:{value:string;label:string;disabled:boolean;onChange:(value:string)=>void}){
  const ref=useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(()=>{
    const node=ref.current;if(!node)return;
    const fit=()=>{node.style.height='0px';node.style.height=`${node.scrollHeight+2}px`;};
    fit();let width=node.clientWidth;
    const observer=new ResizeObserver(()=>{if(node.clientWidth!==width){width=node.clientWidth;fit();}});
    observer.observe(node);return()=>observer.disconnect();
  },[value]);
  return <textarea ref={ref} aria-label={label} value={value} disabled={disabled} rows={1} onChange={event=>onChange(event.target.value)}/>;
}

export function ResumeImportReview({draft,accepted,corrections,busy,hasCurrent,onToggle,onEdit,onConfirm,onAbandon,onReplace}:{draft:ResumeDraft;accepted:Set<string>;corrections:Record<string,string>;busy:boolean;hasCurrent:boolean;onToggle:(id:string,checked:boolean)=>void;onEdit:(id:string,value:string)=>void;onConfirm:()=>void;onAbandon:()=>void;onReplace:()=>void}){
  const root=useRef<HTMLElement>(null);
  useLayoutEffect(()=>{root.current?.closest('.content')?.scrollTo({top:0});},[draft.profile_id]);
  const content=draft.facts.filter(fact=>fact.fact_type!=='skill');
  const tags=draft.facts.filter(fact=>fact.fact_type==='skill');
  // Retain document order instead of sorting a resume into a form wizard.
  const groups: {type:string;facts:typeof content}[]=[];
  for(const fact of content){const last=groups.at(-1);if(last?.type===fact.fact_type)last.facts.push(fact);else groups.push({type:fact.fact_type,facts:[fact]});}
  const kept=content.filter(fact=>accepted.has(fact.fact_id));
  const empty=kept.some(fact=>!(corrections[fact.fact_id]??fact.value).trim());
  return <section ref={root} className="resume-import-review" aria-label="核对导入简历">
    <header className="import-review-heading"><div><h2>核对导入的文稿</h2><p>{draft.file_name} · 内容可直接修改，确认后进入文档编辑器。</p></div><button disabled={busy} onClick={onReplace}>重新导入</button></header>
    <div className="import-document-canvas"><div className="import-document-paper">
      {groups.map((group,index)=><section className="import-document-section" key={`${group.type}-${index}`} aria-label={labels[group.type]??'简历内容'}>
        <h3>{labels[group.type]??'简历内容'}</h3>
        {group.facts.map((fact,entry)=><div className={`import-document-entry${accepted.has(fact.fact_id)?'':' excluded'}`} key={fact.fact_id}>
          <label className="import-keep"><input type="checkbox" disabled={busy} checked={accepted.has(fact.fact_id)} onChange={event=>onToggle(fact.fact_id,event.target.checked)}/><span>{accepted.has(fact.fact_id)?'保留':'已排除'}<span className="sr-only"> {labels[group.type]} {entry+1}</span></span></label>
          <DocumentText label={`${labels[group.type]} ${entry+1} 内容`} value={corrections[fact.fact_id]??fact.value} disabled={busy||!accepted.has(fact.fact_id)} onChange={value=>onEdit(fact.fact_id,value)}/>
        </div>)}
      </section>)}
    </div></div>
    {tags.length>0&&<details className="import-matching-tags"><summary>用于匹配的技能标签 · {tags.filter(fact=>accepted.has(fact.fact_id)).length} 个</summary><p>仅作为匹配线索，不会额外添加到简历正文。请取消不符合实际经历的标签。</p><div>{tags.map(fact=><label key={fact.fact_id}><input type="checkbox" checked={accepted.has(fact.fact_id)} disabled={busy} onChange={event=>onToggle(fact.fact_id,event.target.checked)}/>{fact.value}</label>)}</div></details>}
    <footer className="import-review-footer"><p>{empty?'内容不能为空；不需要的段落可取消保留。':hasCurrent?'确认后保存新版本，原简历保留。':'确认前不会用于岗位匹配。'}</p><div><button disabled={busy} onClick={onAbandon}>暂不使用</button><button className="primary-button" disabled={busy||!kept.length||empty} onClick={onConfirm}>{busy?'正在保存…':'确认并开始编辑'}</button></div></footer>
  </section>;
}
