import {useEffect,useRef,useState} from "react";
import {resolveBrowserDestination,type BrowserDestination} from "../../../shared/browser-search";

export function BrowserAddressBar({url,tabId,newTab,onNavigate,onError}:{url:string;tabId:string|null;newTab:boolean;onNavigate(destination:Extract<BrowserDestination,{url:string}>):void;onError(message:string):void}) {
  const [editing,setEditing]=useState(false),[draft,setDraft]=useState("");
  const input=useRef<HTMLInputElement>(null);
  useEffect(()=>{setEditing(false);setDraft("");},[tabId,newTab]);
  useEffect(()=>window.jobfindsme?.onSourceBrowserFocus?.(()=>setEditing(false)),[]);
  const current=newTab?"":url;
  return <form className="browser-address-form" onSubmit={e=>{
    e.preventDefault();
    const destination=resolveBrowserDestination(editing?draft:current,"bing");
    if(destination.kind==="empty")return;
    if(!("url" in destination)){onError(destination.summary);return;}
    setEditing(false);input.current?.blur();onNavigate(destination);
  }}><input ref={input} className="browser-address" aria-label="地址或 Bing 搜索" placeholder="搜索 Bing 或输入网址" title="输入网址直接打开；关键词使用 Bing 搜索" value={editing?draft:current}
    onFocus={e=>{setDraft(current);setEditing(true);e.currentTarget.select();}}
    onChange={e=>{setDraft(e.target.value);setEditing(true);}}
    onBlur={()=>setEditing(false)}
    onKeyDown={e=>{if(e.key==="Escape"){e.preventDefault();setEditing(false);input.current?.blur();}else if(e.key==="Enter"&&(e.nativeEvent.isComposing||e.keyCode===229))e.preventDefault();}}
  /></form>;
}
