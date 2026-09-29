import test from 'node:test';
import assert from 'node:assert/strict';
import {selectedSourceContinuation} from '../dist-electron/shared/search-scope.js';
const response={source_runs:[{source_id:'boss',can_continue:true,next_cursor:'b2'},{source_id:'zhilian',can_continue:false,next_cursor:null}],planned_queries:[{source_id:'boss'},{source_id:'zhilian'}],executed_queries:[{source_id:'boss'},{source_id:'zhilian'}],blocked_sources:{}};
test('all explicitly selected platforms participate without a two-source cap; unselected never added',()=>{
 assert.deepEqual(selectedSourceContinuation(response,['boss','liepin','zhilian','wuyou'],['boss','zhilian']),{sourceIds:['boss','liepin','wuyou'],cursors:{boss:'b2'},unavailableIds:['zhilian']});
 assert.deepEqual(selectedSourceContinuation(response,['zhilian'],['boss','zhilian']),{sourceIds:[],cursors:{},unavailableIds:['zhilian']});
});
test('budget-unstarted selected source is read once from first batch, deselected source stays excluded',()=>{
 const result={...response,planned_queries:[...response.planned_queries,{source_id:'liepin'}]};
 assert.deepEqual(selectedSourceContinuation(result,['liepin'],['boss','zhilian','liepin']),{sourceIds:['liepin'],cursors:{},unavailableIds:[]});
});
