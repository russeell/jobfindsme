export type UpdateResult = {status:"available"|"current"|"unpublished";tag?:string;message:string};
export const releasesUrl="https://github.com/russeell/jobfindsme/releases";
function version(tag:string):number[]|undefined{
  const match=/^v?(\d+)\.(\d+)\.(\d+)$/.exec(tag);
  return match?.slice(1).map(Number);
}
function isNewer(latest:string,current:string):boolean{
  const next=version(latest)!,installed=version(current)!;
  for(let i=0;i<3;i++){if(next[i]!==installed[i])return next[i]>installed[i];}
  return false;
}
function compatibleAsset(name:string,platform:string,arch:string):boolean{
  if(platform==="darwin")return arch==="arm64"?/^mac-arm64\.zip$/i.test(name):/^mac-x64\.zip$/i.test(name);
  if(platform==="win32")return arch==="x64"?/^windows-x64\.zip$/i.test(name):/^windows-arm64\.zip$/i.test(name);
  return false;
}
export async function checkForUpdates(currentTag:string,platform:string,request:typeof fetch=fetch,arch=process.arch):Promise<UpdateResult>{
  const response=await request("https://api.github.com/repos/russeell/jobfindsme/releases/latest",{headers:{Accept:"application/vnd.github+json"},signal:AbortSignal.timeout(10000),redirect:"error"});
  if(response.status===404)return {status:"unpublished",message:"尚无正式发布版本。仓库代码更新不等于可安装的桌面更新。"};
  if(!response.ok)throw Error(response.status===403||response.status===429?"检查更新受到服务限流，请稍后重试。":"无法连接版本服务，请稍后重试。");
  const release=await response.json() as {tag_name?:string;draft?:boolean;prerelease?:boolean;assets?:{name:string}[]};
  if(!release.tag_name||release.draft||release.prerelease)throw Error("版本服务返回了无效的正式版本信息。");
  const compatible=(release.assets??[]).some(asset=>compatibleAsset(asset.name,platform,arch));
  if(!compatible)return {status:"unpublished",tag:release.tag_name,message:"找到发布记录，但尚无适用于当前系统的桌面安装包。"};
  if(!version(release.tag_name)||!version(currentTag))throw Error("无法比较当前版本与正式版本，请到发布页核对。");
  if(!isNewer(release.tag_name,currentTag))return {status:"current",tag:release.tag_name,message:"当前版本已是最新，或比最新正式版更新。"};
  return {status:"available",tag:release.tag_name,message:"发现新版本。请查看发布说明，再从发布页下载安装。"};
}
