// Runs inside an isolated, allowlisted source page. Page text is data, never code.
export function researchExtractionScript(companyHint = ""): string {
  return `(${extractResearchJob.toString()})(${JSON.stringify(companyHint)})`;
}
function extractResearchJob(companyHint: string) {
  const clean = (value: unknown) => typeof value === "string" ? value.replace(/\s+/g," ").trim() : "";
  const plain = (value: unknown) => typeof value === "string" ? clean(new DOMParser().parseFromString(value, "text/html").body.textContent) : "";
  const text = (selectors:string[]) => {
    for (const selector of selectors) {const result=clean(document.querySelector(selector)?.textContent);if(result) return result;}
    return "";
  };
  let structured: {title:string;company:string;description:string} | undefined;
  const visit = (value:any, depth=0) => {
    if (!value || typeof value !== "object" || depth > 5 || structured) return;
    if (Array.isArray(value)) {value.slice(0,100).forEach(v=>visit(v,depth+1));return;}
    if ([value['@type']].flat().includes('JobPosting')) {
      const title=plain(value.title);const company=plain(value.hiringOrganization?.name) || companyHint;
      const description=plain(value.description);
      if (title && company && description.length >= 80) structured={title,company,description};
    }
    if (value['@graph']) visit(value['@graph'],depth+1);
  };
  for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {visit(JSON.parse(node.textContent?.slice(0,200000) || '{}'));}catch{}
  }
  if (structured) return structured;
  if (location.hostname === 'zhaopin.jd.com' && location.pathname === '/web/job-info-detail') {
    const title = text(['.post-top .post-name']);
    const description = clean([...document.querySelectorAll('.main-content .part')].map(n=>n.textContent).join('\n'));
    if (title && description.length >= 80) return {title:title.slice(0,300),company:companyHint || '京东',description:description.slice(0,30000)};
  }
  const title=text(['[data-automation-id="jobPostingHeader"]','.job-recruit-title','.job-name h1','.job-title h1','.job-title','.name h1','.job-header h1','[class*="title-ROUQ"][title]','.position_detail_sticky .postion_name .title','[class*="detail-title__"]','.posi-name','.job-info-container .base-info .title','.detail-header-title','h1']);
  const company=companyHint || text(['.company-name','.company-info a[title]','.company-info .name','.job-company-name','.company a']);
  const didiDescription=location.hostname==='talent.didiglobal.com'?clean(Array.from(document.querySelectorAll('.whitespace-break-spaces')).map(n=>n.textContent).join(' ')):'';
  const description=didiDescription || clean([...document.querySelectorAll('.jobDetail .block-content,.positin_detail_info_item,[class*="post-content-desc__"],.recruit-content > .work-module,.job-de-de-left .content,.job-info-container .description .value,.detail-content-desc')].map(n=>n.textContent).join(' ')) || text(['[data-automation-id="jobPostingDescription"]','.job-sec-text','.job-description','[class^="job-description-"]','.job-detail .detail-content','.job-intro-content','.describtion__detail-content','.job-describe','[data-testid="job-description"]']);
  if (!title || !company || description.length < 80 || /^(登录|注册|招聘首页|腾讯招聘)$/.test(title)) return null;
  return {title:title.slice(0,300),company:company.slice(0,300),description:description.slice(0,30000)};
}
