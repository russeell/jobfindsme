import test from 'node:test';
import assert from 'node:assert/strict';
import {ResearchRunController} from '../dist-electron/main/research/run-controller.js';

test('run registers synchronously, rejects concurrency and permits immediate retry after cancel',()=>{
 const runs=new ResearchRunController();
 const a=runs.begin({runId:'run-a',sessionId:'session-a',workspaceId:'workspace-a'},90_000);
 assert.throws(()=>runs.begin({runId:'run-b',sessionId:'session-b',workspaceId:'workspace-a'},90_000),/正在生成/);
 assert.equal(runs.cancel('wrong'),false);
 assert.equal(runs.cancel('run-a'),true);assert.equal(a.signal.aborted,true);
 const b=runs.begin({runId:'run-b',sessionId:'session-b',workspaceId:'workspace-a'},90_000);
 runs.finish(a);assert.equal(runs.current?.runId,'run-b');
 runs.finish(b);assert.equal(runs.current,undefined);
 assert.equal(runs.cancel('run-b'),false);
});

test('shutdown cancels the active run and aborts its backend signal',()=>{
 const runs=new ResearchRunController();
 const active=runs.begin({runId:'run-exit',sessionId:'session-a',workspaceId:'workspace-a'},90_000);
 let aborted=false;active.signal.addEventListener('abort',()=>{aborted=true;});
 assert.equal(runs.cancelCurrent(),true);
 assert.equal(aborted,true);
 assert.equal(runs.current,undefined);
 assert.equal(runs.cancelCurrent(),false);
});
