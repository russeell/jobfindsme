import test from 'node:test';
import assert from 'node:assert/strict';
import {resumeContentChanged,resumeImprovementDraft,resumeReviewCounts} from '../dist-electron/shared/resume-library.js';
const base={basic_information:[],experience:[],projects:['实现本地求职工具'],education:[],skills:['Python']};
test('resume edits ignore empty lines and surrounding whitespace but preserve facts and ordering',()=>{
 assert.equal(resumeContentChanged(base,{...base,projects:[' 实现本地求职工具 ','']}),false);
 assert.equal(resumeContentChanged(base,{...base,skills:['Python','SQL']}),true);
 assert.equal(resumeContentChanged({...base,skills:['Python','SQL']},{...base,skills:['SQL','Python']}),true);
 assert.deepEqual(base.projects,['实现本地求职工具']);
});
test('AI entry carries explicit goal without inventing candidate facts',()=>{
 const general=resumeImprovementDraft('  更简洁  ');
 assert.match(general,/读取已确认简历/);assert.match(general,/我的要求：更简洁/);assert.doesNotMatch(general,/目标公司/);
 const target=resumeImprovementDraft('',{company:'虚构公司',title:'工程师',job_id:'synthetic'});
 assert.match(target,/目标公司：虚构公司；岗位：工程师/);assert.match(target,/独立副本，保留基础简历/);assert.match(target,/不增加未经确认/);
});
test('review counts separate decisions from unresolved evidence',()=>{
 assert.deepEqual(resumeReviewCounts({patches:[{status:'accepted',needs_user_input:[]},{status:'proposed',needs_user_input:['确认事实']},{status:'rejected',needs_user_input:[]}]}),{accepted:1,pending:1,needsInput:1});
});

test('campus and professional preview preserve sections while matching export order',async()=>{
 const {resumeTemplateSections}=await import('../dist-electron/shared/resume-library.js');
 assert.deepEqual(resumeTemplateSections('campus'),['basic_information','education','projects','experience','skills']);
 assert.deepEqual(resumeTemplateSections('professional'),['basic_information','experience','projects','skills','education']);
 assert.deepEqual(resumeTemplateSections('compact'),resumeTemplateSections('professional'));
});
test('greetings substitute only explicit placeholders and isolate workspace preferences',async()=>{
 const {renderGreeting,greetingKey}=await import('../dist-electron/shared/application-greeting.js');
 assert.equal(renderGreeting('你好{公司}，想了解{岗位}。',{company:'虚构公司',title:'工程师'}),'你好虚构公司，想了解工程师。');
 assert.equal(renderGreeting('保留{未知}，{岗位}',{company:'示例',title:'$&'}),'保留{未知}，$&');
 assert.notEqual(greetingKey('a'),greetingKey('b'));
});
