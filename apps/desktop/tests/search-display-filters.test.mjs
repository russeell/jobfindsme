import test from 'node:test';
import assert from 'node:assert/strict';
import {searchPageForCurrentFilters,remoteSearchScopeChanged} from '../dist-electron/shared/search-scope.js';
test('continued batches are refiltered with the current salary before display, original collection snapshot stays frozen',async()=>{
 const original={cities:['北京'],salary_mode:'overlap',unknown_policy:'include'};
 const current={...original,salary_min_k:20};const before=JSON.stringify(original);
 const batch={run_id:'original',items:[{salary:10},{salary:25},{salary:30}],total:3};let calls=0;
 const display=await searchPageForCurrentFilters(batch,original,current,10,async(id,filters,size)=>{calls++;assert.equal(id,'original');assert.equal(size,10);return {...batch,run_id:'filtered',items:batch.items.filter(job=>job.salary>=filters.salary_min_k)};});
 assert.deepEqual(display.items.map(job=>job.salary),[25,30]);assert.equal(JSON.stringify(original),before);assert.equal(calls,1);
 assert.equal(remoteSearchScopeChanged('Java',current,'Java',original),false);
});
test('unchanged filters do not add refilter requests; keyword or city changes require new search',async()=>{
 const original={cities:['北京']};const page={run_id:'r'};
 assert.equal(await searchPageForCurrentFilters(page,original,original,10,()=>{throw Error('unexpected')}),page);
 assert.equal(remoteSearchScopeChanged('Python',original,'Java',original),true);
 assert.equal(remoteSearchScopeChanged('Java',{cities:['深圳']},'Java',original),true);
});
