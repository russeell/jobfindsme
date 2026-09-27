import test from 'node:test';
import assert from 'node:assert/strict';
import {runInNewContext} from 'node:vm';
import {careerPageScript,careerClickableScript,careerRecords,alibabaSearchUpdated} from '../dist-electron/main/sources/company-page.js';
import {sourceBrowserSpecs} from '../dist-electron/shared/source-browser-policy.js';

const listUrl='https://talent-holding.alibaba.com/off-campus/position-list?lang=zh';
const detailUrl='https://talent-holding.alibaba.com/off-campus/position-detail?positionId=199900160005';

test('Alibaba holding social list uses the verified entry and positionId detail shape',()=>{
  assert.equal(sourceBrowserSpecs.company_03.loginUrl,listUrl);
  assert.match(careerPageScript(),/position-detail/);
  assert.match(careerPageScript(),/positionId/);
  assert.doesNotMatch(careerClickableScript('company_03'),/_1RRlPtjyYmeDGCWt9lrk2P/);
  const anchor={href:detailUrl,innerText:'算法工程师-AI Infra',getBoundingClientRect:()=>({width:150,height:20}),closest:()=>null,querySelectorAll:()=>[]};
  const document={body:{innerText:'阿里巴巴控股集团社会招聘'},querySelectorAll:selector=>selector==='a[href]'?[anchor]:[]};
  const extracted=runInNewContext(careerPageScript(),{document,location:{hostname:'talent-holding.alibaba.com',href:listUrl},getComputedStyle:()=>({visibility:'visible'}),URL});
  assert.equal(extracted.jobs[0]?.url,detailUrl);
  const page={jobs:[
    {title:'算法工程师-AI Infra',url:detailUrl,location:'杭州',company:'阿里巴巴',salary:''},
    {title:'算法工程师-AI Infra',url:'https://talent-holding.alibaba.com/off-campus/position-detail?positionId=199900160006',location:'北京',company:'阿里巴巴',salary:''},
    {title:'算法工程师-AI Infra',url:'https://talent-holding.alibaba.com/off-campus/position-detail?positionId=199900160007',location:'',company:'阿里巴巴',salary:''},
  ],next:false,empty:false,loading:false};
  const result=careerRecords('company_03',listUrl,page,'AI Infra','杭州');
  assert.deepEqual(result.records.map(row=>row.payload.url),[detailUrl]);
});

test('Alibaba click-only card uses the role title and location, not its update date',()=>{
  class Element {constructor(value,children=[]){this.innerText=value;this.children=children;}getBoundingClientRect(){return {width:180,height:30};}click(){this.clicked=true;}}
  const title=new Element('数据技术及产品部-大模型RL Data工程师-物理设备操作 Agent');
  const date=new Element('更新于 2026-09-24');
  const card=new Element(`${title.innerText}\n${date.innerText}\n杭州`,[title,date]);
  const document={querySelectorAll:()=>[title,date,card]};
  const context={document,HTMLElement:Element,getComputedStyle:()=>({cursor:'pointer'})};
  const candidates=runInNewContext(careerClickableScript('company_03'),context);
  assert.deepEqual(JSON.parse(JSON.stringify(candidates)),[{title:title.innerText,location:'杭州'}]);
  runInNewContext(careerClickableScript('company_03',0),context);
  assert.equal(card.clicked,true);
});

test('Alibaba spaced keyword keeps a matching title token but rejects stale unrelated cards',()=>{
  const page={jobs:[
    {title:'智能引擎-Agent Infra研发工程师/专家-杭州',url:detailUrl,location:'杭州',company:'阿里巴巴',salary:''},
    {title:'公关高级经理-广州',url:'https://talent-holding.alibaba.com/off-campus/position-detail?positionId=199900160006',location:'广州',company:'阿里巴巴',salary:''},
  ],next:true,empty:false,loading:false};
  assert.equal(careerRecords('company_03',listUrl,page,'AI Agent','').records.length,1);
});

test('a typed keyword does not confirm an Alibaba search until the site list changes',()=>{
  const before={keyword:'',count:'613',titles:['公关高级经理']};
  assert.equal(alibabaSearchUpdated(before,{keyword:'Agent',count:'613',titles:['公关高级经理']},'Agent'),false);
  assert.equal(alibabaSearchUpdated(before,{keyword:'Agent',count:'30',titles:['公关高级经理']},'Agent'),false);
  assert.equal(alibabaSearchUpdated(before,{keyword:'Agent',count:'30',titles:['销售经理']},'Agent'),false);
  assert.equal(alibabaSearchUpdated(before,{keyword:'Agent',count:'30',titles:['Agent研发工程师']},'Agent'),true);
  assert.equal(alibabaSearchUpdated(before,{keyword:'Other',count:'30',titles:['Agent研发工程师']},'Agent'),false);
});
