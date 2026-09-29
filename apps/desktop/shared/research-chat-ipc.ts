import {validChatAttachments,attachmentContext} from "./chat-attachments";
import {isAssistantSkillId} from "./assistant-skills";
import type {ResearchChatTurn} from "./contracts";

/** Require a direct, affirmative request before storing a separate report. */
export function explicitReportRequest(question:string):boolean{
  const text=question.replace(/[“「][^”」]*[”」]|"[^"]*"|'[^']*'/gu,"").trim();
  if(/(?:不要|不用|无需|不必|别|不需要|只回答|只聊天)[^。！？\n]{0,18}报告/u.test(text))return false;
  if(/^(?:解释|什么是|如何|怎么|为什么|讨论|分析|介绍|总结|JD|岗位描述|以下)/u.test(text)||/(?:如何|怎么|怎样)[^。！？\n]{0,12}(?:生成|制作|写)[^。！？\n]{0,12}报告/u.test(text))return false;
  const action=/(?:生成|保存|写|制作|整理|出)(?:一份|一个|份)?[^。！？\n]{0,12}(?:研究)?报告/u;
  return /^(?:请|帮我|给我|为我)/u.test(text)&&action.test(text.slice(0,60))||
    /^(?:生成|保存|写|制作|整理|出)/u.test(text)&&action.test(text.slice(0,40))||
    /(?:，|；|然后|并|再)\s*请?\s*(?:生成|保存|写|制作|整理|出)[^。！？\n]{0,16}报告/u.test(text);
}

// Only the model copy is bounded; saved conversation turns remain complete.
export function modelHistoryWithinBudget(history:ResearchChatTurn[],maxChars=20000):ResearchChatTurn[]{
  const selected:ResearchChatTurn[]=[];let used=0,imageChars=0;
  for(let index=history.length-1;index>=0;index--){
    if(selected.length>=200)break;
    const turn=history[index],base=turn.interrupted?`（上条回复已停止，内容未完成）\n${turn.text}`:turn.text,text=turn.role==="user"&&turn.attachments?.length?`${base.slice(0,4000)}\n\n${attachmentContext(turn.attachments).slice(0,4000)}`.slice(0,8000):base.slice(-8000),remaining=maxChars-used;
    if(remaining<=0)break;
    if(text.length>remaining){if(!selected.length)selected.unshift({role:turn.role,text:text.slice(-remaining)});break;}
    const images=turn.attachments?.filter(item=>{if(!item.image||imageChars+item.image.data.length>8_000_000)return false;imageChars+=item.image.data.length;return true;}).slice(0,2);selected.unshift({role:turn.role,text,...(images?.length?{attachments:images}:{})});used+=text.length;
  }
  return selected;
}

export function validResearchChatInput(input:unknown):boolean{
  if(!input||typeof input!=="object")return false;
  const value=input as Record<string,unknown>;
  const validId=(id:unknown,max:number)=>typeof id==="string"&&new RegExp(`^[-a-zA-Z0-9]{8,${max}}$`).test(id);
  const state=value.interview_state as Record<string,unknown>|undefined;
  if(state&&(typeof state!=="object"||!Array.isArray(state.asked)||state.asked.length>20||!state.asked.every(item=>typeof item==="string"&&item.length<=300)||!Array.isArray(state.weaknesses)||state.weaknesses.length>10||!state.weaknesses.every(item=>typeof item==="string"&&item.length<=300)||typeof state.follow_up_reason!=="string"||state.follow_up_reason.length>500||typeof state.current_question!=="string"||state.current_question.length>500))return false;
  return (value.attachments===undefined||validChatAttachments(value.attachments))&&(value.skill_id===undefined||isAssistantSkillId(value.skill_id))&&validId(value.request_id,80)&&validId(value.session_id,100)&&typeof value.workspace_id==="string"
    &&typeof value.connection_id==="string"&&typeof value.question==="string"&&value.question.length<=12000
    &&!!value.question.trim()&&typeof value.research==="boolean"&&Array.isArray(value.history)
    &&value.history.length<=200&&value.history.every(item=>item&&["user","assistant"].includes(item.role)
      &&typeof item.text==="string"&&item.text.length<=8000&&(item.attachments===undefined||validChatAttachments(item.attachments)))&&value.history.reduce((sum,item)=>sum+(item.attachments||[]).reduce((n:number,file:{image?:{data:string}})=>n+(file.image?.data.length||0),0),0)<=8_000_000;
}
