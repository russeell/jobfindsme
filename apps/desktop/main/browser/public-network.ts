import {lookup} from 'node:dns/promises';
import {isIP} from 'node:net';
import {isPublicWebUrl} from '../../shared/source-browser-policy';
export function createPublicNetworkGuard(resolve=lookup){
 const cache=new Map<string,{at:number;allowed:boolean}>();
 return async(value:string):Promise<boolean>=>{
  if(!isPublicWebUrl(value))return false;const url=new URL(value);if(url.port&&!['80','443'].includes(url.port))return false;
  const host=url.hostname.replace(/^\[|\]$/g,'');if(isIP(host))return isPublicWebUrl(value);
  const saved=cache.get(host);if(saved&&Date.now()-saved.at<30000)return saved.allowed;
  try{
   let timer:ReturnType<typeof setTimeout>|undefined;
   const addresses=await Promise.race([resolve(host,{all:true}),new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(Error('DNS timeout')),1500);})]).finally(()=>{if(timer)clearTimeout(timer);});
   const allowed=addresses.length>0&&addresses.every(item=>isPublicWebUrl(`https://${item.family===6?'['+item.address+']':item.address}/`));
   cache.set(host,{at:Date.now(),allowed});if(cache.size>512)cache.delete(cache.keys().next().value!);return allowed;
  }catch{return false;}
 };
}
