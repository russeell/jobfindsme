import type {ResearchChatTurn} from "./contracts";

// Only the model copy is bounded; saved conversation turns remain complete.
export function modelHistoryWithinBudget(history:ResearchChatTurn[],maxChars=20000):ResearchChatTurn[]{
  const selected:ResearchChatTurn[]=[];let used=0;
  for(let index=history.length-1;index>=0;index--){
    if(selected.length>=200)break;
    const turn=history[index],text=turn.text.slice(-8000),remaining=maxChars-used;
    if(remaining<=0)break;
    if(text.length>remaining){if(!selected.length)selected.unshift({...turn,text:text.slice(-remaining)});break;}
    selected.unshift({...turn,text});used+=text.length;
  }
  return selected;
}

export function validResearchChatInput(input:unknown):boolean{
  if(!input||typeof input!=="object")return false;
  const value=input as Record<string,unknown>;
  const validId=(id:unknown,max:number)=>typeof id==="string"&&new RegExp(`^[-a-zA-Z0-9]{8,${max}}$`).test(id);
  return validId(value.request_id,80)&&validId(value.session_id,100)&&typeof value.workspace_id==="string"
    &&typeof value.connection_id==="string"&&typeof value.question==="string"&&value.question.length<=700
    &&!!value.question.trim()&&typeof value.research==="boolean"&&Array.isArray(value.history)
    &&value.history.length<=200&&value.history.every(item=>item&&["user","assistant"].includes(item.role)
      &&typeof item.text==="string"&&item.text.length<=8000);
}
