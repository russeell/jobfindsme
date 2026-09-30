import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {SecureSecretStore} from '../dist-electron/main/security/secure-secret-store.js';

test('successful key access is cached only in memory and invalidated by ciphertext changes and deletion',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 let decryptions=0;
 const encryption={isEncryptionAvailable:()=>true,encryptString:value=>Buffer.from(`encrypted:${value}`),decryptString:value=>{decryptions++;return value.toString().replace('encrypted:','');}};
 try{
  const store=new SecureSecretStore(directory,encryption);store.set('fixture','first');
  const reopened=new SecureSecretStore(directory,encryption);
  assert.equal(reopened.get('fixture'),'first');assert.equal(reopened.get('fixture'),'first');assert.equal(decryptions,1);
  store.set('fixture','second');assert.equal(reopened.get('fixture'),'second');assert.equal(decryptions,2);
  store.delete('fixture');assert.equal(reopened.get('fixture'),undefined);
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});
test('keychain denial remains a key-access error and never caches an unsuccessful read',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 let calls=0;
 const encryption={isEncryptionAvailable:()=>true,encryptString:()=>Buffer.from('cipher'),decryptString:()=>{calls++;throw Error('private details');}};
 try{
  new SecureSecretStore(directory,encryption).set('fixture','fixture');
  const reopened=new SecureSecretStore(directory,encryption);
  for(let i=0;i<2;i++)assert.throws(()=>reopened.get('fixture'),/^Error: assistant_failure:model_key$/);
  assert.equal(calls,2);
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});
