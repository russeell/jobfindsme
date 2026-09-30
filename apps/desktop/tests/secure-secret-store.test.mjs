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
test('keychain denial suppresses repeated prompts until an explicit retry',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 let calls=0;
 const encryption={isEncryptionAvailable:()=>true,encryptString:()=>Buffer.from('cipher'),decryptString:()=>{calls++;throw Error('private details');}};
 try{
  new SecureSecretStore(directory,encryption).set('fixture','fixture');
  const reopened=new SecureSecretStore(directory,encryption);
  for(let i=0;i<2;i++)assert.throws(()=>reopened.get('fixture'),/^Error: assistant_failure:model_key$/);
  assert.equal(calls,1);
  assert.equal(reopened.isAvailable(true),true);
  assert.throws(()=>reopened.get('fixture'),/^Error: assistant_failure:model_key$/);
  assert.equal(calls,2);
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});

test('unavailable keychain is probed once and missing-key metadata never requests access',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 let probes=0;let available=false;
 const encryption={isEncryptionAvailable:()=>{probes++;return available;},encryptString:value=>Buffer.from(value),decryptString:value=>value.toString()};
 try{
  const store=new SecureSecretStore(directory,encryption);
  assert.equal(store.has('missing'),false);assert.equal(store.get('missing'),undefined);assert.equal(probes,0);
  assert.equal(store.isAvailable(),false);assert.equal(store.isAvailable(),false);
  assert.throws(()=>store.set('fixture','fixture'));assert.equal(probes,1);
  available=true;assert.equal(store.isAvailable(),false);
  assert.equal(store.isAvailable(true),true);store.set('fixture','fixture');assert.equal(probes,2);
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});

test('failed encryption pauses further attempts and preserves previously saved ciphertext',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 let denied=false;let encryptions=0;
 const encryption={isEncryptionAvailable:()=>true,encryptString:value=>{encryptions++;if(denied)throw Error('OS denial');return Buffer.from(`cipher:${value}`);},decryptString:value=>value.toString().slice(7)};
 try{
  const store=new SecureSecretStore(directory,encryption);store.set('fixture','first');denied=true;
  assert.throws(()=>store.set('fixture','second'),/^Error: assistant_failure:model_key$/);
  assert.throws(()=>store.set('fixture','third'));assert.equal(encryptions,2);
  assert.equal(store.get('fixture'),'first');
  assert.equal(new SecureSecretStore(directory,encryption).get('fixture'),'first');
  store.isAvailable(true);denied=false;store.set('fixture','fourth');assert.equal(store.get('fixture'),'fourth');
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});

test('credential removal and database rollback require no keychain access',async()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 const file=path.join(directory,'secrets','model-keys.json');
 const provider={isEncryptionAvailable:()=>true,encryptString:()=>Buffer.from('fixture-cipher'),decryptString:()=>{throw Error('must not decrypt');}};
 try{
  new SecureSecretStore(directory,provider).set('fixture','fixture');
  const before=fs.readFileSync(file,'utf8');
  const denied={isEncryptionAvailable:()=>{throw Error('must not probe');},encryptString:()=>{throw Error('must not encrypt');},decryptString:()=>{throw Error('must not decrypt');}};
  const store=new SecureSecretStore(directory,denied);
  await assert.rejects(store.withoutSecret('fixture',async()=>{assert.equal(store.has('fixture'),false);throw Error('database rejected deletion');}),/database rejected/);
  assert.equal(fs.readFileSync(file,'utf8'),before);
  await store.withoutSecret('fixture',async()=>{assert.equal(store.has('fixture'),false);});
  assert.equal(store.has('fixture'),false);assert.equal(store.get('fixture'),undefined);
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});

test('failed ciphertext deletion preserves the memory cache and never commits database changes',async()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'jfm-secrets-'));
 const rename=fs.renameSync;let committed=false;
 const provider={isEncryptionAvailable:()=>true,encryptString:value=>Buffer.from('fixture-cipher'),decryptString:()=>{throw Error('must keep cache');}};
 try{
  const store=new SecureSecretStore(directory,provider);store.set('fixture','fixture');
  fs.renameSync=()=>{throw Error('disk unavailable');};
  await assert.rejects(store.withoutSecret('fixture',async()=>{committed=true;}),/disk unavailable/);
  assert.equal(committed,false);assert.equal(store.get('fixture'),'fixture');
 }finally{fs.renameSync=rename;fs.rmSync(directory,{recursive:true,force:true});}
});
