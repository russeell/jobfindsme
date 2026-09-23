import {userError} from "../../../shared/user-errors";
import {browserIsOccluded,type BrowserOverlay} from "../../../shared/browser-overlays";
import type {SourceBrowserState} from "../../../shared/contracts";
import {type BrowserDestination} from "../../../shared/browser-search";
import {BrowserStartPage} from "./BrowserStartPage";
import {BrowserAddressBar} from "./BrowserAddressBar";
import { Icon } from "./Icon";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode, type CSSProperties } from "react";

type Target = { sourceId: string; url?: string; title: string };
const BrowserContext = createContext<(target: Target) => void>(() => {});
export const useOriginalBrowser = () => useContext(BrowserContext);
const ToggleContext = createContext({open:false,toggle:() => {}});
export function BrowserToggle() { const {open,toggle} = useContext(ToggleContext); return <button className="browser-toggle" aria-label={open ? "收起浏览器" : "打开浏览器"} title={open ? "收起浏览器" : "打开浏览器"} aria-pressed={open} onClick={toggle}><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M15 4v16"/></svg></button>; }
function stored(key: string, fallback: number, min: number, max: number) {
  const value = Number(localStorage.getItem(key) ?? fallback);
  return Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback;
}
export function Splitter({ label, value, min, max, onChange, reverse = false, cancelKey }: { label: string; value: number; min: number; max: number; onChange(value: number): void; reverse?: boolean; cancelKey?: string }) {
  const stopRef = useRef<() => void>(() => {});
  const current = useRef({min, max, onChange});
  current.current = {min, max, onChange};
  // Layout switches can hide/unmount the captured divider before pointerup arrives.
  useEffect(() => () => stopRef.current(), [cancelKey]);
  const apply = (n: number) => { const c = current.current; c.onChange(Math.max(c.min, Math.min(c.max, n))); };
  return <div className="splitter" role="separator" aria-label={label} aria-orientation="vertical" aria-valuenow={Math.round(value)} aria-valuemin={min} aria-valuemax={max} tabIndex={0}
    onKeyDown={e => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) { e.preventDefault(); apply(e.key === "Home" ? min : e.key === "End" ? max : value + (e.key === "ArrowRight" ? 16 : -16) * (reverse ? -1 : 1)); } }}
    onPointerDown={e => {
      if (e.button !== 0 || !e.isPrimary) return;
      e.preventDefault();
      stopRef.current();
      const start = e.clientX, node = e.currentTarget, pointerId = e.pointerId;
      let stopped = false, captureFrame = 0;
      const stop = () => {
        if (stopped) return;
        stopped = true;
        cancelAnimationFrame(captureFrame);
        window.removeEventListener("pointermove", move, true);
        window.removeEventListener("pointerup", end, true);
        window.removeEventListener("pointercancel", end, true);
        window.removeEventListener("mouseup", stop, true);
        window.removeEventListener("blur", stop);
        window.removeEventListener("keydown", key, true);
        window.removeEventListener("mouseout", leave, true);
        document.removeEventListener("visibilitychange", visibility);
        node.removeEventListener("lostpointercapture", end);
        document.body.classList.remove("resizing");
        if (node.hasPointerCapture(pointerId)) node.releasePointerCapture(pointerId);
      };
      const end = (event: PointerEvent) => { if (event.pointerId === pointerId) stop(); };
      const move = (event: PointerEvent) => {
        if (event.pointerId !== pointerId) return;
        if (!(event.buttons & 1)) { stop(); return; }
        apply(value + (event.clientX - start) * (reverse ? -1 : 1));
      };
      const key = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); stop(); } };
      const leave = (event: MouseEvent) => { if (!event.relatedTarget) stop(); };
      const visibility = () => { if (document.hidden) stop(); };
      stopRef.current = stop;
      window.addEventListener("pointermove", move, true);
      window.addEventListener("pointerup", end, true);
      window.addEventListener("pointercancel", end, true);
      window.addEventListener("mouseup", stop, true);
      window.addEventListener("blur", stop);
      window.addEventListener("keydown", key, true);
      window.addEventListener("mouseout", leave, true);
      document.addEventListener("visibilitychange", visibility);
      node.addEventListener("lostpointercapture", end);
      document.body.classList.add("resizing");
      try {
        node.setPointerCapture(pointerId);
        // Native WebContentsView boundaries can swallow the DOM capture-loss event.
        const watchCapture = () => {
          if (stopped) return;
          if (!node.isConnected || !node.getClientRects().length || !node.hasPointerCapture(pointerId)) { stop(); return; }
          captureFrame = requestAnimationFrame(watchCapture);
        };
        captureFrame = requestAnimationFrame(watchCapture);
      } catch { stop(); }
    }} />;
}
export function Workbench({ sidebar, children, onError }: { sidebar: ReactNode; children: ReactNode; onError(message: string): void }) {
  const [sidebarWidth, setSidebarWidth] = useState(() => stored("jfm.sidebar.width", 196, 160, 300));
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("jfm.sidebar.collapsed") === "true");
  const [browserWidth, setBrowserWidth] = useState(() => stored("jfm.browser.width", 650, 520, 1200));
  const [target, setTarget] = useState<Target>();
  const [panelOpen,setPanelOpen] = useState(false);
  const [browserExpanded,setBrowserExpanded] = useState(false);

  const hasBrowser = panelOpen;
  const [newTab,setNewTab]=useState(false);
  const [tabError,setTabError]=useState("");
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  const autoCollapsed=panelOpen && !browserExpanded && windowWidth>=944 && windowWidth<sidebarWidth+880;
  const effectiveCollapsed=collapsed || browserExpanded || autoCollapsed;
  const narrow = windowWidth < (effectiveCollapsed ? 64 : sidebarWidth) + 880;
  const [mode, setMode] = useState<"work" | "browser">("work");
  const [browserState, setBrowserState] = useState<SourceBrowserState>({ url: "", canGoBack: false, canGoForward: false, loading: false,activeTabId:null,tabs:[],notice:"",zoom:1 });
  const activeTab=browserState.tabs.find(t=>t.id===browserState.activeTabId);
  const slot = useRef<HTMLDivElement>(null);
  const splitterContext = `${hasBrowser}:${effectiveCollapsed}:${narrow}:${mode}:${browserExpanded}:${newTab}:${browserState.activeTabId}:${windowWidth}`;
  const visible = hasBrowser && !newTab && !!activeTab && (browserExpanded || !narrow || mode === "browser");
  useEffect(() => { localStorage.setItem("jfm.sidebar.width", String(sidebarWidth)); }, [sidebarWidth]);
  useEffect(() => { localStorage.setItem("jfm.sidebar.collapsed", String(collapsed)); }, [collapsed]);
  useEffect(() => { localStorage.setItem("jfm.browser.width", String(browserWidth)); }, [browserWidth]);
  useEffect(() => { const resize = () => setWindowWidth(window.innerWidth); window.addEventListener("resize", resize); return () => window.removeEventListener("resize", resize); }, []);
  // Opening a target creates/reuses a tab. Restoring the panel only restores layout.
  useEffect(() => { if (!target || !slot.current) return; const r=slot.current.getBoundingClientRect();setTabError("");void window.jobfindsme!.openJobOriginal(target.sourceId,target.url??"",{x:r.x,y:r.y,width:r.width,height:r.height}).catch(e=>setTabError(String(e))).finally(()=>void window.jobfindsme!.sourceBrowserCommand("state").then(setBrowserState)); }, [target]);
  useEffect(() => {
    let frame=0,lastLayout="";
    const selector="[data-browser-overlay],dialog[open],[aria-modal='true']";
    const overlays=()=>Array.from(document.querySelectorAll<HTMLElement>(selector));
    const update=()=>{
      cancelAnimationFrame(frame);
      frame=requestAnimationFrame(()=>{
        const r=slot.current?.getBoundingClientRect();
        const current:BrowserOverlay[]=overlays().map(element=>{
          const style=getComputedStyle(element),bounds=element.getBoundingClientRect();
          return {kind:element.dataset.browserOverlay==="popover"?"popover":"modal",visible:!!element.getClientRects().length&&style.display!=="none"&&style.visibility!=="hidden"&&Number(style.opacity)!==0,bounds};
        });
        const bounds=r&&visible&&!browserIsOccluded(r,current)?{x:r.x,y:r.y,width:r.width,height:r.height}:null;
        const key=JSON.stringify(bounds);
        if(key!==lastLayout){lastLayout=key;void window.jobfindsme?.layoutSourceBrowser(bounds);}
      });
    };
    const observer=new ResizeObserver(update),observed=new Set<Element>();
    const sync=()=>{
      const current=new Set<Element>([...(slot.current?[slot.current]:[]),...overlays()]);
      for(const element of observed)if(!current.has(element)){observer.unobserve(element);observed.delete(element);}
      for(const element of current)if(!observed.has(element)){observer.observe(element);observed.add(element);}
      update();
    };
    sync();const mutation=new MutationObserver(sync);
    mutation.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:["open","aria-modal","data-browser-overlay","style","class","hidden"]});
    window.addEventListener("resize",update);window.addEventListener("focus",update);window.addEventListener("scroll",update,true);
    return()=>{cancelAnimationFrame(frame);observer.disconnect();mutation.disconnect();window.removeEventListener("resize",update);window.removeEventListener("focus",update);window.removeEventListener("scroll",update,true);};
  }, [target, visible, sidebarWidth, collapsed, browserWidth, narrow, mode, browserExpanded, browserState.activeTabId]);
  useEffect(() => { if (!panelOpen) return; const refresh = () => void window.jobfindsme?.sourceBrowserCommand("state").then(setBrowserState); refresh(); const timer = setInterval(refresh, 700); return () => clearInterval(timer); }, [panelOpen]);
  useEffect(() => () => { void window.jobfindsme?.closeSourceBrowser(); }, []);
  function openDestination(destination:Extract<BrowserDestination,{url:string}>) {
    setTarget({sourceId:destination.sourceId,url:destination.url,title:"浏览网页"});setNewTab(false);setTabError("");
  }
  function navigateAddress(destination:Extract<BrowserDestination,{url:string}>) {
    setTabError("");
    if(newTab||!activeTab){openDestination(destination);return;}
    const id=activeTab.id;
    void window.jobfindsme!.navigateBrowserTab(id,destination.url).then(setBrowserState).catch(async error=>{
      const state=await window.jobfindsme!.sourceBrowserCommand("state");setBrowserState(state);
      if(state.activeTabId===id)setTabError(String(error));
    });
  }
  function command(value: Parameters<NonNullable<typeof window.jobfindsme>["sourceBrowserCommand"]>[0]) { setTabError(""); void window.jobfindsme!.sourceBrowserCommand(value).then(setBrowserState).catch(e=>setTabError(String(e))); }
  function close() { void window.jobfindsme?.layoutSourceBrowser(null); setPanelOpen(false); setBrowserExpanded(false); setMode("work"); }
  function toggle() { if (panelOpen) close(); else { if (!browserState.tabs.length) setNewTab(true); setPanelOpen(true); setMode("browser"); } }
  return <BrowserContext.Provider value={value => { setTarget(value); setNewTab(false); setPanelOpen(true); setMode("browser"); }}><ToggleContext.Provider value={{open:hasBrowser,toggle}}><main className={`shell ${effectiveCollapsed ? "sidebar-collapsed" : ""} ${hasBrowser ? "has-browser" : ""} ${narrow ? "narrow-shell" : ""} ${browserExpanded ? "browser-expanded" : ""} ${narrow && hasBrowser && mode === "browser" ? "browser-mode" : ""}`} style={{ "--sidebar-width": `${effectiveCollapsed ? 64 : sidebarWidth}px`, "--browser-width": `${browserWidth}px` } as CSSProperties}>
    <aside className="sidebar" onClick={() => { setMode("work"); setBrowserExpanded(false); }}><button className="collapse-sidebar" title={effectiveCollapsed ? "展开侧边栏" : "收起侧边栏"} aria-label={effectiveCollapsed ? "展开侧边栏" : "收起侧边栏"} onClick={() => { setBrowserExpanded(false); setCollapsed(!effectiveCollapsed); }}><Icon name="panelLeft" /></button>{sidebar}</aside>
    {!effectiveCollapsed && <Splitter label="侧边栏宽度" value={sidebarWidth} min={160} max={300} onChange={setSidebarWidth} cancelKey={splitterContext} />}
    {hasBrowser && narrow && <div className="work-mode-switch"><button className={mode === "work" ? "active" : ""} onClick={() => { setMode("work"); setBrowserExpanded(false); }}>工作区</button><button className={mode === "browser" ? "active" : ""} onClick={() => setMode("browser")}>岗位原页</button><button onClick={close} aria-label="关闭原页">×</button></div>}
    <div className="work-content">{children}</div>
    {hasBrowser && <><div className="browser-divider"><Splitter label="原页面板宽度" value={browserWidth} min={520} max={Math.min(1200, Math.max(520, windowWidth - (effectiveCollapsed ? 64 : sidebarWidth) - 360))} reverse onChange={setBrowserWidth} cancelKey={splitterContext} /></div><aside className="browser-panel"><div className="browser-tabbar" role="tablist" aria-label="浏览器标签">{browserState.tabs.map(tab=><div key={tab.id} className={tab.id===browserState.activeTabId&&!newTab?"browser-tab active":"browser-tab"}><button role="tab" aria-selected={tab.id===browserState.activeTabId&&!newTab} title={tab.url} onClick={()=>{setNewTab(false);void window.jobfindsme!.selectBrowserTab(tab.id).then(setBrowserState).catch(e=>setTabError(String(e)));}}>{tab.loading?"◌ ":""}{tab.title}</button><button aria-label={`关闭标签 ${tab.title}`} onClick={()=>void window.jobfindsme!.closeBrowserTab(tab.id).then(state=>{setBrowserState(state);if(!state.tabs.length)setNewTab(true);})}>×</button></div>)}<button className="new-browser-tab" aria-label="新建标签" disabled={browserState.tabs.length>=12} onClick={()=>{setNewTab(true);setTabError("");}}>＋</button></div><div className="browser-toolbar"><div className="browser-nav"><button aria-label="返回" disabled={newTab || !browserState.canGoBack} onClick={() => command("back")}>←</button><button aria-label="前进" disabled={newTab || !browserState.canGoForward} onClick={() => command("forward")}>→</button><button aria-label="刷新" disabled={newTab} onClick={() => command("reload")}>↻</button><BrowserAddressBar url={browserState.url} tabId={browserState.activeTabId} newTab={newTab} onNavigate={navigateAddress} onError={setTabError}/>{!newTab && activeTab && <div className="browser-zoom"><button aria-label="缩小网页" disabled={browserState.zoom<=.3} onClick={()=>command("zoom-out")}>−</button><button aria-label="恢复100%" title="恢复100%" onClick={()=>command("zoom-reset")}>{Math.round(browserState.zoom*100)}%</button><button aria-label="放大网页" disabled={browserState.zoom>=2} onClick={()=>command("zoom-in")}>＋</button><button disabled={browserState.loading||browserState.fitting} onClick={()=>command("fit-width")}>{browserState.fitting?"适应中…":"适应宽度"}</button></div>}<button className="browser-expand" aria-label={browserExpanded ? "返回分栏" : "放大浏览器"} title={browserExpanded ? "返回分栏，恢复面板宽度" : "放大浏览器，使用主工作区"} onClick={() => {setBrowserExpanded(!browserExpanded);setMode("browser");}}><Icon name={browserExpanded ? "split" : "expand"} /></button><button aria-label="关闭原页" onClick={close}>×</button></div>{(tabError || browserState.notice || activeTab?.error)&&<div className="browser-error" role="alert"><p>{userError(tabError || browserState.notice || activeTab?.error).message}</p>{!newTab && activeTab && <button onClick={()=>command("reload")}>重试</button>}{!newTab && browserState.canGoBack && <button onClick={()=>command("back")}>返回上一页</button>}</div>}</div><div className="native-browser-slot" ref={slot}>{newTab||!activeTab?<BrowserStartPage onOpen={openDestination} limitReached={browserState.tabs.length>=12}/>:<p>平台原页面 · 共享来源登录会话</p>}</div></aside></>}
  </main></ToggleContext.Provider></BrowserContext.Provider>;
}
