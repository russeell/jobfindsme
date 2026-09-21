UPDATE desktop_source_capabilities
SET session_status = 'anonymous',
    list_status = 'verified',
    detail_status = 'verified',
    fields_status = 'partial',
    pagination_status = 'verified',
    enabled = 1,
    last_verified_at = '2026-09-18T00:00:00+00:00',
    notes = '腾讯公开招聘 JSON 接口已实测列表、JD 字段与分页；薪资字段未提供。'
WHERE source_id = 'company_01'
  AND source_type = 'company'
  AND list_status = 'unverified';
