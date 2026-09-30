// Zhilian-only DOM and server-bootstrap adapter. Other platforms do not use it.
const zhilianSpec = {
    cards: [".job-list-panel .job-card", ".joblist-box__item", ".positionlist__item", "[class*='joblist'] article", "[class*='job-list'] [class*='item']", "[class*='position-list'] [class*='item']"],
    title: [".job-card__title-clamp .vue-clamp__text", ".job-card__name", ".jobinfo__name", "[class*='job-name']", "[class*='position-name']", "h3"],
    company: [".job-card__company-name", ".companyinfo__name", "[class*='company-name']", "[class*='company']"],
    location: [".job-card__location", ".jobinfo__other-info-item", "[class*='location']", "[class*='address']"],
    salary: ["[class*='salary']"],
    link: ["a[href*='/jobdetail/']", "a[href*='jobs.zhaopin.com']"],
    next: ["[class*='pagination'] [class*='next']", "li.next"],
  };

// Observed QuerySug input/button: invoke the website's normal search once.
// Called only on the owned background page after risk and URL checks.
export function zhilianSubmitSearchScript(keyword:string):string {
  return `(() => {
    const input=document.querySelector('input.query-sug__input[placeholder="搜索职位、公司"]');
    const button=input?.closest('.query-sug')?.querySelector('button.query-sug__button');
    if(!input||!button||button.disabled)return false;
    const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;
    if(!set)return false;
    set.call(input,${JSON.stringify(keyword)});
    input.dispatchEvent(new Event('input',{bubbles:true}));
    button.click();return true;
  })()`;
}

export function zhilianListExtractionScript(): string {
  const sourceId="zhilian";const spec = JSON.stringify(zhilianSpec);
  return `(() => {
    const spec = ${spec};
    const text = (document.body?.innerText || "").slice(0, 5000);
    const blocked = ["滑动验证", "安全验证", "访问过于频繁", "captcha", "请完成验证"]
      .find((marker) => text.toLowerCase().includes(marker.toLowerCase()));
    const visible=node=>{const rect=node.getBoundingClientRect?.();const style=getComputedStyle(node);return !!rect&&rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity)!==0;};
    const loginHost=/passport\\.zhaopin\\.com/.test(location.hostname);
    const loginForm=Array.from(document.querySelectorAll('input[type="password"],input[autocomplete="current-password"]')).some(visible);
    const pick = (root, selectors) => {
      for (const selector of selectors) {
        const node = root.querySelector(selector);
        // VueClamp displays ellipsized text; its aria-label retains the full title.
        const fullTitle=${JSON.stringify(sourceId)}==='zhilian' && selector==='.job-card__title-clamp .vue-clamp__text' ? node?.getAttribute?.('aria-label') : undefined;
        const attributeTitle=node?.getAttribute?.('title');
        const displayed=(node?.textContent||'').trim();let compatibleTitle;
        if(selector==='.job-card__title-clamp .vue-clamp__text'&&!fullTitle&&!attributeTitle&&(!displayed||/…|\\.\\.\\./.test(displayed))){
          try{const clamp=root.querySelector('.job-card__title-clamp')?.__vue__;if(clamp?.$options?.name==='VueClamp')compatibleTitle=clamp.$props?.content;}catch{/* DOM remains available when the compatibility component is inaccessible. */}
        }
        const value = (fullTitle || attributeTitle || compatibleTitle || displayed || "").replace(/\\s+/g, " ").trim();
        if (value) return value;
      }
      return "";
    };
    const href = (root) => {
      if (root.matches?.('a[href]')) return root.href;
      for (const selector of spec.link) {
        const node = root.querySelector(selector);
        if (node?.href) return node.href;
      }
      if (${JSON.stringify(sourceId)} === 'zhilian' && root.matches?.('.job-card')) {
        // Verified compatibility with the observed JobCard/VueClamp components;
        // not a stable API. Only this card's props, never Vue account/store state.
        const component=root.__vue__,job=component?.$props?.job;
        if(component?.$options?.name==='JobCard' && job && typeof job.name==='string' && typeof job.companyName==='string' &&
          job.name.trim()===pick(root,spec.title) && job.companyName.trim()===pick(root,spec.company) &&
          typeof job.positionUrl==='string') return job.positionUrl;
      }
      return "";
    };
    let cards = [];
    for (const selector of spec.cards) {
      cards = Array.from(document.querySelectorAll(selector));
      if (cards.length) break;
    }
    if (${JSON.stringify(sourceId)} === 'zhilian' && !cards.length) {
      // New layouts retain canonical job links even when card class names change.
      cards = Array.from(document.querySelectorAll('a[href*="/jobdetail/"],a[href*="jobs.zhaopin.com/"]'))
        .filter(visible).map(link=>link.closest('article,li,[class*="job-card"],[class*="job-item"],[class*="position-item"]') || link);
      cards = [...new Set(cards)];
    }
    let skippedCards=0;const jobs=[];
    for(const card of cards.filter(visible).slice(0,60)){
      try{
        const item={title:pick(card,spec.title)||(card.matches?.('a[href]')?(card.getAttribute?.('title')||card.textContent||'').trim():''),company:pick(card,spec.company),location:pick(card,spec.location),salary:pick(card,spec.salary),url:href(card)};
        if(!item.title||!item.url||(${JSON.stringify(sourceId)}==='zhilian'&&!item.company)){skippedCards++;continue;}
        jobs.push(item);
      }catch{skippedCards++;}
    }
    let hasNext = false;
    for (const selector of spec.next) {
      const next = document.querySelector(selector);
      if (next && !next.matches("[disabled], .disabled, [aria-disabled='true']")) {
        hasNext = true; break;
      }
    }
    const searchKeyword=${JSON.stringify(sourceId)}==='zhilian' ? document.querySelector('input[placeholder="搜索职位、公司"]')?.value : undefined;
    // Read only search metadata and public list fields from the server bootstrap.
    // Do not enumerate or return user/cookie/resume/store objects.
    const state=typeof window==='undefined'?undefined:window.__INITIAL_STATE__;
    const initialSearch=state&&typeof state==='object'?{
      mode:state.pageMode,keyword:String(state.queryParams?.kw||state.queryParams?.keyWords||'').trim(),city:String(state.queryParams?.re||state.queryParams?.cityAreaCode||state.queryParams?.jl||state.queryParams?.cityCode||'').trim(),
      scopeFields:['kw','keyWords','jl','cityCode','re','cityAreaCode'].filter(k=>state.queryParams?.[k]!==undefined).join(','),
      page:state.pageIndex,count:state.positionCount,loading:state.loadingStatus,failed:state.listLoadError===true,
      jobs:Array.isArray(state.positionList)?state.positionList.slice(0,100).map(j=>({name:j?.name,companyName:j?.companyName,positionUrl:j?.positionUrl||j?.positionURL,workCity:j?.workCity,cityDistrict:j?.cityDistrict,streetName:j?.streetName,salary60:j?.salary60})):undefined,
    }:undefined;
    return { jobs, hasNext, searchKeyword, skippedCards, initialSearch, diagnostics:{readyState:document.readyState,visibility:document.visibilityState,cards:cards.length,visibleCards:cards.filter(visible).length,}, empty:/暂无相关职位|没有找到相关职位|没有符合条件的职位/.test(text), blocked: blocked || null, loginRequired: Boolean(loginHost||loginForm) };
  })()`;
}
