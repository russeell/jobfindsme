# JobFindsMe 中文岗位标注指南 v0.2

本指南用于 M14-001（中文标注匹配基准）和 M15-001（个人实地试用）的每日 Top 10 标注。

## 标注流程

每天搜索完成后，打开 `data/eval/field_trial/day_0N.json`，对每个岗位填写以下字段：

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

## 每日标注文件位置

```
data/eval/field_trial/day_01.json  # 第 1 天
data/eval/field_trial/day_02.json  # 第 2 天
...
data/eval/field_trial/day_07.json  # 第 7 天
```

## 7 天完成后

运行以下命令汇总所有标注：

```bash
python -m jobfindsme.evaluation.run \
  --type chinese \
  --dataset data/eval/v0.2_labeled.json \
  --report reports/evaluation/v0.2_labeled.json
```
