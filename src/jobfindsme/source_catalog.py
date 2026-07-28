from __future__ import annotations

from urllib.parse import quote_plus

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> tuple[DiscoverySource, ...]:
    """Return only sources with a maintained public connector contract."""

    if not _targets_china(locations):
        return ()
    query = " ".join(roles[:3]) if roles else "AI 大模型 Agent"
    return (
        DiscoverySource(
            kind="baidu_career",
            source_name="百度招聘",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="字节跳动",
            site_key="bytedance",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="美团",
            site_key="meituan",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="滴滴",
            site_key="didi",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="哔哩哔哩",
            site_key="bilibili",
            query=query,
        ),
        DiscoverySource(
            kind="greenhouse",
            source_name="Airbnb 中国",
            board_token="airbnb",
        ),
        DiscoverySource(
            kind="ashby",
            source_name="Airwallex",
            board_name="airwallex",
        ),
    )


def source_links(
    roles: tuple[str, ...],
    locations: tuple[str, ...],
) -> tuple[SourceLink, ...]:
    """Official live-search links; link-only entries are never scraped."""

    query = " ".join((*roles, *locations)).strip() or "AI 工程师"
    encoded = quote_plus(query)

    return (
        # ── 有自动 Connector 的企业 ──
        SourceLink(
            name="百度招聘 (自动)",
            category="企业官网 · 自动发现",
            url=f"https://talent.baidu.com/jobs/social-list?search={encoded}",
            access_mode="official_link",
            note="已接入自动 Connector，岗位实时获取并匹配",
        ),
        SourceLink(
            name="腾讯招聘 (自动)",
            category="企业官网 · 自动发现",
            url="https://careers.tencent.com/zh-cn/search.html",
            access_mode="official_link",
            note="已接入自动 Connector，岗位实时获取并匹配",
        ),
        SourceLink(
            name="字节跳动招聘 (自动)",
            category="企业官网 · 自动发现",
            url=f"https://jobs.bytedance.com/experienced/position?keywords={encoded}",
            access_mode="official_link",
            note="已接入 Playwright 自动 Connector，岗位实时获取并匹配",
        ),
        SourceLink(
            name="美团招聘 (自动)",
            category="企业官网 · 自动发现",
            url=f"https://zhaopin.meituan.com/web/campus?keyword={encoded}",
            access_mode="official_link",
            note="已接入 Playwright 自动 Connector，岗位实时获取并匹配",
        ),
        SourceLink(
            name="滴滴招聘 (自动)",
            category="企业官网 · 自动发现",
            url=f"https://talent.didiglobal.com/social?keyword={encoded}",
            access_mode="official_link",
            note="已接入 Playwright 自动 Connector，岗位实时获取并匹配",
        ),
        SourceLink(
            name="哔哩哔哩招聘 (自动)",
            category="企业官网 · 自动发现",
            url=f"https://jobs.bilibili.com/social?keyword={encoded}",
            access_mode="official_link",
            note="已接入 Playwright 自动 Connector，岗位实时获取并匹配",
        ),
        SourceLink(
            name="Airbnb 中国 (自动)",
            category="企业官网 · 自动发现",
            url="https://boards.greenhouse.io/airbnb",
            access_mode="official_link",
            note="通过 Greenhouse 公开 API 自动获取中国区岗位",
        ),
        # ── 企业官网（手动浏览） ──
        SourceLink(
            name="阿里巴巴招聘",
            category="企业官网 · 互联网大厂",
            url=f"https://talent.alibaba.com/off-campus/?search={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="华为招聘",
            category="企业官网 · 互联网大厂",
            url="https://career.huawei.com/reccampportal/portal5/social-recruitment-ai.html",
            access_mode="official_link",
            note="AI 社会招聘专区",
        ),
        SourceLink(
            name="京东招聘",
            category="企业官网 · 互联网大厂",
            url=f"https://zhaopin.jd.com/web/jobs?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="网易招聘",
            category="企业官网 · 互联网大厂",
            url=f"https://hr.163.com/job-list.html?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="拼多多招聘",
            category="企业官网 · 互联网大厂",
            url=f"https://careers.pinduoduo.com/jobs?search={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="小红书招聘",
            category="企业官网 · 知名企业",
            url=f"https://job.xiaohongshu.com/social?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="快手招聘",
            category="企业官网 · 知名企业",
            url=(f"https://zhaopin.kuaishou.cn/recruit/social?searchKey={encoded}"),
            access_mode="official_link",
        ),
        SourceLink(
            name="小米招聘",
            category="企业官网 · 知名企业",
            url=f"https://zhaopin.xiaomi.com/?keywords={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="携程招聘",
            category="企业官网 · 知名企业",
            url=f"https://job.ctrip.com/social-recruitment.html?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="蚂蚁集团招聘",
            category="企业官网 · 知名企业",
            url=f"https://talent.antgroup.com/position?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="联想招聘",
            category="企业官网 · 知名企业",
            url=f"https://talent.lenovo.com.cn/search?key={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="大疆招聘",
            category="企业官网 · 知名企业",
            url=f"https://we.dji.com/zh-CN/social?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="商汤科技招聘",
            category="企业官网 · 知名企业",
            url=f"https://www.sensetime.com/cn/join-list?keyword={encoded}",
            access_mode="official_link",
        ),
        # ── AI & 新势力企业 ──
        SourceLink(
            name="科大讯飞招聘",
            category="企业官网 · AI企业",
            url=f"https://www.iflytek.com/career/social?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="旷视科技招聘",
            category="企业官网 · AI企业",
            url="https://www.megvii.com/career/",
            access_mode="official_link",
        ),
        SourceLink(
            name="知乎招聘",
            category="企业官网 · AI企业",
            url="https://www.zhihu.com/careers",
            access_mode="official_link",
        ),
        SourceLink(
            name="米哈游招聘",
            category="企业官网 · AI企业",
            url=f"https://campus.mihoyo.com/?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="理想汽车招聘",
            category="企业官网 · AI企业",
            url=f"https://www.lixiang.com/careers?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="小鹏汽车招聘",
            category="企业官网 · AI企业",
            url=f"https://careers.xiaopeng.com/?keyword={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="蔚来招聘",
            category="企业官网 · AI企业",
            url=f"https://www.nio.cn/careers?keyword={encoded}",
            access_mode="official_link",
        ),
        # ── 招聘平台（用户自行浏览） ──
        SourceLink(
            name="BOSS直聘",
            category="招聘平台",
            url=f"https://www.zhipin.com/web/geek/job?query={encoded}",
            access_mode="user_browser",
            note="需在平台登录后查看",
        ),
        SourceLink(
            name="猎聘",
            category="招聘平台",
            url=f"https://www.liepin.com/zhaopin/?key={encoded}",
            access_mode="user_browser",
        ),
        SourceLink(
            name="智联招聘",
            category="招聘平台",
            url=f"https://sou.zhaopin.com/?kw={encoded}",
            access_mode="user_browser",
        ),
        SourceLink(
            name="前程无忧",
            category="招聘平台",
            url=f"https://we.51job.com/pc/search?keyword={encoded}",
            access_mode="user_browser",
        ),
    )


def _targets_china(locations: tuple[str, ...]) -> bool:
    if not locations:
        return True
    china_markers = (
        "中国",
        "北京",
        "上海",
        "深圳",
        "杭州",
        "广州",
        "成都",
        "武汉",
        "南京",
        "苏州",
        "西安",
        "重庆",
    )
    return any(marker in location for location in locations for marker in china_markers)
