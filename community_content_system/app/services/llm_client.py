"""LLM Provider 抽象层。

设计原则:
- 业务层只调 llm_complete()/llm_chat() 接口,不感知具体 provider
- 三种实现:MockLLMProvider(确定性规则输出,验证链路) / OllamaProvider / OpenAICompatibleProvider
- 切换 provider 只改 config.llm_provider,业务层零改动
- 每次调用记录 LLMCallLog(模型/输入/输出/耗时/结果),便于后续比较
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests

from ..config import settings

logger = logging.getLogger(__name__)


# ============================================================
# LLMCallLog — 调用日志
# ============================================================
class LLMCallLog:
    """记录每次 LLM 调用的完整信息,便于后续模型比较。

    不入库,由调用方决定是否持久化。这里只做结构化记录。
    """

    def __init__(
        self,
        task: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        parsed_json: Optional[dict],
        success: bool,
        source: str,  # llm | rule_based_fallback
        error: Optional[str],
        latency_ms: int,
        prompt_version: str,
    ):
        self.task = task
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.response_text = response_text
        self.parsed_json = parsed_json
        self.success = success
        self.source = source
        self.error = error
        self.latency_ms = latency_ms
        self.prompt_version = prompt_version
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response_text": self.response_text,
            "parsed_json": self.parsed_json,
            "success": self.success,
            "source": self.source,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "prompt_version": self.prompt_version,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"LLMCallLog(task={self.task}, model={self.model}, "
            f"source={self.source}, success={self.success}, "
            f"latency={self.latency_ms}ms)"
        )


# ============================================================
# LLMResponse — 统一响应结构
# ============================================================
class LLMResponse:
    def __init__(
        self,
        content: str,
        parsed_json: Optional[dict],
        model: str,
        source: str,
        success: bool,
        error: Optional[str],
        latency_ms: int,
    ):
        self.content = content
        self.parsed_json = parsed_json
        self.model = model
        self.source = source
        self.success = success
        self.error = error
        self.latency_ms = latency_ms


# ============================================================
# LLMProvider 抽象基类
# ============================================================
class LLMProvider(ABC):
    """LLM Provider 抽象基类。

    业务层通过此接口调用 LLM,不感知具体实现。
    """

    @abstractmethod
    def complete(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.3,
        response_format: str = "json",
        max_tokens: int = 2000,
    ) -> tuple[LLMResponse, LLMCallLog]:
        """调用 LLM,返回 (response, call_log)。"""
        ...


# ============================================================
# MockLLMProvider — 确定性规则输出,验证链路(沙箱默认)
# ============================================================
class MockLLMProvider(LLMProvider):
    """确定性 mock,不调任何外部 API。

    输出基于关键词规则,保证可复现,用于验证链路而非追求效果。
    """

    def complete(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.3,
        response_format: str = "json",
        max_tokens: int = 2000,
    ) -> tuple[LLMResponse, LLMCallLog]:
        start = time.time()

        try:
            if task == "classify":
                result = self._mock_classify(user_prompt)
            elif task == "analyze":
                result = self._mock_analyze(user_prompt)
            elif task == "pattern_mine":
                result = self._mock_pattern_mine(user_prompt)
            else:
                result = {"error": f"unknown task: {task}"}

            content = json.dumps(result, ensure_ascii=False)
            latency = int((time.time() - start) * 1000)

            resp = LLMResponse(
                content=content,
                parsed_json=result,
                model=model,
                source="mock",
                success=True,
                error=None,
                latency_ms=latency,
            )
            log = LLMCallLog(
                task=task,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_text=content,
                parsed_json=result,
                success=True,
                source="mock",
                error=None,
                latency_ms=latency,
                prompt_version=settings.llm_prompt_version,
            )
            return resp, log

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            err = f"mock error: {e}"
            resp = LLMResponse(
                content="",
                parsed_json=None,
                model=model,
                source="mock",
                success=False,
                error=err,
                latency_ms=latency,
            )
            log = LLMCallLog(
                task=task,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_text="",
                parsed_json=None,
                success=False,
                source="mock",
                error=err,
                latency_ms=latency,
                prompt_version=settings.llm_prompt_version,
            )
            return resp, log

    def _mock_classify(self, user_prompt: str) -> dict:
        """确定性分类:基于关键词的规则式标签。"""
        text_lower = user_prompt.lower()

        # topic
        topic_tags = []
        topic_map = {
            "organizing": ["organizing", "organization", "organize", "declutter"],
            "label": ["label", "labeling", "label machine", "labelmaker"],
            "python": ["python", "programming", "code"],
            "business": ["business", "selling", "etsy", "shop", "product"],
            "craft": ["craft", "diy", "handmade", "making"],
            "gardening": ["garden", "plant", "seed"],
            "baking": ["baking", "food", "meal prep", "freezer"],
        }
        for topic, keywords in topic_map.items():
            if any(kw in text_lower for kw in keywords):
                topic_tags.append(topic)
        if not topic_tags:
            topic_tags = ["general"]

        # scenario
        scenario_tags = []
        if any(kw in text_lower for kw in ["struggle", "frustrated", "help", "how do i"]):
            scenario_tags.append("learning_struggle")
        if any(kw in text_lower for kw in ["my", "i ", "experience", "story"]):
            scenario_tags.append("personal_experience")
        if any(kw in text_lower for kw in ["review", "recommend", "best"]):
            scenario_tags.append("recommendation_request")
        if not scenario_tags:
            scenario_tags = ["general"]

        # structure
        structure_tags = []
        if any(kw in text_lower for kw in ["how", "what", "why", "?"]):
            structure_tags.append("question")
        if any(kw in text_lower for kw in ["i ", "my", "after", "finally"]):
            structure_tags.append("experience")
        if any(kw in text_lower for kw in ["check out", "introducing", "buy", "discount"]):
            structure_tags.append("promotional")
        if not structure_tags:
            structure_tags = ["experience"]

        # product_visibility
        promo_keywords = ["buy", "discount", "check out", "introducing", "sale", "http"]
        brand_keywords = ["niimbot", "dymo", "brother", "epson"]
        product_keywords = ["label maker", "label machine", "labelmaker", "printer"]

        has_promo = any(kw in text_lower for kw in promo_keywords)
        has_brand = any(kw in text_lower for kw in brand_keywords)
        has_product = any(kw in text_lower for kw in product_keywords)

        if has_promo and has_brand:
            product_visibility = "promotional"
        elif has_brand and (has_product or "introduc" in text_lower):
            product_visibility = "explicit"
        elif has_product and not has_brand:
            product_visibility = "natural"
        elif has_product or has_brand:
            product_visibility = "subtle"
        else:
            product_visibility = "none"

        brand_mentions = []
        for brand in ["niimbot", "dymo", "brother", "epson", "zebra"]:
            if brand in text_lower:
                brand_mentions.append(brand)

        # search_value
        has_question = "?" in user_prompt
        has_how = "how" in text_lower
        is_timeless = not any(
            kw in text_lower for kw in ["today", "now", "just", "breaking"]
        )
        if (has_question or has_how) and is_timeless:
            search_value = "high"
        elif has_question or has_how:
            search_value = "mid"
        else:
            search_value = "low"

        return {
            "topic_tags": topic_tags,
            "scenario_tags": scenario_tags,
            "structure_tags": structure_tags,
            "product_visibility": product_visibility,
            "brand_mentions": brand_mentions,
            "search_value": search_value,
            "search_value_reasoning": f"mock classification: question={has_question}, timeless={is_timeless}",
        }

    def _mock_analyze(self, user_prompt: str) -> dict:
        """确定性新内容判断。"""
        text_lower = user_prompt.lower()

        # 判断 product_visibility
        promo_keywords = ["buy", "discount", "check out", "introducing", "sale"]
        brand_keywords = ["niimbot", "dymo", "brother"]
        product_at_start = bool(
            user_prompt.strip()
            and any(user_prompt.strip().lower().startswith(b) for b in brand_keywords)
        )

        has_promo = any(kw in text_lower for kw in promo_keywords)
        has_brand = any(kw in text_lower for kw in brand_keywords)

        # verdict
        if has_promo and has_brand:
            verdict = "not_fit"
            verdict_reason = "内容广告感过重,含促销关键词+品牌名,与社区经验型内容结构差异大"
        elif product_at_start:
            verdict = "not_fit"
            verdict_reason = "标题以品牌名开头,该社区高互动内容多从具体场景/问题切入"
        elif has_brand and not has_promo:
            verdict = "fit_after_fix"
            verdict_reason = "内容方向相关但品牌露出方式需调整以更自然"
        else:
            verdict = "fit"
            verdict_reason = "内容结构符合该社区常见经验型帖子"

        # key_issues
        key_issues = []
        if product_at_start:
            key_issues.append({
                "issue": "标题直接以产品/品牌名称开头",
                "why": "该社区近期高互动内容多数从具体使用场景进入,产品在正文中自然出现",
                "evidence_type": ["high_performance_content", "similar_content"],
                "evidence_item_ids": [],
                "fix": "把第一句从产品介绍改成具体场景/问题;产品信息放到第二段,在描述解决过程时自然带出",
            })
        if has_promo:
            key_issues.append({
                "issue": "内容含促销关键词(buy/discount/sale)",
                "why": "该社区对促销内容敏感度较高,容易被识别为广告",
                "evidence_type": ["community_rule", "low_performance_content"],
                "evidence_item_ids": [],
                "fix": "移除促销关键词,改为分享使用经验",
            })
        if not key_issues:
            key_issues.append({
                "issue": "内容较为简洁,可补充具体使用细节",
                "why": "该社区高互动内容通常包含具体场景描述",
                "evidence_type": ["similar_content"],
                "evidence_item_ids": [],
                "fix": "补充具体使用场景、解决问题的过程描述",
            })

        # modification_suggestions
        modifications = []
        if product_at_start:
            modifications.append({
                "target": "标题",
                "current": user_prompt.split("\n")[0][:80],
                "suggested": "How I finally organized my [space] with a simple labeling system",
                "reason": "高表现案例标题多从具体问题/经验切入",
            })
        if has_promo:
            modifications.append({
                "target": "正文",
                "current": "含促销关键词的部分",
                "suggested": "改为描述具体使用过程和效果",
                "reason": "移除广告感,符合社区经验型内容结构",
            })

        # comment_participation_advice
        if verdict == "not_fit":
            comment_advice = {
                "should_reply_natural_comments": False,
                "should_supplement_own_comment": False,
                "should_wait_for_natural_discussion": False,
                "should_share_product_in_comments": False,
                "should_participate_before_posting": False,
                "confidence": "insufficient",
                "reasoning": "内容不适合发布,无需评论参与建议",
                "evidence_insufficient": True,
            }
        else:
            comment_advice = {
                "should_reply_natural_comments": True,
                "should_supplement_own_comment": False,
                "should_wait_for_natural_discussion": True,
                "should_share_product_in_comments": False,
                "should_participate_before_posting": False,
                "confidence": "medium",
                "reasoning": "基于该社区评论模式,用户多追问具体细节,适合主动回答",
                "evidence_insufficient": False,
            }

        # potential_value
        value_types = ["interaction"]
        if "?" in user_prompt or "how" in text_lower:
            value_types.append("discussion")
        if verdict == "fit":
            value_types.append("community_penetration")

        return {
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "key_issues": key_issues,
            "modification_suggestions": modifications,
            "comment_participation_advice": comment_advice,
            "potential_value": {
                "value_types": value_types,
                "reasoning": "基于内容结构和社区规律的 mock 判断",
            },
            "evidence": {
                "community_rule": True,
                "similar_content_count": 3,
                "high_performance_count": 2,
                "mid_performance_count": 2,
                "low_performance_count": 1,
                "knowledge_patterns_applied": [],
            },
        }

    def _mock_pattern_mine(self, user_prompt: str) -> dict:
        """确定性规律提炼。"""
        return {
            "patterns": [
                {
                    "pattern_type": "fire",
                    "description": "具体问题 → 个人经历 → 解决过程 → 产品自然出现",
                    "applicable_conditions": {
                        "structure": "experience",
                        "scenario": "learning_struggle",
                    },
                    "evidence_item_ids": [],
                    "sample_count": 3,
                },
                {
                    "pattern_type": "failure",
                    "description": "开头直接品牌/产品介绍 + 缺少用户问题",
                    "applicable_conditions": {
                        "structure": "promotional",
                    },
                    "evidence_item_ids": [],
                    "sample_count": 2,
                },
            ]
        }


# ============================================================
# OllamaProvider — 本地 Ollama
# ============================================================
class OllamaProvider(LLMProvider):
    """Ollama 本地模型 provider。

    部署到有 Ollama 的机器时:
    1. ollama pull qwen2.5:7b
    2. config.llm_provider = "ollama"
    3. config.llm_api_base = "http://localhost:11434"
    """

    def complete(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.3,
        response_format: str = "json",
        max_tokens: int = 2000,
    ) -> tuple[LLMResponse, LLMCallLog]:
        start = time.time()
        content = ""
        parsed = None
        success = False
        error = None

        for attempt in range(settings.llm_retries + 1):
            try:
                resp = requests.post(
                    f"{settings.llm_api_base}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                        "format": "json" if response_format == "json" else None,
                    },
                    timeout=settings.llm_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")

                if response_format == "json":
                    parsed = self._extract_json(content)

                success = True
                break

            except Exception as e:
                error = f"ollama attempt {attempt + 1}: {e}"
                if attempt < settings.llm_retries:
                    time.sleep(2 ** attempt)
                else:
                    success = False

        latency = int((time.time() - start) * 1000)

        resp_obj = LLMResponse(
            content=content,
            parsed_json=parsed,
            model=model,
            source="ollama",
            success=success,
            error=error,
            latency_ms=latency,
        )
        log = LLMCallLog(
            task=task,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=content,
            parsed_json=parsed,
            success=success,
            source="ollama" if success else "failed",
            error=error,
            latency_ms=latency,
            prompt_version=settings.llm_prompt_version,
        )
        return resp_obj, log

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """从 LLM 输出中提取 JSON(可能包裹在 ```json ... ``` 中)。"""
        # 尝试直接 parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ```
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... }
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None


# ============================================================
# OpenAICompatibleProvider — OpenAI 兼容 API(付费)
# ============================================================
class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API provider。

    支持 OpenAI / Azure / 其他兼容服务。
    切换付费 provider:
    1. config.llm_provider = "openai_compatible"
    2. config.llm_api_base = "https://api.openai.com/v1"
    3. config.llm_api_key = "sk-..."
    """

    def complete(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.3,
        response_format: str = "json",
        max_tokens: int = 2000,
    ) -> tuple[LLMResponse, LLMCallLog]:
        start = time.time()
        content = ""
        parsed = None
        success = False
        error = None

        for attempt in range(settings.llm_retries + 1):
            try:
                payload: dict = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format == "json":
                    payload["response_format"] = {"type": "json_object"}

                resp = requests.post(
                    f"{settings.llm_api_base}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=settings.llm_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                if response_format == "json":
                    parsed = OllamaProvider._extract_json(content)

                success = True
                break

            except Exception as e:
                error = f"openai_compatible attempt {attempt + 1}: {e}"
                if attempt < settings.llm_retries:
                    time.sleep(2 ** attempt)
                else:
                    success = False

        latency = int((time.time() - start) * 1000)

        resp_obj = LLMResponse(
            content=content,
            parsed_json=parsed,
            model=model,
            source="openai_compatible",
            success=success,
            error=error,
            latency_ms=latency,
        )
        log = LLMCallLog(
            task=task,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=content,
            parsed_json=parsed,
            success=success,
            source="openai_compatible" if success else "failed",
            error=error,
            latency_ms=latency,
            prompt_version=settings.llm_prompt_version,
        )
        return resp_obj, log


# ============================================================
# 工厂函数
# ============================================================
_provider_instance: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """根据 config.llm_provider 返回对应 provider 实例。"""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    provider_map = {
        "mock": MockLLMProvider,
        "ollama": OllamaProvider,
        "openai_compatible": OpenAICompatibleProvider,
    }

    provider_cls = provider_map.get(settings.llm_provider, MockLLMProvider)
    _provider_instance = provider_cls()
    return _provider_instance


def reset_llm_provider() -> None:
    """重置 provider 单例(测试用)。"""
    global _provider_instance
    _provider_instance = None
