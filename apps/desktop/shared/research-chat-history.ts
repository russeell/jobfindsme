import type {ResearchChatDelta,ResearchChatTurn} from "./contracts";
import type {PendingResearch} from "./research-dialogue";

export type SavedResearchChat={id:string;title:string;updatedAt:string;turns:ResearchChatTurn[];reportIds:string[];subjectCompany?:string;subjectTitle?:string;jobId?:string;researchMode?:boolean;draft?:string;failure?:string;pendingResearch?:PendingResearch};
const key=(workspaceId:string)=>`jobfindsme:research-chat:${workspaceId}`;
export type ActiveResearchRequest={id:string;workspaceId:string;sessionId:string;kind:"model"|"report"};
export const acceptsResearchDelta=(active:ActiveResearchRequest|null,event:ResearchChatDelta,workspaceId?:string)=>!!active&&active.kind==="model"&&active.id===event.request_id&&active.workspaceId===event.workspace_id&&active.sessionId===event.session_id&&workspaceId===event.workspace_id;

export function beginChat(chat:SavedResearchChat|undefined,id:string,question:string,at:string):{chat:SavedResearchChat;history:ResearchChatTurn[]}{
  const turns=chat?.turns||[];
  const retry=chat?.draft===question&&turns.at(-1)?.role==="user"&&turns.at(-1)?.text===question;
  const history=retry?turns.slice(0,-1):turns;
  return {history,chat:{id,title:chat?.title||question.slice(0,40),updatedAt:at,turns:retry?turns:[...turns,{role:"user",text:question}],reportIds:chat?.reportIds||[],subjectCompany:chat?.subjectCompany,subjectTitle:chat?.subjectTitle,jobId:chat?.jobId,researchMode:chat?.researchMode,draft:question,pendingResearch:chat?.pendingResearch}};
}

export function finishChat(chat:SavedResearchChat,text:string,reportId:string|undefined,at:string):SavedResearchChat{
  return {...chat,updatedAt:at,turns:[...chat.turns,{role:"assistant",text}],reportIds:reportId?[...chat.reportIds,reportId]:chat.reportIds,draft:undefined,failure:undefined,pendingResearch:undefined};
}

export function failChat(chat:SavedResearchChat,reason:string,at:string):SavedResearchChat{
  return {...chat,updatedAt:at,failure:reason,draft:chat.draft||chat.turns.at(-1)?.text};
}

export function loadResearchChats(workspaceId:string):SavedResearchChat[]{
  try{
    const value=JSON.parse(localStorage.getItem(key(workspaceId))||"[]");
    if(!Array.isArray(value))return [];
    return value.filter(item=>item&&typeof item.id==="string"&&Array.isArray(item.turns)&&item.turns.every((turn:unknown)=>!!turn&&typeof turn==="object"&&"role" in turn&&"text" in turn&&["user","assistant"].includes(String(turn.role))&&typeof turn.text==="string")).slice(0,50);
  }catch{return [];}
}

export function saveResearchChats(workspaceId:string,chats:SavedResearchChat[]):boolean{
  try{localStorage.setItem(key(workspaceId),JSON.stringify(chats.slice(0,50)));return true;}
  catch{return false;}
}

export function toStoredResearchChat(workspaceId:string,chat:SavedResearchChat):Record<string,unknown>{
  return {workspace_id:workspaceId,id:chat.id,subject_key:(chat.subjectCompany||"").toLocaleLowerCase().replace(/\s+/g,""),subject_company:chat.subjectCompany,subject_title:chat.subjectTitle,job_id:chat.jobId,research_mode:chat.researchMode,turns:chat.turns,report_ids:chat.reportIds.slice(-30),draft:chat.draft,pending:chat.pendingResearch,failure:chat.failure};
}
export function fromStoredResearchChat(item:Record<string,unknown>):SavedResearchChat{
  const turns=Array.isArray(item.turns)?item.turns.filter(value=>value&&typeof value==="object"&&["user","assistant"].includes(value.role)&&typeof value.text==="string") as ResearchChatTurn[]:[];
  const first=turns.find(value=>value.role==="user");
  return {id:String(item.id),title:first?.text.slice(0,40)||"研究对话",updatedAt:String(item.updated_at||new Date().toISOString()),turns,reportIds:Array.isArray(item.report_ids)?item.report_ids.filter((value):value is string=>typeof value==="string"):[],subjectCompany:typeof item.subject_company==="string"?item.subject_company:undefined,subjectTitle:typeof item.subject_title==="string"?item.subject_title:undefined,jobId:typeof item.job_id==="string"?item.job_id:undefined,researchMode:typeof item.research_mode==="boolean"?item.research_mode:undefined,draft:typeof item.draft==="string"?item.draft:undefined,pendingResearch:item.pending&&typeof item.pending==="object"?item.pending as PendingResearch:undefined,failure:typeof item.failure==="string"?item.failure:undefined};
}
export function mergeResearchChats(local:SavedResearchChat[],remote:SavedResearchChat[]):SavedResearchChat[]{
  const byId=new Map(remote.map(chat=>[chat.id,chat]));
  for(const chat of local){const stored=byId.get(chat.id);if(!stored||chat.turns.length>stored.turns.length||chat.turns.length===stored.turns.length&&chat.updatedAt>stored.updatedAt)byId.set(chat.id,chat);}
  return [...byId.values()].sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)).slice(0,50);
}
