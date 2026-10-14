import test from 'node:test';
import assert from 'node:assert/strict';
import {resumeSelectionQuality as quality} from '../dist-electron/shared/resume-selection-quality.js';

test('no-op edits are distinct from actual proofreading corrections',()=>{
 assert.equal(quality('负责 API 开发。','负责API开发！','resume_rewrite'),'unchanged');
 assert.equal(quality('负责接口，开发。','负责接口开发。','resume_proofread'),'ok');
 assert.equal(quality('负责接口开发。',' 负责接口开发。 ','resume_proofread'),'unchanged');
 assert.equal(quality('使用 Ｐｙｔｈｏｎ 完成项目。','使用Python完成项目。','resume_proofread'),'unchanged');
});
test('explicit metrics, dates and durations cannot silently change or disappear',()=>{
 for(const after of ['使用 Python 完成 300 条评测，准确率 91%。','使用 Python 完成 200 条评测，准确率 97%。','使用 Python 完成评测，准确率 91%。','使用 Python 完成 200 条评测，准确率 91。']){
  assert.equal(quality('使用 Python 完成 200 条评测，准确率 91%。',after,'resume_shorten'),'facts_changed');
 }
 assert.equal(quality('负责项目，2024.03–2025.08。','2024年3月–2025年8月期间，承担项目开发。','resume_rewrite'),'ok');
 assert.equal(quality('负责项目，2024.03–2025.08。','负责项目，2024.03–2026.08。','resume_rewrite'),'facts_changed');
 assert.equal(quality('项目开发，1年。','承担项目开发，12个月。','resume_rewrite'),'ok');
 assert.equal(quality('项目开发，3年。','项目开发，3个月。','resume_rewrite'),'facts_changed');
 assert.equal(quality('完成 1,000 条评测。','评测样本共1000条。','resume_rewrite'),'ok');
});
test('clear additional skills, degrees and stronger responsibility claims are rejected',()=>{
 for(const after of ['独立完成 Python 接口开发。','主导 Python 接口开发。','精通 Python 接口开发。','负责 Python 和 Kubernetes 接口开发。','博士，负责 Python 接口开发。','负责{公司}的 Python 接口开发。']){
  assert.equal(quality('本科，参与 Python 接口开发。',after,'resume_rewrite'),'facts_changed');
 }
 assert.equal(quality('主导 Python 项目。','精通 Python，主导项目。','resume_rewrite'),'facts_changed');
 assert.equal(quality('负责 Kubernetes 服务。','承担 K8s 服务开发。','resume_rewrite'),'ok');
 assert.equal(quality('使用 PostgreSQL 完成项目。','项目数据库使用 postgres。','resume_rewrite'),'ok');
});
