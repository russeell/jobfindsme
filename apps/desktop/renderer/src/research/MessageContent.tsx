import type {ResearchEvidence} from "../../../shared/contracts";
import {parseMessageBlocks,tokenizeMessageInline} from "../../../shared/message-content";

type Props={text:string;sources?:ResearchEvidence[];onCitation?:(number:number)=>void};
export function MessageContent({text,sources,onCitation}:Props){
  const inline=(value:string)=>tokenizeMessageInline(value).map((part,index)=>{
    if(part.kind==="strong")return <strong key={index}>{inline(part.text)}</strong>;
    if(part.kind==="em")return <em key={index}>{inline(part.text)}</em>;
    if(part.kind==="code")return <code key={index}>{part.text}</code>;
    if(part.kind==="link")return <a key={index} href={part.url} target="_blank" rel="noopener noreferrer">{part.text}</a>;
    if(part.kind==="citation"&&part.number&&sources?.[part.number-1]&&onCitation)return <button key={index} type="button" className="citation-button" aria-label={`查看引用 ${part.number}`} onClick={()=>onCitation(part.number!)}>{part.text}</button>;
    return part.text;
  });
  return <div className="message-content">{parseMessageBlocks(text).map((block,index)=>{
    if(block.kind==="heading")return <h3 key={index} className="research-answer-heading">{inline(block.text)}</h3>;
    if(block.kind==="quote")return <blockquote key={index}>{inline(block.text)}</blockquote>;
    if(block.kind==="code")return <pre key={index}><code>{block.text}</code></pre>;
    if(block.kind==="table")return <div key={index} className="message-table-scroll"><table><thead><tr>{block.rows[0].map((cell,j)=><th key={j}>{inline(cell)}</th>)}</tr></thead><tbody>{block.rows.slice(1).map((row,j)=><tr key={j}>{row.map((cell,k)=><td key={k}>{inline(cell)}</td>)}</tr>)}</tbody></table></div>;
    if(block.kind==="list")return block.ordered?<ol key={index}>{block.items.map((item,j)=><li key={j}>{inline(item)}</li>)}</ol>:<ul key={index}>{block.items.map((item,j)=><li key={j}>{inline(item)}</li>)}</ul>;
    return <p key={index}>{inline(block.text)}</p>;
  })}</div>;
}
