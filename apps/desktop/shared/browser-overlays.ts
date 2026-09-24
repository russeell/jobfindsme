export type OverlayBounds = {x:number;y:number;width:number;height:number};
export type BrowserOverlay = {kind:"modal"|"popover";visible:boolean;bounds:OverlayBounds};

export function browserIsOccluded(browser:OverlayBounds, overlays:BrowserOverlay[]):boolean {
  return overlays.some(overlay=>{
    if(!overlay.visible)return false;
    if(overlay.kind==="modal")return true;
    const a=browser,b=overlay.bounds;
    return a.width>0 && a.height>0 && b.width>0 && b.height>0 &&
      Math.min(a.x+a.width,b.x+b.width)>Math.max(a.x,b.x) &&
      Math.min(a.y+a.height,b.y+b.height)>Math.max(a.y,b.y);
  });
}
