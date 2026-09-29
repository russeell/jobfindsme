import test from 'node:test';
import assert from 'node:assert/strict';
import {jobDescriptionParagraphs} from '../dist-electron/shared/job-description.js';
test('flattened numbered JD separates sections without changing source words',()=>{
 const source='职位描述 本岗位负责研发。 （一）核心服务 1.设计 API；2.优化检索。 任职要求（一）基础要求 1.熟悉 Python。';
 const parts=jobDescriptionParagraphs(source);
 assert.ok(parts.includes('2.优化检索。'));
 assert.ok(parts.includes('任职要求（一）基础要求'));
 assert.equal(parts.join('').replace(/\s/g,''),source.replace(/\s/g,''));
});
test('preserves decimals, versions, unnumbered prose and existing paragraphs',()=>{
 assert.deepEqual(jobDescriptionParagraphs('使用 Python 3.10，要求 1.5 年经验，预算 20.5K。\r\n\r\n按照岗位要求完成研发。'),['使用 Python 3.10，要求 1.5 年经验，预算 20.5K。','按照岗位要求完成研发。']);
 assert.deepEqual(jobDescriptionParagraphs(''),[]);
});
