# jobfindsme Real-World Source Report

- Generated at: `2026-08-09T03:12:44+00:00`
- Database: `~/.jobfindsme/data/jobfindsme.db`
- Query: roles=['AI应用工程师'], locations=['上海', '深圳'], salary_min_k=20
- End-to-end elapsed: `7.007s`
- Remote discovered: `84`
- Unique imported: `79`
- Top results: `20`

## Sources

| Source | Status | Time | Found | Unique | Top | Cache | Error |
|---|---:|---:|---:|---:|---:|---:|---|
| 猎聘·深圳 | SUCCESS | 1.401s | 42 | 39 | 10 | no |  |
| 智联招聘·深圳 | DEGRADED | 4.486s | 0 | 0 | 0 | yes | 智联接口返回空结果（可能被风控拦截，请稍后重试或用浏览器查看） |
| 猎聘·上海 | SUCCESS | 1.444s | 42 | 40 | 10 | no |  |
| 前程无忧·上海 | DEGRADED | 3.431s | 0 | 0 | 0 | yes | 前程无忧页面内请求失败：waf_blocked |
| BOSS直聘·上海 | DEGRADED | 0.534s | 0 | 0 | 10 | yes | browser refresh returned no jobs; using cached records |
| 智联招聘·上海 | DEGRADED | 4.326s | 0 | 0 | 0 | yes | 智联接口返回空结果（可能被风控拦截，请稍后重试或用浏览器查看） |
| 前程无忧·深圳 | DEGRADED | 3.129s | 0 | 0 | 0 | yes | 前程无忧页面内请求失败：waf_blocked |
| BOSS直聘·深圳 | DEGRADED | 0.271s | 0 | 0 | 10 | yes | browser refresh returned no jobs; using cached records |

## MCP Smoke

- Doctor OK: `True`
- Configure OK: `True`
- Search OK: `True`
- Sections present: `True`
- Link present: `True`
