import {useEffect,useState} from "react";
import {type SourceBrowserId} from "../../../main/source-browser-policy";
import {browserSiteNames,normalizeSearchEngine,resolveWebsiteHomepage,resolveWebSearch,searchEngineNames,type BrowserDestination} from "../../../shared/browser-search";

export function BrowserStartPage({onOpen,limitReached}:{onOpen(destination:Extract<BrowserDestination,{url:string}>):void;limitReached:boolean}) {
  const [mode,setMode]=useState<"website"|"search">("website");
  const [site,setSite]=useState<SourceBrowserId|"">("");
  const [keywords,setKeywords]=useState("");
  const [engine,setEngine]=useState(()=>normalizeSearchEngine(localStorage.getItem("jfm.browser.search-engine")));
  useEffect(()=>{localStorage.setItem("jfm.browser.search-engine",engine);},[engine]);
  const destination=mode==="website"?resolveWebsiteHomepage(site):resolveWebSearch(keywords,engine);
  return <form className="browser-new-page" onSubmit={e=>{e.preventDefault();if("url" in destination)onOpen(destination);}}>
    <div className="browser-start-modes" role="tablist" aria-label="新标签操作">
      <button type="button" role="tab" aria-selected={mode==="website"} onClick={()=>setMode("website")}>打开招聘网站</button>
      <button type="button" role="tab" aria-selected={mode==="search"} onClick={()=>setMode("search")}>网页搜索</button>
    </div>
    {mode==="website" ? <>
      <label>招聘网站<select aria-label="招聘网站" value={site} onChange={e=>setSite(e.target.value as SourceBrowserId)}><option value="">选择招聘网站</option>{Object.entries(browserSiteNames).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
    </> : <>
      <label>搜索关键词<input aria-label="搜索关键词" value={keywords} onChange={e=>setKeywords(e.target.value)} placeholder="例如 AI 工程师"/></label>
    </>}
    {destination.kind==="invalid"&&<p className="error-message" role="alert">{destination.summary}</p>}
    <div className="browser-start-actions">
      {mode==="search"&&<label>搜索引擎<select aria-label="搜索引擎" value={engine} onChange={e=>setEngine(normalizeSearchEngine(e.target.value))}>{Object.entries(searchEngineNames).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>}
      <button className="primary-button" disabled={limitReached||!("url" in destination)}>{mode==="website"?"打开网站":"搜索"}</button>
    </div>
  </form>;
}
