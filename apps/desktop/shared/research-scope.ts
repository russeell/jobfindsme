export type ResearchScope={company?:string;title?:string};
const unknown=new Set(["某公司","这家公司","该公司","公司","某个公司","哪个公司","未知公司"]);

export function researchScopeFromQuestion(question:string):ResearchScope {
  const value=question.trim();
  const labelled=value.match(/(?:公司|企业)\s*[:：]\s*([^，,。；;\n]{2,60})/u);
  const quoted=value.match(/[「“《]([^」”》]{2,60})[」”》]/u);
  const natural=value.match(/(?:研究|了解|看看|查询|调查|分析|关于|请问)\s*([^，,。；;？?\s]{2,40}?)的(?:[^，,。；;？?\n]{0,50})(?:经营|业务|上市|福利|员工|口碑|岗位|职位|工作强度|发展)/u)
    ??value.match(/(?:研究|了解|看看|查询|调查|分析|关于|请问)\s*([^，,。；;？?\s]{2,40}?)(?:经营|业务|上市|福利|员工|口碑|工作强度|发展)/u)
    ??value.match(/^([^，,。；;？?\s]{2,40}?)的(?:经营|业务|上市|福利|员工|口碑|工作强度|发展)/u)
    ??value.match(/^([^，,。；;？?\s]{2,40}?)的(?:研发)?团队(?:怎么样|靠谱吗|如何)[？?]?$/u)
    ??value.match(/^([^，,。；;？?\s]{2,40}?)(?:怎么样|靠谱吗|如何)[？?]?$/u);
  const company=(labelled?.[1]??quoted?.[1]??natural?.[1]??"").trim().replace(/的$/u,"");
  const role=value.match(/(?:岗位|职位)\s*[:：]\s*([^，,。；;\n]{2,80})/u)
    ??value.match(/(?:的|招聘)([^，,。；;？?\n]{2,80}?)(?:岗位|职位)/u);
  const title=role?.[1]?.trim();
  return {company:company&&!unknown.has(company)&&!/^(?:这家|该公司|某公司|公司)/u.test(company)?company:undefined,title:title||undefined};
}
