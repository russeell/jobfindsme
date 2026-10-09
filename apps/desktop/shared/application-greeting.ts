export const defaultGreeting='您好，我对贵公司的「{岗位}」岗位很感兴趣，希望进一步了解岗位要求与团队情况。方便沟通一下吗？';
export const greetingKey=(workspaceId:string)=>`jfm.application.greeting.${workspaceId}`;
export function renderGreeting(template:string,job:{title:string;company:string}):string{
 return template.replace(/\{(岗位|公司)\}/g,(_match,key)=>key==='岗位'?job.title:job.company).slice(0,3000);
}
