import test from 'node:test';
import assert from 'node:assert/strict';
import {selectMaterialText} from '../dist-electron/main/research/preparation-materials.js';
import {loadInterviewMaterials} from '../dist-electron/main/research/interview-materials.js';

test('interview and greeting budgets retain a relevant final grouped entry without altering facts',async()=>{
 const project='示例平台 2025.04–2026.03\nKubernetes 自动部署，200 个服务，耗时下降 30%。';
 const text=JSON.stringify({experience:Array.from({length:60},(_,i)=>`其他示例公司 ${i}\n处理无关材料。`.repeat(20)),projects:[project],basic_information:['不可发送的个人信息']});
 const payload=await loadInterviewMaterials(async()=>({title:'Kubernetes 平台工程师',description:'运行 Kubernetes 服务。'}),async()=>({source_version_id:'saved-old',text,limitations:'脱敏'}));
 assert.equal(payload.resume.source_version_id,'saved-old');assert.ok(payload.resume.text.includes(project));assert.ok(payload.resume.text.length<=12000);assert.ok(!payload.resume.text.includes('不可发送的个人信息'));
 assert.match(payload.limitations.join(''),/未包含全部/);
});
test('a relevant tail inside a single overlong experience retains its company and dates',()=>{
 const text=JSON.stringify({experience:['示例公司 2025.04–2026.03\n'+Array.from({length:50},()=> '处理早期事务。'.repeat(8)).join('\n')+'\nKubernetes 部署 200 个服务。']});
 const selected=selectMaterialText(text,'Kubernetes',800);
 assert.ok(selected.text.includes('示例公司 2025.04–2026.03'));assert.ok(selected.text.includes('Kubernetes 部署 200 个服务。'));assert.ok(selected.text.length<=800);
});
test('selection uses whole technical terms and preserves source order for selected paragraphs',()=>{
 const java='示例 Java 服务，处理 200 个请求。';
 const text='JavaScript 网站。'.repeat(30)+'\n\n'+java+'\n\n'+'Java 数据验证，91% 准确率。';
 const result=selectMaterialText(text,'Java',100);
 assert.ok(result.text.startsWith(java));assert.ok(!result.text.includes('JavaScript'));assert.ok(result.text.endsWith('Java 数据验证，91% 准确率。'));
 const unicode=selectMaterialText('😀'.repeat(20),'',5);assert.equal(unicode.text,'😀😀');
 assert.equal(selectMaterialText(text,'Java.',100).text,result.text,'Sentence punctuation cannot hide a related tail');
 const emoji=selectMaterialText('😀'.repeat(200)+'Java services.','Java.',101);
 assert.ok(emoji.text.includes('Java'));assert.ok(!/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(emoji.text));
});
