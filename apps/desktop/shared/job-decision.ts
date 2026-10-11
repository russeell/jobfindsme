import type {ScoreDetails,SearchResultItem} from './contracts';
import {hasFullDescription} from './research-reports';

type Job=SearchResultItem['job'];
const labels:Record<string,string>={skills:'技能',projects:'项目',education:'学历',experience:'经验'};
export function jobDecision(job:Job,details?:ScoreDetails,stale=false,resumeAvailable=false){
  const signals:string[]=[],gaps:string[]=[];
  if(job.source.liveness==='closed')gaps.push('来源标记岗位已关闭，投递前先确认是否重新开放。');
  else if(job.source.liveness==='stale')gaps.push('岗位信息已过期，先到原页确认是否仍在招聘。');
  else gaps.push('是否仍在招聘，以岗位原页为准。');
  if(!hasFullDescription(job))gaps.push('完整 JD 尚未取得，职责与要求仍需核对。');
  if(!job.locations.length)gaps.push('工作地点未注明。');
  if(job.salary_min_k===null&&job.salary_max_k===null&&!job.salary?.raw_text?.trim())gaps.push('薪资未注明，沟通时确认范围与口径。');
  if(stale)gaps.push('岗位原文已变化，旧匹配线索暂不使用。');
  else if(resumeAvailable&&hasFullDescription(job)){
    for(const [key,value] of Object.entries(details||{})){
      const text=value.explanation?.trim().replaceAll('暂不计分','仍需核对').replace('，按达成比例计分','');
      if(!text)continue;
      const line=`${labels[key]||key}：${text}`;
      if(value.status==='known'&&value.ratio>=1)signals.push(line);else gaps.push(line);
    }
  }
  if(!resumeAvailable)gaps.push('尚无已确认简历，暂不判断与你的匹配情况。');
  return {signals:[...new Set(signals)],gaps:[...new Set(gaps)]};
}
