import {lstat,opendir,readFile} from "node:fs/promises";
import path from "node:path";
import {randomUUID} from "node:crypto";
import {attachmentLimits,type ChatAttachmentSelection} from "../../shared/chat-attachments";
/** Only called with paths returned by the native picker, never renderer paths. */
export async function collectChatAttachments(paths:string[],extract:(name:string,content:string)=>Promise<{text:string;truncated:boolean;image?:{mimeType:"image/jpeg";data:string}}>):Promise<ChatAttachmentSelection>{
 const result:ChatAttachmentSelection={attachments:[],warnings:[]};let scanned=0,total=0,bytes=0,imageChars=0,stopped=false;
 const warn=(name:string,reason:string)=>{if(result.warnings.length<12)result.warnings.push(`${name}：${reason}`);};
 async function visit(file:string,name:string,depth:number):Promise<void>{
  if(stopped)return;
  if(++scanned>1000||result.attachments.length>=attachmentLimits.files){stopped=true;warn("附件","已达到数量限制，其余文件未读取");return;}
  try{
   const stat=await lstat(file);if(stat.isSymbolicLink()){warn(name,"跳过快捷链接");return;}
   if(stat.isDirectory()){
    if(depth>=5){warn(name,"目录层级过深，未读取");return;}
    const dir=await opendir(file);for await(const entry of dir){if(stopped)break;if(entry.name.startsWith('.')||['node_modules','__pycache__','venv'].includes(entry.name))continue;await visit(path.join(file,entry.name),`${name}/${entry.name}`,depth+1);}return;
   }
   if(!stat.isFile())return;
   if(!['.pdf','.docx','.txt','.md','.png','.jpg','.jpeg','.webp'].includes(path.extname(file).toLowerCase())){warn(name,"不支持此格式");return;}
   if(stat.size>attachmentLimits.bytes||bytes+stat.size>20*1024*1024){warn(name,"文件过大，未读取");return;}
   if(total>=attachmentLimits.totalChars){stopped=true;warn("附件","文本已达到限制，其余文件未读取");return;}
   const content=await readFile(file);if(content.length>attachmentLimits.bytes){warn(name,"文件过大，未读取");return;}bytes+=content.length;
   const extracted=await extract(path.basename(file),content.toString('base64'));
   if(extracted.image){imageChars+=extracted.image.data.length;if(imageChars>8_000_000){warn(name,"图片总量超限，未添加");return;}}
   const text=extracted.text.slice(0,Math.min(attachmentLimits.chars,attachmentLimits.totalChars-total));
   if(!text.trim()){warn(name,"未读到文本");return;}
   const truncated=extracted.truncated||text.length<extracted.text.length;
   result.attachments.push({id:randomUUID(),name:name.slice(0,300),text,truncated,...(extracted.image?{image:extracted.image}:{})});total+=text.length;
  }catch{warn(name,"读取失败，请检查文件是否损坏或被占用");}
 }
 for(const file of paths)await visit(file,path.basename(file),0);
 return result;
}
