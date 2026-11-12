"""Replaceable intranet LLM adapter with a deterministic offline fallback."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Protocol, Callable
from urllib import error, request


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    degraded: bool
    audit: dict[str, Any]


class LLMAdapter(Protocol):
    def explain(self, payload: dict[str, Any]) -> LLMResponse: ...
    def judge_relationships(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def judge_engineering_semantics(self, cases: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]: ...


def load_runtime_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    if config.get("schema_version") != "1.1.0":
        raise ValueError("Unsupported runtime configuration schema_version")
    return config


def _fact_summary(payload: dict[str, Any]) -> str:
    document = payload.get("document", "UNKNOWN")
    counts = payload.get("counts", {})
    conflicts = payload.get("conflicts", [])
    findings = payload.get("findings", [])
    lines = [
        f"模型：{document}",
    ]
    if findings:
        lines.append(
            "规则结果："
            f"PASS={counts.get('PASS', 0)}，"
            f"WARN={counts.get('WARN', 0)}，"
            f"FAIL={counts.get('FAIL', 0)}，"
            f"NOT_EVALUATED={counts.get('NOT_EVALUATED', 0)}，"
            f"EXEMPTED={counts.get('EXEMPTED', 0)}，"
            f"ERROR={counts.get('ERROR', 0)}"
        )
    else:
        lines.append(
            "结果："
            f"CLASH={counts.get('CLASH', 0)}，"
            f"CONTACT={counts.get('CONTACT', 0)}，"
            f"CLEARANCE={counts.get('CLEARANCE', 0)}，"
            f"EXEMPTED={counts.get('EXEMPTED', 0)}"
        )
    for item in conflicts[:20]:
        lines.append(
            f"- {item.get('type', 'UNKNOWN')}: "
            f"{item.get('first_product')} / {item.get('second_product')}，"
            f"CATIA值={item.get('value_mm')} mm，状态={item.get('rule_status')}"
        )
    for item in findings[:20]:
        measured = item.get("measured_value")
        measurement = ""
        if measured is not None:
            measurement = f"，实测={measured} {item.get('unit', '')}".rstrip()
        objects = " / ".join(
            value for value in (item.get("object_a"), item.get("object_b")) if value
        )
        lines.append(
            f"- {item.get('issue_id', 'UNKNOWN')} [{item.get('status', 'UNKNOWN')}/"
            f"{item.get('severity', 'UNKNOWN')}] {item.get('title', '')}"
            f"，对象={objects or 'UNKNOWN'}{measurement}"
        )
    budget = payload.get("confidence_budget")
    if isinstance(budget, dict):
        lines.append(
            "范围："
            f"已检查={len(budget.get('checked', []))}，"
            f"未检查={len(budget.get('not_checked', []))}，"
            f"降级={len(budget.get('degraded', []))}"
        )
    return "\n".join(lines)


class TemplateAdapter:
    """Offline fallback that never invents geometry conclusions."""

    def explain(self, payload: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            text=_fact_summary(payload),
            provider="template",
            model="deterministic-v1",
            degraded=True,
            audit={"reason": "LLM disabled or unavailable", "facts_preserved": True},
        )

    def judge_relationships(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Deliberately return no invented design intent. The caller validates
        # these results and applies its conservative deterministic fallback.
        from .component_relationships import conservative_assessment
        return [conservative_assessment(item).to_dict() for item in contexts]

    def judge_engineering_semantics(self, cases: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
        return [{"classification": "UNKNOWN", "confidence": 0.0, "evidence_refs": [],
                 "reason": "本地模板不生成新的工程语义。",
                 "uncertainty": [f"{kind} semantic judge disabled"]} for _ in cases]


class OpenAICompatibleIntranetAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config["base_url"]).rstrip("/")
        self.model = str(config["model"])
        self.timeout = float(config.get("timeout_seconds", 60))
        self.api_key_env = str(config.get("api_key_env", "CATIA_CHECKER_LLM_API_KEY"))
        self.extra_headers = dict(config.get("extra_headers", {}))

    def explain(self, payload: dict[str, Any]) -> LLMResponse:
        api_key = os.environ.get(self.api_key_env, "")
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是公司内网 CATIA 检查报告助手。只能解释输入的结构化事实；"
                        "不得改变数值、单位、CATIA冲突类型或规则状态；不得宣称模型合格。"
                    ),
                },
                {"role": "user", "content": _fact_summary(payload)},
            ],
        }
        endpoint = f"{self.base_url}/chat/completions"
        try:
            response = request.urlopen(
                request.Request(
                    endpoint,
                    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers=headers,
                    method="POST",
                ),
                timeout=self.timeout,
            )
            data = json.loads(response.read().decode("utf-8"))
            text = str(data["choices"][0]["message"]["content"])
            return LLMResponse(
                text=text,
                provider="openai_compatible_intranet",
                model=self.model,
                degraded=False,
                audit={"endpoint": endpoint, "facts_preserved": "requires_validation"},
            )
        except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
            fallback = TemplateAdapter().explain(payload)
            return LLMResponse(
                text=fallback.text,
                provider=fallback.provider,
                model=fallback.model,
                degraded=True,
                audit={"reason": type(exc).__name__, "endpoint": endpoint, "facts_preserved": True},
            )

    def judge_relationships(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Request structured design-relationship judgments from an intranet model."""
        api_key = os.environ.get(self.api_key_env, "")
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        instruction = (
            "你是CATIA组件关系复核器。仅依据输入事实判断近距离/接触是否符合设计意图。"
            "逐项返回JSON数组，顺序和数量必须与输入一致。每项仅含decision、confidence、"
            "reason、key_evidence、relation_type。decision只能是PASS_NORMAL_CONNECTION、"
            "CHECK_CLEARANCE、REVIEW_REQUIRED。名称只能作为弱证据；STEP缺少语义时从严。"
            "穿透不得判PASS_NORMAL_CONNECTION；证据不足必须REVIEW_REQUIRED。不得改写距离。"
        )
        body = {"model": self.model, "temperature": 0, "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(contexts, ensure_ascii=False)},
        ]}
        endpoint = f"{self.base_url}/chat/completions"
        try:
            response = request.urlopen(request.Request(
                endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers=headers, method="POST"), timeout=self.timeout)
            content = str(json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"])
            if content.startswith("```"):
                content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(content)
            if not isinstance(result, list):
                raise ValueError("relationship response is not a JSON array")
            return result
        except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
            return TemplateAdapter().judge_relationships(contexts)

    def judge_engineering_semantics(self, cases: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
        allowed = ("PIPE,FITTING,FLANGE,CLAMP,BRACKET,CASE_STRUCTURE,OTHER,UNKNOWN"
                   if kind == "object" else
                   "CONNECTED,SUPPORTED,NEARBY,INTERFERENCE,UNKNOWN")
        instruction = (
            "你是哑模型工程语义判断器。只能使用每个case的facts，名称仅为弱证据。"
            "逐项返回JSON数组，每项必须且只能包含classification、confidence、evidence_refs、"
            "reason、uncertainty。classification允许值：" + allowed + "。"
            "evidence_refs只能引用facts中实际存在的键；证据不足返回UNKNOWN。"
            "禁止输出PASS、FAIL、豁免或任何检查处置。"
        )
        api_key = os.environ.get(self.api_key_env, "")
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {"model": self.model, "temperature": 0, "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(cases, ensure_ascii=False)},
        ]}
        endpoint = f"{self.base_url}/chat/completions"
        try:
            response = request.urlopen(request.Request(
                endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers=headers, method="POST"), timeout=self.timeout)
            content = str(json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"])
            if content.startswith("```"):
                content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(content)
            if not isinstance(result, list):
                raise ValueError("semantic response is not a JSON array")
            return result
        except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
            return TemplateAdapter().judge_engineering_semantics(cases, kind)


_PROVIDER_FACTORIES: dict[str, Callable[[dict[str, Any]], LLMAdapter]] = {}


def register_llm_provider(name: str, factory: Callable[[dict[str, Any]], LLMAdapter]) -> None:
    """Register an explicit local provider factory; never dynamically import configuration text."""
    if not name or name in {"template", "openai_compatible_intranet"} or name in _PROVIDER_FACTORIES:
        raise ValueError("Provider name is empty, reserved or already registered")
    _PROVIDER_FACTORIES[name] = factory


def create_llm_adapter(runtime_config: dict[str, Any]) -> LLMAdapter:
    llm = runtime_config.get("llm", {})
    mode = llm.get("mode", "template")
    if mode in _PROVIDER_FACTORIES:
        return _PROVIDER_FACTORIES[mode](llm)
    if mode == "template":
        return TemplateAdapter()
    if mode == "openai_compatible_intranet":
        return OpenAICompatibleIntranetAdapter(llm)
    raise ValueError(f"Unsupported llm.mode: {mode}")
