export function formatSalary(job:{salary_min_k:number|null;salary_max_k:number|null}):string{
  const {salary_min_k:min,salary_max_k:max}=job;
  if(min==null&&max==null)return "薪资未注明";
  if(min==null)return `${max}K 以下`;
  if(max==null)return `${min}K 起`;
  return `${min}-${max}K`;
}
