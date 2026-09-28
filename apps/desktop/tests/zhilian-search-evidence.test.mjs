import test from 'node:test';
import assert from 'node:assert/strict';
import {ZhilianSearchEvidence} from '../dist-electron/main/sources/zhilian-search-evidence.js';
const endpoint='https://fe-api.zhaopin.com/c/i/search/positions';
const body=(keyword='AI',city='765',page=1)=>JSON.stringify({eventScenario:'pcSearchedSouSearch',S_SOU_FULL_INDEX:keyword,S_SOU_WORK_CITY:city,pageIndex:page});
const job={name:'AI工程师',companyName:'示例',positionUrl:'https://www.zhaopin.com/jobdetail/one.htm'};
const response=(list=[job],count=list.length)=>JSON.stringify({code:200,data:{list,count}});
test('binds card identity to the matching keyword, city, page and search endpoint response',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});
 for(const [keyword,city,page] of [['Java','765',1],['AI','538',1],['AI','765',2]])assert.equal(e.request('bad',endpoint,'POST',body(keyword,city,page)),false);
 assert.equal(e.request('r',endpoint,'POST',body()),true);e.response('r',response());
 assert.equal(e.matches({title:job.name,company:job.companyName,url:job.positionUrl}),true);
 assert.equal(e.matches({title:job.name,company:'其他公司',url:job.positionUrl}),false);
 assert.equal(e.matches({title:job.name,company:job.companyName,url:'https://www.zhaopin.com/jobdetail/recommended.htm'}),false);
});
test('a newer keyword request invalidates old results and late responses',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.request('old',endpoint,'POST',body());
 e.request('new',endpoint,'POST',body('Java'));e.response('old',response());assert.equal(e.ready,false);
});
test('only a matched successful zero-count response confirms no results',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});assert.equal(e.empty,false);
 e.request('r',endpoint,'POST',body());e.response('r',response([],0));assert.equal(e.empty,true);
 e.request('next',endpoint,'POST',body());e.response('next','{"code":200,"data":{"list":[],"count":30}}');assert.equal(e.empty,false);
});

test('verified legacy link normalization preserves identity across layout host changes',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.request('r',endpoint,'POST',body());
 e.response('r',response([{...job,positionUrl:'http://jobs.zhaopin.com/one.htm?track=1'}]));
 assert.equal(e.matches({title:job.name,company:job.companyName,url:job.positionUrl}),true);
});
test('recommendation requests invalidate previously matched search evidence',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.request('r',endpoint,'POST',body());e.response('r',response());
 assert.equal(e.ready,true);e.request('recommend','https://fe-api.zhaopin.com/c/i/job/recommend','POST','{}');assert.equal(e.ready,false);
});

test('server bootstrap independently binds search mode, keyword, city, page and completed list',()=>{
 const state={mode:'search',keyword:'AI',city:'765',page:1,count:1,loading:false,jobs:[job]};
 const url='https://www.zhaopin.com/jobs/?pageMode=search&kw=AI&jl=765&p=1';
 for(const patch of [{mode:'recommend'},{keyword:'Java'},{city:'538'},{page:2},{loading:true},{failed:true}]){
  const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.initial({...state,...patch},url);assert.equal(e.ready,false);
 }
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.initial(state,url);assert.equal(e.ready,true);assert.equal(e.matches({title:job.name,company:job.companyName,url:job.positionUrl}),true);
 e.request('new',endpoint,'POST',body('Java'));e.initial(state,url);assert.equal(e.ready,false,'stale bootstrap cannot override a later search');
});
test('completed scoped server zero result differs from an uninitialized empty list',()=>{
 const e=new ZhilianSearchEvidence({keyword:'none',city:'深圳',page:1});
 const state={mode:'search',keyword:'none',city:'765',page:1,count:0,loading:true,jobs:[]};
 const url='https://www.zhaopin.com/jobs/?pageMode=search&kw=none&jl=765&p=1';
 e.initial(state,url);assert.equal(e.empty,false);e.initial({...state,loading:false},url);assert.equal(e.empty,true);
});

test('malformed structured siblings do not discard valid search records',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.request('r',endpoint,'POST',body());
 e.response('r',response([null,{name:'broken'},job]));assert.equal(e.ready,true);
 assert.equal(e.invalidRecords,2);
 assert.equal(e.matches({title:job.name,company:job.companyName,url:job.positionUrl}),true);
});

test('verified structured jobs survive DOM layout changes and retain only matching card supplements',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.request('r',endpoint,'POST',body());
 e.response('r',response([{...job,workCity:'深圳',cityDistrict:'南山'}]));
 assert.deepEqual(e.records([]),[{title:job.name,company:job.companyName,url:job.positionUrl,location:'深圳 南山',salary:''}]);
 const [value]=e.records([{title:job.name,company:'不同公司',url:job.positionUrl,location:'上海',salary:'50万'}]);
 assert.equal(value.location,'深圳 南山');assert.equal(value.salary,'');
});

test('scoped zero-match response discards its appended suggestions; inconsistent positive totals cannot prove a list',()=>{
 const e=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});e.request('r',endpoint,'POST',body());
 e.response('r',response([job],0));assert.equal(e.empty,true);assert.deepEqual(e.records([]),[]);
 e.request('next',endpoint,'POST',body());e.response('next',response([job,{...job,positionUrl:'https://www.zhaopin.com/jobdetail/two.htm'}],1));assert.equal(e.ready,false);
});

test('blank keyword echo with unsupported expanded jobs is not accepted as a matching search',()=>{
 const e=new ZhilianSearchEvidence({keyword:'NoSuchKeyword',city:'深圳',page:1});e.request('r',endpoint,'POST',body('NoSuchKeyword'));
 e.response('r',JSON.stringify({code:200,data:{kw:'',list:[job],count:200}}));assert.equal(e.ready,false);assert.equal(e.responseStatus,'empty_keyword_expansion');
 const normal=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});normal.request('r',endpoint,'POST',body());normal.response('r',JSON.stringify({code:200,data:{kw:'',list:[job],count:200}}));assert.equal(normal.ready,true);
 const echoed=new ZhilianSearchEvidence({keyword:'AI',city:'深圳',page:1});echoed.request('r',endpoint,'POST',body());echoed.response('r',JSON.stringify({code:200,data:{kw:'Java',list:[job],count:200}}));assert.equal(echoed.ready,false);assert.equal(echoed.responseStatus,'echo_mismatch');
});
