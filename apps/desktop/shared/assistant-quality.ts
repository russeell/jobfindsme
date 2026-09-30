/** Small delivery checks, not a substitute for evaluating the model's meaning. */
export function interviewResponseIssue(text:string,request:string,hasPreviousQuestion:boolean):string|undefined {
 if(/结束|暂停|总结|参考答案|答题示例|准备清单|题库|列出.*问题|(?:多|几|\d+)道题/u.test(request))return;
 const questions=text.match(/[?？]/gu)||[];
 if(questions.length>1)return 'multiple_questions';
 if(!questions.length)return 'question_missing';
 if(hasPreviousQuestion&&!/(?:做得|说清|清楚|有效|准确|优点|亮点|不足|遗漏|改进|尚未|没说|还缺|需要补|建议)/u.test(text))return 'feedback_missing';
}
export function researchDomainMatches(url:string,domains:string[]):boolean {
 if(!domains.length)return true;
 try{const host=new URL(url).hostname.toLowerCase();return domains.some(value=>{const domain=value.toLowerCase();return host===domain||host.endsWith(`.${domain}`);});}catch{return false;}
}
