import type {TrackedJob,ResearchChatTurn} from './contracts';
export function localDay(now=new Date()):string{return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;}
export function reminderDay(offset:number,now=new Date()):string{
 const day=new Date(now);day.setDate(day.getDate()+offset);return localDay(day);
}
export function dueJobs(items:TrackedJob[],today=localDay()):TrackedJob[]{
 return items.filter(item=>item.preparation?.stage!=='closed'&&item.preparation?.next_action.trim()&&item.preparation.due_date&&item.preparation.due_date<=today).sort((a,b)=>a.preparation!.due_date!.localeCompare(b.preparation!.due_date!));
}
export function interviewReview(turns:ResearchChatTurn[]):string[]{
 const state=[...turns].reverse().find(turn=>turn.role==='assistant'&&!turn.interrupted&&turn.interviewState)?.interviewState;
 return [...new Set(state?.weaknesses.map(value=>value.trim()).filter(Boolean)||[])].slice(0,10);
}
