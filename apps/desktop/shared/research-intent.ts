export type ResearchTopic="company"|"job";

export function researchTopicsForQuestion(question:string,hasJobContext:boolean,hasExplicitRole:boolean):ResearchTopic[]{
  const text=question.trim();
  if(!text)return hasJobContext?["company","job"]:["company"];
  const mentionsRole=/(?:岗位|职位|职责|技术栈|任职|招聘|JD|晋升|职业发展)/iu.test(text);
  const mentionsCompany=/(?:公司|企业|经营|业务|上市|福利|口碑|员工|财务)/u.test(text);
  if((hasJobContext||hasExplicitRole)&&(mentionsRole||!mentionsCompany))return ["company","job"];
  return ["company"];
}
