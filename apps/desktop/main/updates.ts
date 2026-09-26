export type UpdateResult = {status:"available"|"current"|"unpublished";tag?:string;message:string};
export const releasesUrl="https://github.com/russeell/jobfindsme/releases";
export async function checkForUpdates(currentTag:string,platform:string,request:typeof fetch=fetch):Promise<UpdateResult>{
  const response=await request("https://api.github.com/repos/russeell/jobfindsme/releases/latest",{headers:{Accept:"application/vnd.github+json"},signal:AbortSignal.timeout(10000),redirect:"error"});
  if(response.status===404)return {status:"unpublished",message:"尚无正式发布版本。仓库代码更新不等于可安装的桌面更新。"};
  if(!response.ok)throw Error(response.status===403||response.status===429?"检查更新受到服务限流，请稍后重试。":"无法连接版本服务，请稍后重试。");
  const release=await response.json() as {tag_name?:string;draft?:boolean;prerelease?:boolean;assets?:{name:string}[]};
  if(!release.tag_name||release.draft||release.prerelease)throw Error("版本服务返回了无效的正式版本信息。");
  const compatible=(release.assets??[]).some(asset=>platform==="darwin"?/\.(dmg|zip)$/i.test(asset.name)&&!/win|linux/i.test(asset.name):platform==="win32"?(/\.(exe|msi)$/i.test(asset.name)||/windows.*\.zip$/i.test(asset.name)):/\.(AppImage|deb|rpm)$/i.test(asset.name));
  if(!compatible)return {status:"unpublished",tag:release.tag_name,message:"找到发布记录，但尚无适用于当前系统的桌面安装包。"};
  if(currentTag===release.tag_name)return {status:"current",tag:release.tag_name,message:"当前已安装此正式版本。"};
  return {status:"available",tag:release.tag_name,message:"发现可下载的正式版本。预览构建与正式版本不作新旧排序，请查看发布说明后安装。"};
}
