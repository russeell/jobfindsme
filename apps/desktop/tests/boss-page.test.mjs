import assert from 'node:assert/strict';
import test from 'node:test';
import {runInNewContext} from 'node:vm';
import {bossPageScript} from '../dist-electron/main/sources/boss-page.js';

// Fictional DOM for the observed headhunter detail page. No account, cookies,
// requests or private recruiter information are included.
function readDetail(header, agency='示例招聘服务公司', clientElement) {
 const node=text=>({innerText:text,textContent:text,getBoundingClientRect:()=>({width:100,height:20}),querySelectorAll:()=>[]});
 const description=node('任职要求\n熟悉 Python、FastAPI、Linux 和 SQL。\n'+ '具备工程实践和沟通协作能力。'.repeat(10)+'\n客户公司：正文提到的其他公司');
 const banner=node(header);
 if(clientElement)banner.querySelectorAll=selector=>selector==='*'?[node(clientElement),node('杭州 在校/应届 本科')]:[];
 const document={
  body:node(header+'\n'+description.innerText),
  querySelector:selector=>selector==='.job-banner'?banner:null,
  querySelectorAll(selector){
   if(selector==='.job-sec-text,.job-detail .text,.job-description')return [description];
   if(selector.includes('.job-name h1'))return [node('Python开发工程师')];
   if(selector.includes('.sider-company'))return agency?[node(agency)]:[];
   return [];
  },
 };
 document.body.querySelectorAll=document.querySelectorAll;
 return runInNewContext(bossPageScript(),{
  document,location:new URL('https://www.zhipin.com/job_detail/fictional-client.html'),
  URL,getComputedStyle:()=>({display:'block',visibility:'visible'}),
 }).detail;
}

test('headhunter JD uses the explicitly labelled client, preserving anonymous client names',()=>{
 const detail=readDetail('招聘中\nPython开发工程师\n20-40K·14薪\n客户公司：某大型计算机软件公司\n深圳');
 assert.equal(detail.company,'某大型计算机软件公司');
 assert.equal(detail.title,'Python开发工程师');
 assert.match(detail.description,/任职要求/);
 assert.equal(readDetail('客户公司: 示例研发公司\n深圳').company,'示例研发公司');
});

test('company text outside the labelled header cannot replace the employer',()=>{
 assert.equal(readDetail('招聘中\nPython开发工程师').company,'示例招聘服务公司');
 assert.equal(readDetail('招聘中\n客户公司：\n深圳','').company,'');
});
test('inline client label excludes adjacent city, experience and education',()=>{
 const detail=readDetail('招聘中\n客户公司：某大型计算机软件公司杭州 在校/应届 本科','示例招聘服务公司','客户公司：某大型计算机软件公司');
 assert.equal(detail.company,'某大型计算机软件公司');
});
