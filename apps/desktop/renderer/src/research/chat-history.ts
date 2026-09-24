import type {ResearchChatTurn} from "../../../shared/contracts";

export type SavedResearchChat={id:string;title:string;updatedAt:string;turns:ResearchChatTurn[];reportIds:string[]};
const key=(workspaceId:string)=>`jobfindsme:research-chat:${workspaceId}`;

export function loadResearchChats(workspaceId:string):SavedResearchChat[]{
  try{
    const value=JSON.parse(localStorage.getItem(key(workspaceId))||"[]");
    if(!Array.isArray(value))return [];
    return value.filter(item=>item&&typeof item.id==="string"&&Array.isArray(item.turns)).slice(0,50);
  }catch{return [];}
}

export function saveResearchChats(workspaceId:string,chats:SavedResearchChat[]):void{
  localStorage.setItem(key(workspaceId),JSON.stringify(chats.slice(0,50).map(chat=>({...chat,turns:chat.turns.slice(-20)}))));
}
