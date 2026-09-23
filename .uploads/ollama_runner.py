"""Ollama 调用脚本(用户本地运行)。

用法:
1. 把 peptides_llm_bundle.json 和本脚本放在同一目录
2. 确保 Ollama 已启动(ollama serve 或后台运行)
3. 确保已 pull 模型:ollama pull qwen2.5:7b (或 qwen2.5:14b)
4. 运行:python ollama_runner.py
5. 跑完产出 peptides_llm_results.json
6. 把 peptides_llm_results.json 传回给沙箱

可选参数:
  --model qwen2.5:7b        指定模型
  --base http://localhost:11434  Ollama 地址
  --bundle peptides_llm_bundle.json  输入 bundle
  --output peptides_llm_results.json  输出
  --temperature 0.3
  --max-tokens 2000
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: 缺少 requests 库。请运行: pip install requests")
    sys.exit(1)


def extract_json(text: str) -> Optional[dict]:
    """从 LLM 输出中提取 JSON。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def call_ollama(base: str, model: str, system_prompt: str, user_prompt: str,
               temperature: float, max_tokens: int, timeout: int = 180) -> dict:
    """调用 Ollama /api/chat,返回完整调用记录。"""
    start = time.time()
    raw_response_text = ""
    parsed = None
    success = False
    error = None

    try:
        resp = requests.post(
            f"{base}/api/chat",
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
                "format": "json",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_response_text = data.get("message", {}).get("content", "")
        parsed = extract_json(raw_response_text)
        success = parsed is not None
        if not success:
            error = "JSON parse failed"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    latency = int((time.time() - start) * 1000)
    return {
        "model": model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response_text": raw_response_text,
        "parsed_json": parsed,
        "success": success,
        "error": error,
        "latency_ms": latency,
    }


def validate_evidence(parsed: Optional[dict], allowed_ids: list[str]) -> dict:
    """校验 evidence_item_ids 必须来自召回集。"""
    if not parsed:
        return {"valid": False, "reason": "no parsed JSON"}
    allowed = set(allowed_ids)
    llm_claimed = set()
    for issue in parsed.get("key_issues", []):
        for eid in issue.get("evidence_item_ids", []):
            llm_claimed.add(eid)
    invalid = llm_claimed - allowed
    return {
        "valid": len(invalid) == 0,
        "llm_claimed_ids": sorted(llm_claimed),
        "invalid_ids": sorted(invalid),
        "allowed_ids": sorted(allowed),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="qwen2.5:7b")
    p.add_argument("--base", default="http://localhost:11434")
    p.add_argument("--bundle", default="peptides_llm_bundle.json")
    p.add_argument("--output", default="peptides_llm_results.json")
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--max-tokens", type=int, default=2000)
    p.add_argument("--timeout", type=int, default=180)
    args = p.parse_args()

    if not os.path.exists(args.bundle):
        print(f"ERROR: bundle 文件不存在: {args.bundle}")
        print("请先从沙箱下载 peptides_llm_bundle.json 放到当前目录")
        sys.exit(1)

    # 检查 Ollama 是否在线
    try:
        r = requests.get(f"{args.base}/api/tags", timeout=5)
        r.raise_for_status()
        tags = r.json()
        available = [m["name"] for m in tags.get("models", [])]
        print(f"Ollama 在线,可用模型: {available}")
        if args.model not in available and not any(args.model in m for m in available):
            print(f"WARNING: 模型 {args.model} 不在列表中,可能需要 ollama pull {args.model}")
    except Exception as e:
        print(f"ERROR: 无法连接 Ollama ({args.base}): {e}")
        print("请确认: 1) ollama serve 已启动  2) 地址正确")
        sys.exit(1)

    with open(args.bundle, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    system_prompt = bundle["system_prompt"]
    tests = bundle["tests"]
    print(f"\n开始测试 {len(tests)} 条,模型={args.model},temperature={args.temperature}")
    print("=" * 60)

    results = []
    for i, t in enumerate(tests):
        print(f"\n[{i+1}/{len(tests)}] {t['id']}: {t['title'][:60]}")
        print(f"  调用 Ollama (最长 {args.timeout}s)...")
        call = call_ollama(
            base=args.base,
            model=args.model,
            system_prompt=system_prompt,
            user_prompt=t["user_prompt"],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )
        v = validate_evidence(call["parsed_json"], t["all_retrieved_item_ids"])

        result = {
            "test_id": t["id"],
            "title": t["title"],
            "selftext": t["selftext"],
            "new_content_tags": t["new_content_tags"],
            "all_retrieved_item_ids": t["all_retrieved_item_ids"],
            "similar_high_count": t["similar_high_count"],
            "similar_failure_count": t["similar_failure_count"],
            "patterns_count": t["patterns_count"],
            "llm_call": call,
            "evidence_validation": v,
        }
        results.append(result)

        if call["success"]:
            parsed = call["parsed_json"]
            print(f"  OK latency={call['latency_ms']}ms verdict={parsed.get('verdict')}")
            print(f"  key_issues={len(parsed.get('key_issues', []))} "
                  f"modifications={len(parsed.get('modification_suggestions', []))}")
            print(f"  evidence valid={v['valid']} claimed={v['llm_claimed_ids']}")
        else:
            print(f"  FAIL: {call['error']}")

    output = {
        "model": args.model,
        "base": args.base,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "system_prompt": system_prompt,
        "results": results,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 60)
    print(f"完成!结果已保存: {args.output}")
    print(f"请把 {args.output} 传回沙箱,沙箱会解析对比")


if __name__ == "__main__":
    main()
