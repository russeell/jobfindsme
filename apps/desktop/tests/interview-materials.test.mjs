import test from 'node:test';
import assert from 'node:assert/strict';
import {interviewMaterialReader,loadInterviewMaterials} from '../dist-electron/main/research/interview-materials.js';
test('interview reuses successful materials within one task but retries failed reads',async()=>{
 let reads=0;const read=interviewMaterialReader(async()=>{if(++reads===1)throw Error('offline');return {source_version_id:'tailored',text:'虚构项目：Python API',limitations:'脱敏'};});
 await assert.rejects(read());const [a,b]=await Promise.all([read(),read()]);assert.equal(reads,2);assert.equal(a,b);
 const payload=await loadInterviewMaterials(async()=>({job_id:'job-a',description:'职责：开发 API',source:{detail_level:'detail_page'},unneeded:'private'}),read);
 assert.equal(payload.resume.source_version_id,'tailored');assert.equal(payload.job.description,'职责：开发 API');assert.equal(payload.job.unneeded,undefined);assert.equal(reads,2);
});
test('missing JD or resume does not block preparation and oversized materials are bounded',async()=>{
 const absent=await loadInterviewMaterials(async()=>{throw Error('unavailable');},async()=>{throw Error('no confirmed resume');});
 assert.equal(absent.job,null);assert.equal(absent.resume,null);assert.equal(absent.limitations.length,2);
 const long=await loadInterviewMaterials(async()=>({description:'a'.repeat(17000)}),async()=>({source_version_id:'v1',text:'b'.repeat(13000),limitations:''}));
 assert.equal(long.job.description.length,16000);assert.equal(long.resume.text.length,12000);assert.match(long.limitations.join(''),/材料过长/);
});
