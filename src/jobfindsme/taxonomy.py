from __future__ import annotations

import re

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Java": ("java",),
    "Go": ("golang", "go语言"),
    "C++": ("c++", "cpp"),
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "Django": ("django",),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "Transformers": ("transformers", "huggingface"),
    "RAG": ("rag", "检索增强生成", "知识库问答"),
    "Agent": ("agent", "智能体", "ai agent"),
    "MCP": ("mcp", "model context protocol"),
    "LangGraph": ("langgraph",),
    "LangChain": ("langchain",),
    "LlamaIndex": ("llamaindex", "llama index"),
    "vLLM": ("vllm",),
    "LoRA": ("lora", "qlora"),
    "Milvus": ("milvus",),
    "Elasticsearch": ("elasticsearch", "es"),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "Redis": ("redis",),
    "MongoDB": ("mongodb", "mongo"),
    "Docker": ("docker", "容器化"),
    "Kubernetes": ("kubernetes", "k8s"),
    "Git": ("git",),
    "Linux": ("linux",),
    "BM25": ("bm25",),
    "向量数据库": ("向量数据库", "vector database"),
    "Embedding": ("embedding", "嵌入模型"),
    "Reranker": ("reranker", "重排模型", "精排"),
    "Function Calling": ("function calling", "函数调用", "工具调用"),
}

ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "AI应用工程师": (
        "ai应用工程师",
        "大模型应用工程师",
        "llm应用工程师",
        "生成式ai工程师",
        "agent工程师",
    ),
    "算法工程师": ("算法工程师", "机器学习工程师", "深度学习工程师"),
    "后端工程师": ("后端工程师", "服务端工程师", "backend engineer"),
}

LOCATION_ALIASES: dict[str, tuple[str, ...]] = {
    "中国": ("china", "cn -"),
    "北京": ("beijing", "北京市"),
    "上海": ("shanghai", "上海市"),
    "深圳": ("shenzhen", "深圳市"),
    "杭州": ("hangzhou", "杭州市"),
    "广州": ("guangzhou", "广州市"),
    "成都": ("chengdu", "成都市"),
    "重庆": ("chongqing", "重庆市"),
    "武汉": ("wuhan", "武汉市"),
    "西安": ("xi'an", "xian", "西安市"),
    "南京": ("nanjing", "南京市"),
    "苏州": ("suzhou", "苏州市"),
}


def extract_skills(text: str) -> dict[str, str]:
    """Return canonical skill -> exact evidence snippet."""
    normalized = text.casefold()
    found: dict[str, str] = {}
    for canonical, aliases in SKILL_ALIASES.items():
        candidates = (canonical, *aliases)
        for alias in sorted(candidates, key=len, reverse=True):
            match = re.search(
                rf"(?<![a-z0-9+#]){re.escape(alias.casefold())}(?![a-z0-9+#])",
                normalized,
            )
            if match:
                found[canonical] = text[match.start() : match.end()]
                break
    return found


def extract_required_skills(text: str) -> dict[str, str]:
    markers = ("任职要求", "职位要求", "必备条件", "必须", "requirements")
    normalized = text.casefold()
    offsets = [normalized.find(marker.casefold()) for marker in markers]
    offsets = [offset for offset in offsets if offset >= 0]
    required_text = text[min(offsets) :] if offsets else ""
    return extract_skills(required_text)


def expand_role_terms(roles: tuple[str, ...]) -> tuple[str, ...]:
    expanded: list[str] = []
    for role in roles:
        normalized = role.casefold()
        expanded.append(role)
        for canonical, aliases in ROLE_ALIASES.items():
            family = (canonical, *aliases)
            if any(
                item.casefold() in normalized or normalized in item.casefold()
                for item in family
            ):
                expanded.extend(family)
    return tuple(dict.fromkeys(expanded))


def expand_location_terms(locations: tuple[str, ...]) -> tuple[str, ...]:
    expanded: list[str] = []
    for location in locations:
        normalized = location.casefold()
        expanded.append(location)
        for canonical, aliases in LOCATION_ALIASES.items():
            family = (canonical, *aliases)
            if any(
                item.casefold() in normalized or normalized in item.casefold()
                for item in family
            ):
                expanded.extend(family)
    return tuple(dict.fromkeys(expanded))
