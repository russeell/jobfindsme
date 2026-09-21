UPDATE desktop_source_capabilities
SET last_verified_at = '2026-09-19T00:00:00+00:00',
    notes = '匿名 HTTP 列表：2026-09-19 生产 .app 快照 92 条，桌面结果 5 页且第二页稳定；官方原页完整 JD 已可视核验。列表 description 仍为摘要，未声明结构化完整 JD；桌面快照页数不代表来源全量分页。'
WHERE source_id = 'liepin'
  AND notes = '匿名 HTTP 列表曾实测 42 条；完整 JD 与分页待验证';
