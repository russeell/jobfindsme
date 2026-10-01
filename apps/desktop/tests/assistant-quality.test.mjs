import test from 'node:test';
import assert from 'node:assert/strict';
import {deliveredInterviewQuestion,interviewModeFor,interviewSetupQuestion,interviewResponseIssue,researchDomainMatches} from '../dist-electron/shared/assistant-quality.js';
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

test('interview preparation does not require a JD or masquerade as an answer',()=>{
 assert.equal(interviewModeFor('帮助我准备agent面试'),'prepare');
 assert.equal(interviewResponseIssue('先练工具调用与失败恢复，再用假设项目练习。','帮助我准备agent面试',true),undefined);
 assert.equal(interviewResponseIssue('没有JD就无法开始面试。','开始模拟面试',false),'jd_required');
 assert.equal(interviewResponseIssue('请先提供JD。','帮助我准备agent面试',false),'jd_required');
 assert.equal(interviewResponseIssue('没有JD也能准备，之后可选补充。','帮助我准备agent面试',false),undefined);
 assert.equal(interviewModeFor('准备好了，开始模拟Agent面试','prepare'),'practice');
 assert.equal(interviewModeFor('再展开工具调用的重点','prepare'),'prepare');
 assert.equal(interviewModeFor('给我参考答案'),'reference');
 assert.equal(interviewModeFor('结束并复盘'),'summary');
 assert(interviewSetupQuestion('想练哪个岗位方向？'));
 assert(!interviewSetupQuestion('缓存失效时你会如何处理？'));
 assert.equal(deliveredInterviewQuestion('请解释工具调用超时后的处理过程。'),'请解释工具调用超时后的处理过程');
 assert.equal(interviewResponseIssue('请解释工具调用超时后的处理过程。','开始模拟面试',false),undefined);
});
