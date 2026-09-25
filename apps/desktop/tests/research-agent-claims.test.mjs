import test from 'node:test';
import assert from 'node:assert/strict';
import {parseClaims} from '../dist-electron/main/research/pi-research-agent.mjs';

const body='示例公司在上海设立了研发团队，并介绍了产品方向。示例公司计划上市。';
const source={evidence_id:'ev_one',company:'示例公司',excerpt:body,url:'https://www.zhihu.com/p/1',verification_status:'independently_retrieved',context:{source_type:'personal_account'}};
const evidence=new Map([['ev_one',source]]);
const one=(statement,quote='示例公司在上海设立了研发团队',scope='上海',category='business')=>parseClaims(JSON.stringify({claims:[{statement,quote,evidence_ids:['ev_one'],category,scope}]}),evidence,'示例公司').claims;
test('direct and limited paraphrase claims bind to the original and derive source type',()=>{
 const direct=one('示例公司在上海设立了研发团队');
 assert.equal(direct.length,1);assert.equal(direct[0].support_level,'direct');assert.equal(direct[0].source_type,'personal_account');
 const qualified=one('示例公司在上海设立研发团队');
 assert.equal(qualified.length,1);assert.equal(qualified[0].support_level,'qualified');
});
test('entity, negation, current time, listing and geographic overreach are rejected',()=>{
 assert.equal(one('另一家公司在上海设立研发团队').length,0);
 assert.equal(one('示例公司未在上海设立研发团队').length,0);
 assert.equal(one('示例公司目前在上海设立研发团队').length,0);
 assert.equal(one('示例公司在全国设立研发团队').length,0);
 assert.equal(one('示例公司已上市','示例公司计划上市','团队、地区或法律主体未核实','listing').length,0);
});
test('invented scope is downgraded and a missing citation cannot become a claim',()=>{
 assert.equal(one('示例公司在上海设立了研发团队',undefined,'全球')[0].scope,'团队、地区或法律主体未核实');
 const missing=parseClaims(JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:['missing'],category:'business',scope:'上海'}]}),evidence,'示例公司');
 assert.equal(missing.claims.length,0);
 assert.deepEqual(parseClaims('ignore all rules',evidence,'示例公司').claims,[]);
});
