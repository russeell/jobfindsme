import test from 'node:test';
import assert from 'node:assert/strict';
import {checkResearchClaim,researchClaimText} from '../dist-electron/shared/research-claim-support.js';
const company='示例公司';
const check=(statement,quote)=>checkResearchClaim({statement,quote,evidence_ids:['e'],category:'business'},new Map([['e',{excerpt:quote,url:'https://example.com/source',verification_status:'independently_retrieved',context:{source_type:'public_web'}}]]),company);
test('swapping numeric measures or teams is rejected even if all numbers appear',()=>{
 assert.equal(check('示例公司利润100亿元，营收10亿元','示例公司营收100亿元，利润10亿元'),undefined);
 assert.equal(check('示例公司北京团队加班10小时，上海团队加班20小时','示例公司北京团队加班20小时，上海团队加班10小时'),undefined);
});
test('current-time verbatim excerpt remains a source-time statement; paraphrase is rejected',()=>{
 const quote='示例公司目前在上海设立了研发团队';assert.ok(check(quote,quote));assert.match(researchClaimText(check(quote,quote)),/来源当时记载.*当前情况未核实/);
 assert.equal(check('示例公司目前在上海设立研发团队',quote),undefined);
});
