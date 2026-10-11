import test from 'node:test';
import assert from 'node:assert/strict';
import {SharedFlight} from '../dist-electron/main/shared-flight.js';
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
test('same read shares work; cancellation does not cancel another subscriber',async()=>{
 const flights=new SharedFlight(), gate=defer();let calls=0,upstream;
 const work=signal=>{calls++;upstream=signal;return gate.promise;};
 const a=new AbortController(),b=new AbortController();
 const first=flights.run('same',work,a.signal,1000),second=flights.run('same',work,b.signal,2000);
 await Promise.resolve();a.abort();await assert.rejects(first,/cancelled/);assert.equal(upstream.aborted,false);
 gate.resolve({ok:true});assert.deepEqual(await second,{ok:true});assert.equal(calls,1);
});
test('own timeout detaches, final cancellation aborts work and allows immediate retry',async()=>{
 const flights=new SharedFlight(),gate=defer();let signal;
 const short=flights.run('same',s=>{signal=s;return gate.promise;},undefined,5);
 const control=new AbortController(),long=flights.run('same',()=>gate.promise,control.signal,1000);
 await assert.rejects(short,/source_timeout/);assert.equal(signal.aborted,false);
 control.abort();await assert.rejects(long,/cancelled/);assert.equal(signal.aborted,true);
 assert.equal(await flights.run('same',async()=>2),2);gate.resolve(1);
});
test('failures can retry, workspaces stay separate and teardown cancels waiters',async()=>{
 const flights=new SharedFlight();await assert.rejects(flights.run('w1',async()=>{throw Error('failure');}),/failure/);
 let calls=0;const work=async()=>++calls;await Promise.all([flights.run('w1',work),flights.run('w2',work)]);assert.equal(calls,2);
 const pending=flights.run('w1',()=>new Promise(()=>{}));flights.cancelAll();await assert.rejects(pending,/cancelled/);
});
