# jobfindsme 中文岗位标注指南 v0.2

本指南用于 M14-001（中文标注匹配基准）和 M15-001（个人实地试用）的每日 Top 10 标注。

## 标注流程

每天搜索完成后，打开 `data/eval/field_trial/day_0N.json`，对每个岗位填写以下字段：

只有人工检查完成后，才把该条岗位的 `annotated` 改成 `true`。模板中的
`relevance: 0` 只是占位值；`annotated: false` 的记录不会进入正式指标。

## 字段说明

### relevance（相关性）0-3

| 分数 | 含义 | 示例 |
|------|------|------|
| 0 | 不相关 | 岗位族完全不匹配（如：招前端却推荐后端） |
| 1 | 弱相关 | 岗位族接近但有明显硬伤（如：要求5年经验限3年） |
| 2 | 相关 | 岗位族匹配，地点/年限/薪资可接受 |
| 3 | 完美匹配 | 岗位族、技能栈、行业方向都高度吻合 |

**判定规则**：
- 先看岗位族（title/target_roles）是否匹配
- 再看硬条件是否通过（地点、年限、排除词）
- 最后看技能栈匹配度

### liveness（有效性）

| 值 | 含义 |
|----|------|
| `active` | 岗位仍在招聘，发布日期在 30 天内 |
| `stale` | 岗位超过 30 天未更新，可能已失效 |
| `closed` | 岗位已明确关闭或链接失效 |

### valid_link（链接有效性）

- `true`：apply_url 能打开到真实的岗位详情页（不是首页、404、或已下线）
- `false`：链接打不开、跳转到首页、显示"岗位已下线"

### duplicate_of（重复）

- 如果该岗位与之前某天的某个岗位是**同一公司在同一渠道发布的同一职位**，填写那个 case_id
- 判断标准：同一公司 + 同一岗位名称 + 同一来源 = 重复
- 留空 `null` 表示不重复

### hard_filter_error（硬过滤错误）

- `true`：该岗位本应在硬过滤阶段被排除（如：外包/驻场未被过滤、地点不符、年限超限），但出现在推荐中
- `false`：过滤正确

### notes（备注）

任何你注意到的异常，如：
- 薪资明显不合理
- JD 描述与实际岗位不符
- 来源数据质量问题

## 每日运行信息

除 Top 10 标签外，每天还要记录：

- `source_attempts`：本次实际请求的来源；
- `source_successes`：成功返回可解析结果的来源；
- `source_failures`：失败来源及简短原因；
- `duplicates_detected`：进入 Top 10 前被系统去掉的重复岗位数；
- `time_to_first_results_seconds`：从发出需求到看到第一批结果的耗时；
- `agent_host`：本次使用的 Agent，例如 `codex` 或 `claude-code`。

`P@10` 和 `NDCG@10` 按天计算后做宏平均，避免只有第一天的数据进入指标。
报告只有同时满足以下条件才标记为可对外引用：

- 至少 3 天、50 条人工标签且没有待标注项；
- `evidence_kind` 为 `field_trial`；
- `collection_method` 为 `live_loop_human_annotation`；
- provenance 保存至少 3 份原始 Live Loop 报告路径及 SHA256；
- 评测时原始报告仍存在且 Hash 一致。

手工构造、脚本生成或从 fixture 复制的岗位只能放在 `data/eval/synthetic/`，
即使数量和指标达标也不能成为 M14 证据。

## 每日标注文件位置

```
data/eval/field_trial/day_01.json  # 第 1 天
data/eval/field_trial/day_02.json  # 第 2 天
...
data/eval/field_trial/day_07.json  # 第 7 天
```

每天直接运行 Live Loop，同时保存机器报告和待标注 Top 10：

```bash
python -m jobfindsme.evaluation.live_loop \
  --agent-host codex \
  --allow-browser-sources \
  --day 1 \
  --output reports/field-trials/loops/day_01.json \
  --annotation-output data/eval/field_trial/day_01.json
```

人工逐条打开投递链接后填写标签。不要修改 Loop 原始报告；它的 Hash 会进入最终
dataset provenance。若报告被改动，`ready_for_claim` 自动变为 `false`。

## 至少 5 个有效采集日、累计 50 条人工标签后

M14 的原则门槛是“至少 3 天且至少 50 条”，但每日模板最多包含 Top 10，
因此当前实现下实际至少需要 5 个有 10 条结果的采集日；若某天不足 10 条，
还需要继续采集。

先把每日标签和对应的原始 Live Loop 报告组装成可验真的数据集。`--days` 与
`--loop-reports` 必须按日期一一对应：

```bash
python -m jobfindsme.evaluation.assemble \
  --version v1.0.0 \
  --labeler russeell \
  --days data/eval/field_trial/day_*.json \
  --loop-reports reports/field-trials/loops/day_*.json \
  --output data/eval/field_trial/chinese_real_v1.0.json
```

组装器会拒绝待标注项、不同 Search Plan、不同简历画像，以及与原始报告不一致的
岗位 ID；同时自动记录报告路径和 SHA256。

然后运行正式评测门禁：

```bash
python -m jobfindsme.evaluation.run \
  --type chinese \
  --dataset data/eval/field_trial/chinese_real_v1.0.json \
  --require-claim-ready \
  --report reports/evaluation/chinese_real_v1.0.json
```
