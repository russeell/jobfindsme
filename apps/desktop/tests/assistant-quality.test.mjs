import test from 'node:test';
import assert from 'node:assert/strict';
import {interviewResponseIssue,researchDomainMatches} from '../dist-electron/shared/assistant-quality.js';
test('interview repair detects several questions, missing question and missing answer feedback',()=>{
 assert.equal(interviewResponseIssue('你负责什么？如何验证？','开始模拟面试',false),'multiple_questions');
 assert.equal(interviewResponseIssue('已记录，等你回答下一题','开始模拟面试',false),'question_missing');
 assert.equal(interviewResponseIssue('怎样验证？','我先写了测试',true),'feedback_missing');
 assert.equal(interviewResponseIssue('你说清了验证思路，但还缺失败分支。怎样覆盖失败分支？','我先写了测试',true),undefined);
 for(const request of ['结束并总结','给我参考答案','列出面试问题','给我3道题'])assert.equal(interviewResponseIssue('清单',''+request,true),undefined);
});
test('research domain constraints apply to candidate host rather than a search engine promise',()=>{
 assert(researchDomainMatches('https://docs.example.org/topic',['example.org']));
 assert(researchDomainMatches('https://example.org/topic',['example.org']));
 assert(!researchDomainMatches('https://example.org.attacker.test/topic',['example.org']));
 assert(!researchDomainMatches('https://another.test/topic',['example.org']));
 assert(researchDomainMatches('https://another.test/topic',[]));
});
