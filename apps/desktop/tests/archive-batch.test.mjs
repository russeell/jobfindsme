import {test} from 'node:test';
import assert from 'node:assert/strict';
import {runArchiveBatch} from '../dist-electron/shared/archive-batch.js';
test('partial failure preserves successful rows and processes each ID once, serially',async()=>{
 let inFlight=0;const visited=[];
 const result=await runArchiveBatch(['a','b','b','c'],async id=>{assert.equal(inFlight++,0);await Promise.resolve();visited.push(id);inFlight--;if(id==='b')throw Error('locked');},()=>true);
 assert.deepEqual(visited,['a','b','c']);assert.deepEqual(result,{succeeded:['a','c'],failed:1});
});
test('workspace switch stops remaining writes',async()=>{
 let current=true;const visited=[];
 const result=await runArchiveBatch(['a','b','c'],async id=>{visited.push(id);current=false;},()=>current);
 assert.deepEqual(visited,['a']);assert.deepEqual(result,{succeeded:['a'],failed:2});
});
