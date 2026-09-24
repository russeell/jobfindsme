import {useState} from "react";
import type {JobTrackingState} from "../../../shared/contracts";
import {PopoverButton} from "../shared/PopoverButton";

export function JobActions({tracking,onTrack,onOpen,onResearch,onError,researchDisabledReason,hasReport}: {tracking:JobTrackingState;onTrack(event:"read"|"saved"|"applied",enabled:boolean):Promise<unknown>;onOpen():Promise<unknown>;onResearch?():void;researchDisabledReason?:string;hasReport?:boolean;onError(message?:string):void}) {
  const [pending,setPending]=useState("");
  async function perform(name:string,action:()=>Promise<unknown>) {
    if(pending)return;setPending(name);onError(undefined);
    try{await action();}catch(e){onError(e instanceof Error?e.message:String(e));}finally{setPending("");}
  }
  return <div className="job-actions"><div className="job-action-buttons"><button className="primary-button" disabled={!!pending} onClick={()=>void perform("open",onOpen)}>{pending==="open"?"正在打开…":"查看岗位原页 ↗"}</button>{onResearch&&<button className="research-job-action" disabled={!!pending||!!researchDisabledReason} title={researchDisabledReason} onClick={onResearch}>{hasReport?"查看研究报告":"研究岗位"}</button>}<button className={`save-job ${tracking.saved?"is-saved":""}`} title={tracking.saved?"取消收藏岗位":"收藏岗位"} aria-pressed={tracking.saved} disabled={!!pending} onClick={()=>void perform("saved",()=>onTrack("saved",!tracking.saved))}><span aria-hidden="true">{tracking.saved?"★":"☆"}</span>{tracking.saved?"已收藏":"收藏"}</button></div><PopoverButton title="更新岗位状态" disabled={!!pending} label={<span className="job-status-text">{tracking.read?"✓ 已读":"未读"} · {tracking.applied?"✓ 已投递":"未投递"}</span>}>{close=><><p className="note">打开链接不代表已经投递，请按实际进度更新。</p><button className="status-option" aria-pressed={tracking.read} onClick={()=>{close();void perform("read",()=>onTrack("read",!tracking.read));}}>{tracking.read?"撤销已读":"标为已读"}</button><button className="status-option" aria-pressed={tracking.applied} onClick={()=>{close();void perform("applied",()=>onTrack("applied",!tracking.applied));}}>{tracking.applied?"撤销已投递":"确认已投递"}</button></>}</PopoverButton></div>;
}
