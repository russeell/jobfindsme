import test from 'node:test';
import assert from 'node:assert/strict';
import {publicAtsDetailEndpoint,parsePublicAtsDetail} from '../dist-electron/main/sources/public-detail.js';
test('public ATS detail parsing binds the response to the requested tenant and job ID',()=>{
 const url='https://xiaomi.jobs.f.mioffice.cn/index/position/123/detail';
 assert.equal(publicAtsDetailEndpoint(url),'https://xiaomi.jobs.f.mioffice.cn/api/v1/job/posts/123');
 assert.equal(publicAtsDetailEndpoint(url.replace('xiaomi','other')),null);
 assert.equal(publicAtsDetailEndpoint(url.replace('https:','http:')),null);
 const data={code:0,data:{job_post_detail:{id:'123',title:'Engineer',description:'Observed responsibilities '.repeat(4),requirement:'Observed requirements '.repeat(4)}}};
 assert.equal(parsePublicAtsDetail(data,url).company,'小米');
 assert.match(parsePublicAtsDetail(data,url).description,/职位要求/);
 assert.throws(()=>parsePublicAtsDetail(data,url.replace('123','124')),/不完整/);
 data.data.job_post_detail.requirement='';assert.throws(()=>parsePublicAtsDetail(data,url),/不完整/);
});
