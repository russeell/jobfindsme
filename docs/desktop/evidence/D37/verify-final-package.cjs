const {_electron}=require('/Users/russeell/Documents/github pr/qwen-code/node_modules/playwright');
const fs=require('fs'),assert=require('assert/strict');
const executablePath=(process.env.JFM_PACKAGE_OUTPUT||'/private/tmp/JobFindsMe-D37-UI20.app')+'/Contents/MacOS/JobFindsMe';
const expectedLabel=process.env.JFM_BUILD_LABEL||'D37-20260920-ui20';
const evidenceDir=process.env.JFM_EVIDENCE_DIR||__dirname;
const profile='/private/tmp/jfm-d37-ui20-'+Date.now();
(async()=>{
 const app=await _electron.launch({executablePath,args:['--user-data-dir='+profile],env:{...process.env,ELECTRON_RUN_AS_NODE:''}});
 try{
  const page=await app.firstWindow();page.setDefaultTimeout(20000);
  await page.waitForFunction(()=>!document.querySelector('nav button')?.disabled);
  assert((await page.locator('.footer').innerText()).includes(expectedLabel));
  assert.equal(await app.evaluate(({app})=>app.getPath('userData')),profile);
  await page.locator('nav').getByRole('button',{name:'岗位来源',exact:true}).click();
  assert.equal(await page.locator('.source-card').count(),4);
  await page.getByRole('button',{name:/公司官网 · 16/}).click();
  assert.equal(await page.locator('.source-card').count(),16);
  for(const name of ['DeepSeek','MiniMax','智谱','月之暗面','阶跃星辰'])assert.equal(await page.locator('.source-card').filter({hasText:name}).count(),1);
  assert.equal(await page.locator('.source-card').filter({hasText:'阿里巴巴'}).getByText('自动检索待验证').count(),1);
  const jdStatus=expectedLabel.startsWith('D38-')?'可检索 · 部分覆盖':'自动检索待验证';
  assert.equal(await page.locator('.source-card').filter({hasText:'京东'}).getByText(jdStatus,{exact:true}).count(),1);
  for(const width of [1240,860]){
   await app.evaluate(({BrowserWindow},value)=>BrowserWindow.getAllWindows()[0].setContentSize(value,820),width);
   await page.screenshot({path:evidenceDir+`/sources-${width}.png`});
  }
  await page.locator('.source-card').filter({hasText:'DeepSeek'}).getByRole('checkbox').check();
  await page.locator('nav').getByRole('button',{name:'发现岗位',exact:true}).click();
  await page.locator('.compact-filters').getByRole('button',{name:'岗位来源',exact:true}).click();
  assert.equal(await page.locator('.source-picker label').filter({hasText:'DeepSeek'}).getByRole('checkbox').isChecked(),true);
  assert.equal(await page.locator('.source-picker input:checked').count(),1);
  await page.screenshot({path:evidenceDir+'/discover-source-filter.png'});
  await page.keyboard.press('Escape');
  console.log(`PASS ${expectedLabel}: build/profile, 20-source catalog, truthful blockers, cross-page selection, 1240/860`);
 }finally{await app.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
