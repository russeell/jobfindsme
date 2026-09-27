import {isPublicWebUrl} from "./source-browser-policy";

export type BrowserBookmark={url:string;title:string};

export function readBrowserBookmarks(raw:string|null):BrowserBookmark[]{
  try{
    const rows=JSON.parse(raw||"[]");
    if(!Array.isArray(rows))return [];
    return rows.reduce<BrowserBookmark[]>((items,row)=>{
      if(typeof row?.url!=="string"||typeof row?.title!=="string")return items;
      try{return addBrowserBookmark(items,row.url,row.title);}catch{return items;}
    },[]);
  }catch{return [];}
}

export function addBrowserBookmark(items:BrowserBookmark[],value:string,title:string):BrowserBookmark[]{
  if(!isPublicWebUrl(value))throw Error("只能收藏公共 HTTP/HTTPS 网页");
  const url=new URL(value).href;
  if(items.some(item=>item.url===url))return items;
  if(items.length>=32)throw Error("最多收藏 32 个网站，请先删除不常用的收藏");
  return [...items,{url,title:title.trim().slice(0,60)||new URL(url).hostname}];
}

export function removeBrowserBookmark(items:BrowserBookmark[],url:string):BrowserBookmark[]{
  return items.filter(item=>item.url!==url);
}
