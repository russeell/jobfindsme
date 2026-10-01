import {useEffect,useRef} from 'react';
import type {ResumeState} from '../../../shared/contracts';
import {ResumePage} from './ResumePage';

export function ResumeDialog({onClose,onChanged}:{onClose():void;onChanged(state:ResumeState):void}){
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const previous=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();if(previous?.isConnected)previous.focus();};},[]);
  return <dialog ref={dialog} className="resume-dialog" aria-labelledby="resume-dialog-title" onCancel={event=>{event.preventDefault();onClose();}} onClick={event=>{if(event.target===event.currentTarget)onClose();}}>
    <header><div><span className="preparation-eyebrow">你的求职材料</span><h2 id="resume-dialog-title">我的简历</h2></div><button type="button" className="preparation-close" aria-label="关闭简历" onClick={onClose}>×</button></header>
    <div className="resume-dialog-body"><ResumePage embedded onChanged={onChanged}/></div>
  </dialog>;
}
