import type {ScoreDetails,SearchResultItem} from '../../../shared/contracts';
import {jobDecision} from '../../../shared/job-decision';
export function JobDecision({job,details,stale=false,resumeAvailable=false}:{job:SearchResultItem['job'];details?:ScoreDetails;stale?:boolean;resumeAvailable?:boolean}){
  const {signals,gaps}=jobDecision(job,details,stale,resumeAvailable);
  return <section className="job-decision" aria-label="投递前核对"><h4>投递前看这里</h4>{signals.length>0&&<div className="job-decision-signals"><small>本地对应线索</small>{signals.slice(0,2).map(text=><p key={text}>{text}</p>)}</div>}<div className="job-decision-gaps"><small>需要核对</small>{gaps.slice(0,3).map(text=><p key={text}>{text}</p>)}</div>{(signals.length>2||gaps.length>3)&&<details><summary>查看其余线索</summary>{signals.slice(2).map(text=><p key={text}>{text}</p>)}{gaps.slice(3).map(text=><p key={text}>{text}</p>)}</details>}</section>;
}
