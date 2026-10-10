// Serial writes keep the local database responsive; a failed row stays selected
// for retry, while successful rows must never be submitted again by the UI.
export async function runArchiveBatch(ids:readonly string[],apply:(id:string)=>Promise<void>,canContinue:()=>boolean){
 const unique=[...new Set(ids)],succeeded:string[]=[];let failed=0;
 for(let index=0;index<unique.length;index++){
  if(!canContinue()){failed+=unique.length-index;break;}
  try{await apply(unique[index]);succeeded.push(unique[index]);}catch{failed++;}
 }
 return {succeeded,failed};
}
