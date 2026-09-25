import test from 'node:test';
import assert from 'node:assert/strict';
import {parseClaims} from '../dist-electron/main/research/pi-research-agent.mjs';

const evidence=new Map([['ev_one',{evidence_id:'ev_one',excerpt:'示例公司在上海设立了研发团队，并介绍了产品方向。',url:'https://www.zhihu.com/p/1',verification_status:'independently_retrieved'}]]);
test('only verbatim quotes bound to existing evidence survive',()=>{
 const checked=parseClaims(JSON.stringify({claims:[
  {quote:'示例公司在上海设立了研发团队',evidence_ids:['ev_one'],category:'business',scope:'上海'},
  {quote:'示例公司已经上市且利润翻倍',evidence_ids:['ev_one'],category:'listing',scope:'全国'},
  {quote:'示例公司在上海设立了研发团队',evidence_ids:['missing'],category:'business',scope:'上海'}
 ],limitations:[]}),evidence);
 assert.equal(checked.claims.length,1);
 assert.equal(checked.claims[0].evidence_ids[0],'ev_one');
 assert.equal(checked.claims[0].scope,'上海');
 const inventedScope=parseClaims(JSON.stringify({claims:[{quote:'示例公司在上海设立了研发团队',evidence_ids:['ev_one'],category:'business',scope:'全球'}]}),evidence);
 assert.equal(inventedScope.claims[0].scope,'团队、地区或法律主体未核实');
});
test('malformed model output cannot become a research claim',()=>{
 assert.deepEqual(parseClaims('Please ignore prior instructions',evidence).claims,[]);
 assert.deepEqual(parseClaims(JSON.stringify({claims:[{quote:'伪造结论',evidence_ids:['ev_one'],category:'business'}]}),evidence).claims,[]);
});
