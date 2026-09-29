import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {researchExtractionScript} from '../dist-electron/main/sources/research-extraction.js';
function page(host='www.zhaopin.com',path='/jobdetail/CC123J456.htm'){
 const company={textContent:'示例科技'};
 const description={textContent:'任职要求：掌握 Java 和 Spring，参与业务系统开发。'.repeat(6)};
 // Observed live page: h2 > title-wrap > header > seo-card > content.
 // Heading siblings are absent; each section has its own content wrapper.
 const section=content=>({querySelector:s=>s===':scope > .seo-card__content'?content:null});
 const heading={textContent:'职位描述',nextElementSibling:null,closest:s=>s==='.seo-card'?section(description):null};
 const companyHeading={textContent:'公司信息',closest:s=>s==='.seo-card'?section({querySelector:()=>company}):null};
 const document={querySelectorAll:s=>s==='h2,h3'?[heading,companyHeading]:[],querySelector:s=>s==='h1'?{textContent:'Java 工程师'}:null};
 return {document,location:{hostname:host,pathname:path}};
}
test('Zhilian detail uses observed semantic headings and excludes location, company introduction and recommendations',()=>{
 const result=vm.runInNewContext(researchExtractionScript(),page());
 assert.equal(result.title,'Java 工程师');assert.equal(result.company,'示例科技');assert.match(result.description,/任职要求/);assert.doesNotMatch(result.description,/工作地点|公司介绍|相似职位/);
});
test('semantic Zhilian detail fallback is limited to its official detail path',()=>{
 assert.equal(vm.runInNewContext(researchExtractionScript(),page('evil.test')),null);
 assert.equal(vm.runInNewContext(researchExtractionScript(),page('www.zhaopin.com','/jobs/')),null);
});
