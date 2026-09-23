import {createContext,useContext,useEffect,useId,useLayoutEffect,useRef,useState,type ReactNode} from "react";
import {createPortal} from "react-dom";

const ParentPopover=createContext<{id:string;boundary:Element|null}|null>(null);

export function PopoverButton({label,title,children,chosen=false,disabled=false,width=300}: {label:ReactNode;title:string;children:ReactNode|((close:()=>void)=>ReactNode);chosen?:boolean;disabled?:boolean;width?:number}) {
  const [open,setOpen]=useState(false);
  const [position,setPosition]=useState({left:12,top:80,width});
  const trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null);
  const id=useId(),parent=useContext(ParentPopover);
  const boundary=trigger.current?.closest(".work-content") ?? parent?.boundary ?? null;
  const close=(restoreFocus=true)=>{setOpen(false);if(restoreFocus)trigger.current?.focus();};

  useLayoutEffect(()=>{
    if(!open)return;
    let frame=0;
    const place=()=>{
      const anchor=trigger.current;
      if(!anchor?.isConnected)return close(false);
      const r=anchor.getBoundingClientRect();
      if(!r.width||!r.height)return close(false);
      const scope=(anchor.closest(".work-content") ?? parent?.boundary)?.getBoundingClientRect();
      const leftEdge=Math.max(12,(scope?.left ?? 0)+12),rightEdge=Math.min(innerWidth-12,(scope?.right ?? innerWidth)-12);
      const panelWidth=Math.min(width,Math.max(0,rightEdge-leftEdge));
      const next={width:panelWidth,left:Math.max(leftEdge,Math.min(r.left,rightEdge-panelWidth)),top:Math.max(12,Math.min(r.bottom+6,innerHeight-(panel.current?.offsetHeight ?? 260)-12))};
      setPosition(old=>old.left===next.left&&old.top===next.top&&old.width===next.width?old:next);
    };
    const schedule=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(place);};
    place();
    const resize=new ResizeObserver(schedule);if(trigger.current)resize.observe(trigger.current);if(panel.current)resize.observe(panel.current);
    const mutation=new MutationObserver(schedule);mutation.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:["hidden","class","style"]});
    window.addEventListener("resize",schedule);window.addEventListener("scroll",schedule,true);
    return()=>{cancelAnimationFrame(frame);resize.disconnect();mutation.disconnect();window.removeEventListener("resize",schedule);window.removeEventListener("scroll",schedule,true);};
  },[open,width,parent?.boundary]);

  useEffect(()=>{
    if(!open)return;
    panel.current?.querySelector<HTMLElement>("input,select,button,textarea,[tabindex='0']")?.focus();
    const contains=(target:EventTarget|null)=>{
      if(!(target instanceof Node))return false;
      if(trigger.current?.contains(target)||panel.current?.contains(target))return true;
      let child=(target instanceof Element?target:target.parentElement)?.closest<HTMLElement>("[data-popover-panel]");
      while(child){if(child.id===id)return true;child=child.dataset.popoverParent?document.getElementById(child.dataset.popoverParent):null;}
      return false;
    };
    const outside=(event:Event)=>{if(!contains(event.target))close(false);};
    const escape=(event:KeyboardEvent)=>{
      if(event.key!=="Escape"||Array.from(document.querySelectorAll("[data-popover-panel]")).at(-1)!==panel.current)return;
      event.preventDefault();event.stopPropagation();close();
    };
    document.addEventListener("pointerdown",outside,true);document.addEventListener("focusin",outside);document.addEventListener("keydown",escape);
    const unsubscribe=window.jobfindsme?.onSourceBrowserFocus?.(()=>close(false));
    return()=>{document.removeEventListener("pointerdown",outside,true);document.removeEventListener("focusin",outside);document.removeEventListener("keydown",escape);unsubscribe?.();};
  },[open,id]);

  return <><button ref={trigger} type="button" className={`popover-trigger ${chosen?"chosen":""}`} aria-label={title} title={title} aria-haspopup="dialog" aria-expanded={open} disabled={disabled} onClick={()=>setOpen(!open)}>{label}<span aria-hidden="true">⌄</span></button>{open&&createPortal(<ParentPopover.Provider value={{id,boundary}}><div ref={panel} id={id} data-popover-panel="" data-popover-parent={parent?.id} data-browser-overlay="popover" className="filter-popover" role="dialog" aria-modal="false" aria-label={title} style={position}><div className="popover-heading"><strong>{title}</strong><button type="button" aria-label={`关闭${title}`} onClick={()=>close()}>×</button></div>{typeof children==="function"?children(()=>close()):children}</div></ParentPopover.Provider>,document.body)}</>;
}
