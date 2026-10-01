/** Small explicit alternatives; never expand an initial search or use resume text. */
export function alternativeSearchKeywords(query:string):string[]{
  const variants:Record<string,string[]>={
    'python工程师':['Python开发工程师','Python后端开发'],
    'python开发工程师':['Python工程师','Python后端开发'],
    'java工程师':['Java开发工程师','Java后端开发'],
    'java开发工程师':['Java工程师','Java后端开发'],
    '前端工程师':['前端开发工程师','Web前端开发'],
    '数据工程师':['数据开发工程师','大数据开发工程师'],
    'ai工程师':['AI开发工程师','人工智能工程师'],
  };
  return variants[query.replace(/\s+/g,'').toLowerCase()]||[];
}
