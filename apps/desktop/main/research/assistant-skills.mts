import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {isBundledSkillId,type BundledSkillId} from "../../shared/assistant-skills.js";
export function loadAssistantSkill(id:BundledSkillId):string{
  if(!isBundledSkillId(id))throw Error("unknown assistant skill");
  const file=new URL(`../../../skills/${id}/SKILL.md`,import.meta.url);
  const text=readFileSync(fileURLToPath(file),"utf8");
  if(!text.trim()||text.length>16000)throw Error("invalid bundled assistant skill");
  return text;
}
