/** A topic anchor is not a legal company identity; retain its full label separately. */
export function researchSubject(label:string){
 const clean=label.trim();const topic=/(?:行业|市场|生态|领域|技术趋势|发展趋势)$/.test(clean);
 const anchor=topic?clean.replace(/(?:行业|市场|生态|领域|技术趋势|发展趋势)$/,'').trim():clean;
 return {label:clean,anchor:anchor.length>=2?anchor:clean,kind:topic?'topic' as const:'company' as const};
}
