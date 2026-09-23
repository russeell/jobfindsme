/** First-party ATS detail endpoints observed in the corresponding official pages. */
export function publicAtsDetailEndpoint(url:string):string|null {
 const u=new URL(url),id=/^\/index\/position\/(\d+)\/detail\/?$/.exec(u.pathname)?.[1];
 return u.protocol==='https:'&&['vrfi1sk8a0.jobs.feishu.cn','xiaomi.jobs.f.mioffice.cn'].includes(u.hostname)&&id?`${u.origin}/api/v1/job/posts/${id}`:null;
}
export function parsePublicAtsDetail(data:unknown,url:string){
 const value=data as {code?:number;data?:{job_post_detail?:{id?:string;title?:string;description?:string;requirement?:string}}};
 const job=value?.data?.job_post_detail,id=/\/position\/(\d+)\//.exec(url)?.[1];
 if(value?.code!==0||!job||job.id!==id||typeof job.title!=='string'||typeof job.description!=='string'||typeof job.requirement!=='string'||!job.requirement.trim())throw Error('source_contract_error:官网详情结构不完整');
 const description=`职位描述\n${job.description}\n\n职位要求\n${job.requirement}`;
 if(description.length<80||description.length>30000)throw Error('source_contract_error:官网详情长度异常');
 return {title:job.title,company:new URL(url).hostname==='xiaomi.jobs.f.mioffice.cn'?'小米':'MiniMax',description,url};
}
