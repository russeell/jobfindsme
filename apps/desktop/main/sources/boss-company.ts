// Read the smallest visible header element carrying the explicit client label.
// Its parent may concatenate city, experience and education on the same line.
// Keep this DOM-only helper serializable for both JD and application readers.
export function bossClientCompanyDom(banner:Element|null):string{
  if(!banner)return '';
  const text=(node:Element)=>((node as HTMLElement).innerText||node.textContent||'').trim();
  const labelled=(node:Element)=>/^客户公司\s*[:：]/.test(text(node));
  const visible=(node:Element)=>{const bounds=node.getBoundingClientRect();return bounds.width>0&&bounds.height>0&&getComputedStyle(node).visibility!=='hidden';};
  const children=Array.from(banner.querySelectorAll('*')).filter(visible);
  const nodes=children.filter(node=>labelled(node)&&!Array.from(node.querySelectorAll('*')).some(child=>visible(child)&&labelled(child)));
  const values=[...new Set(nodes.map(node=>text(node).replace(/^客户公司\s*[:：]\s*/,'').trim()).filter(Boolean))];
  if(values.length===1)return values[0];
  if(nodes.length||children.length)return '';
  // Plain-text header fallback cannot cross a line boundary into other fields.
  return text(banner).split(/\r?\n/).map(line=>line.trim()).find(line=>/^客户公司\s*[:：]\s*\S/.test(line))?.replace(/^客户公司\s*[:：]\s*/,'').trim()||'';
}
