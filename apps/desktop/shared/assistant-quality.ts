export type InterviewMode='prepare'|'practice'|'reference'|'summary';
export function interviewModeFor(request:string,previous?:InterviewMode):InterviewMode {
 if(/结束|暂停|总结|复盘/u.test(request))return 'summary';
 if(/参考答案|答题示例|题库|列出.*问题|(?:多|几|\d+)道题/u.test(request))return 'reference';
 if(/(?:开始|继续|直接|进入|切换到|换成).{0,12}(?:模拟|练习|面试|问我)|考我|问我.{0,8}(?:一|第).*题/u.test(request))return 'practice';
 if(/准备.*面试|面试.*准备|准备清单|复习|考点|学习计划|备考|怎么准备|如何准备/u.test(request))return 'prepare';
 return previous==='prepare'?'prepare':'practice';
}
export function interviewSetupQuestion(text:string):boolean {
 return /(?:想|要|希望|目标|准备|练习).{0,12}(?:哪个|什么|哪类|哪种).{0,10}(?:岗位|方向|面试)|(?:目标岗位|岗位方向).{0,8}(?:是什么|是哪个)|(?:能否提供|可以提供|是否有|请提供).{0,12}(?:JD|简历|岗位描述)|(?:有|提供).{0,8}(?:JD|简历).{0,4}[吗？?]/iu.test(text);
}
export function deliveredInterviewQuestion(text:string):string|undefined {
 const question=text.match(/[^。！？?\n]+[?？]/u)?.[0].trim();
 if(question)return question.replace(/^(?:接着|继续)?(?:练习一题|第.{1,4}题|问题|追问)[:：]\s*/u,'');
 // A single spoken instruction is a valid question, even without a question mark.
 const prompts=text.split(/\n|[。！]/u).map(line=>line.trim()).filter(line=>/^(?:(?:第.{1,4}题|问题|追问)[:：]\s*)?请(?:介绍|解释|讲述|描述|设计|分析|说明|谈|举|说)/u.test(line));
 return prompts.length===1?prompts[0]:undefined;
}
/** Small delivery checks, not a substitute for evaluating the model's meaning. */
export function interviewResponseIssue(text:string,request:string,hasPreviousQuestion:boolean,mode=interviewModeFor(request)):string|undefined {
 if(mode==='summary'||mode==='reference')return;
 // JD is an optional refinement, never a prerequisite for preparation or practice.
 if(/(?:(?:必须|请先|需要先).{0,8}(?:提供|上传|补充)|先提供|先上传).{0,12}(?:JD|岗位描述|职位描述)|(?:没有|缺少).{0,10}(?:JD|岗位描述|职位描述).{0,16}(?:无法|不能|没法|才能)/iu.test(text))return 'jd_required';
 if(mode==='prepare')return;
 const questions=text.match(/[?？]/gu)||[];
 if(questions.length>1)return 'multiple_questions';
 if(!deliveredInterviewQuestion(text))return 'question_missing';
 if(hasPreviousQuestion&&!interviewSetupQuestion(text)&&!/(?:做得|说清|清楚|有效|准确|优点|亮点|不足|遗漏|改进|尚未|没说|还缺|需要补|建议|具体|说明了)/u.test(text))return 'feedback_missing';
}
export function researchDomainMatches(url:string,domains:string[]):boolean {
 if(!domains.length)return true;
 try{const host=new URL(url).hostname.toLowerCase();return domains.some(value=>{const domain=value.toLowerCase();return host===domain||host.endsWith(`.${domain}`);});}catch{return false;}
}
