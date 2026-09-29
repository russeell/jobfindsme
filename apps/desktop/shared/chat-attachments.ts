export type ChatAttachment={id:string;name:string;text:string;truncated:boolean;image?:{mimeType:"image/jpeg";data:string}};
export type ChatAttachmentSelection={attachments:ChatAttachment[];warnings:string[]};
export const attachmentLimits={files:10,bytes:5*1024*1024,chars:8000,totalChars:24000};
export function validChatAttachments(value:unknown):value is ChatAttachment[]{
 if(!Array.isArray(value)||value.length>attachmentLimits.files)return false;
 let total=0,imageBytes=0;return value.every(item=>{if(!item||typeof item.id!=="string"||item.id.length>80||typeof item.name!=="string"||!item.name||item.name.length>300||typeof item.text!=="string"||!item.text.trim()||item.text.length>attachmentLimits.chars||typeof item.truncated!=="boolean")return false;if(item.image!==undefined){if(item.image?.mimeType!=="image/jpeg"||typeof item.image.data!=="string"||item.image.data.length>2_000_000||!/^\/9j\/[A-Za-z0-9+/=]+$/.test(item.image.data))return false;imageBytes+=item.image.data.length;if(imageBytes>8_000_000)return false;}total+=item.text.length;return total<=attachmentLimits.totalChars;});
}
export function attachmentContext(items:ChatAttachment[]=[]):string{return items.map(item=>`文件材料：${item.name}${item.truncated?"（仅包含部分文本）":""}\n${item.text}`).join("\n\n");}
