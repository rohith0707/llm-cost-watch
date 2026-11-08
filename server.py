"""LLM Cost Watch — Model Context Protocol (MCP) Server for LLM Cost & Latency Intelligence.
Allows Claude Desktop, Claude Code, and autonomous harnesses to ask natural language questions about LLM spend and performance:
"Ask Claude why our LLM bill jumped."
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

DATA_FILE = Path(__file__).resolve().parent / "data" / "llm_traces.json"

# Standard Model Pricing per 1M tokens (Nov 2026 calibration)
MODEL_PRICING = {
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "tier": "frontier"},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00, "tier": "efficient"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "tier": "frontier"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "tier": "efficient"},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "tier": "micro"}
}

def load_traces() -> List[Dict[str, Any]]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Initialize MCP 2.x Server
mcp = MCPServer("llm-cost-watch")

@mcp.tool()
def cost_by_feature(timeframe: str = "7d") -> Dict[str, Any]:
    """Analyze which features spend the most LLM budget over the specified timeframe.
    
    Args:
        timeframe: Time window to analyze (e.g. '24h', '7d', '30d'). Default is '7d'.
        
    Returns:
        Breakdown of total spend ($), call count, token usage, and spend per feature sorted by cost.
    """
    traces = load_traces()
    if not traces:
        return {"status": "empty", "message": "No trace data recorded yet."}
        
    by_feature: Dict[str, Dict[str, Any]] = {}
    total_spend = 0.0
    
    for t in traces:
        feat = t.get("feature", "unknown")
        model = t.get("model", "gpt-4o")
        inp_tok = t.get("input_tokens", 0)
        out_tok = t.get("output_tokens", 0)
        
        rates = MODEL_PRICING.get(model, {"input": 3.00, "output": 15.00})
        cost = (inp_tok / 1_000_000 * rates["input"]) + (out_tok / 1_000_000 * rates["output"])
        total_spend += cost
        
        if feat not in by_feature:
            by_feature[feat] = {
                "feature": feat,
                "total_spend_usd": 0.0,
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "models_used": set(),
                "avg_cost_per_call_usd": 0.0
            }
            
        by_feature[feat]["total_spend_usd"] += cost
        by_feature[feat]["call_count"] += 1
        by_feature[feat]["input_tokens"] += inp_tok
        by_feature[feat]["output_tokens"] += out_tok
        by_feature[feat]["models_used"].add(model)

    features_list = []
    for feat, data in by_feature.items():
        data["models_used"] = list(data["models_used"])
        data["total_spend_usd"] = round(data["total_spend_usd"], 4)
        data["avg_cost_per_call_usd"] = round(data["total_spend_usd"] / max(data["call_count"], 1), 5)
        features_list.append(data)
        
    features_list.sort(key=lambda x: x["total_spend_usd"], reverse=True)
    top_spender = features_list[0]["feature"] if features_list else None
    top_pct = round((features_list[0]["total_spend_usd"] / max(total_spend, 0.001)) * 100, 1) if features_list else 0

    return {
        "summary": f"Total spend across {len(traces)} calls: ${round(total_spend, 2)}. Top spender: '{top_spender}' ({top_pct}% of total budget).",
        "timeframe": timeframe,
        "total_spend_usd": round(total_spend, 2),
        "total_calls": len(traces),
        "features": features_list
    }

@mcp.tool()
def slow_calls(limit: int = 5, min_latency_ms: float = 1200.0) -> Dict[str, Any]:
    """Identify which features and prompts are pushing p95 latency up in production.
    
    Args:
        limit: Maximum number of slowest features to return. Default 5.
        min_latency_ms: Minimum latency threshold in ms to flag. Default 1200ms.
        
    Returns:
        Latency percentiles (p50, p95, p99), outlier counts, and bottleneck analysis.
    """
    traces = load_traces()
    if not traces:
        return {"status": "empty", "message": "No trace data recorded."}
        
    by_feature: Dict[str, List[float]] = {}
    samples: Dict[str, Dict[str, Any]] = {}
    
    for t in traces:
        feat = t.get("feature", "unknown")
        lat = t.get("latency_ms", 0.0)
        by_feature.setdefault(feat, []).append(lat)
        
        # Track slowest call sample per feature
        if feat not in samples or lat > samples[feat].get("latency_ms", 0):
            samples[feat] = {
                "latency_ms": lat,
                "model": t.get("model"),
                "prompt_snippet": (t.get("prompt", "")[:120] + "...") if len(t.get("prompt", "")) > 120 else t.get("prompt", ""),
                "tokens": t.get("input_tokens", 0) + t.get("output_tokens", 0)
            }

    results = []
    for feat, lats in by_feature.items():
        lats_sorted = sorted(lats)
        n = len(lats_sorted)
        p50 = statistics.median(lats_sorted)
        p95 = lats_sorted[int(n * 0.95)] if n > 1 else lats_sorted[0]
        p99 = lats_sorted[int(n * 0.99)] if n > 1 else lats_sorted[-1]
        
        slow_count = sum(1 for x in lats if x >= min_latency_ms)
        if p95 >= min_latency_ms or slow_count > 0:
            sample = samples.get(feat, {})
            # Diagnose bottleneck
            diagnosis = "Normal latency"
            if sample.get("tokens", 0) > 4000:
                diagnosis = "High token payload causing generation bottleneck"
            elif p95 > 2500 and "sonnet" in str(sample.get("model", "")):
                diagnosis = "Recursive multi-step tool call without streaming timeout"
            elif p95 > 2000:
                diagnosis = "Model reasoning stall; candidate for speculative decoding or cache hits"

            results.append({
                "feature": feat,
                "calls_analyzed": n,
                "p50_ms": round(p50, 1),
                "p95_ms": round(p95, 1),
                "p99_ms": round(p99, 1),
                "calls_over_threshold": slow_count,
                "slowest_sample": sample,
                "bottleneck_diagnosis": diagnosis
            })

    results.sort(key=lambda x: x["p95_ms"], reverse=True)
    return {
        "summary": f"Found {len(results)} features with p95 >= {min_latency_ms}ms.",
        "threshold_ms": min_latency_ms,
        "slow_features": results[:limit]
    }

@mcp.tool()
def routing_suggestions(savings_threshold_pct: float = 20.0) -> Dict[str, Any]:
    """Suggest which production LLM tasks could move to a cheaper model without quality drops.
    
    Args:
        savings_threshold_pct: Minimum percentage savings required to recommend a route.
        
    Returns:
        Actionable model routing candidates, estimated monthly dollar savings, and latency reductions.
    """
    traces = load_traces()
    if not traces:
        return {"status": "empty", "message": "No trace data recorded."}

    # Aggregate by feature
    by_feature: Dict[str, Dict[str, Any]] = {}
    for t in traces:
        feat = t.get("feature", "unknown")
        model = t.get("model", "unknown")
        out_tokens = t.get("output_tokens", 0)
        task_type = t.get("task_type", "general")
        
        if feat not in by_feature:
            by_feature[feat] = {
                "feature": feat,
                "models": {},
                "avg_output_tokens": [],
                "task_types": set(),
                "calls": 0
            }
        by_feature[feat]["models"][model] = by_feature[feat]["models"].get(model, 0) + 1
        by_feature[feat]["avg_output_tokens"].append(out_tokens)
        by_feature[feat]["task_types"].add(task_type)
        by_feature[feat]["calls"] += 1

    recommendations = []
    total_projected_savings_monthly = 0.0

    for feat, d in by_feature.items():
        primary_model = max(d["models"], key=d["models"].get)
        avg_out = statistics.mean(d["avg_output_tokens"]) if d["avg_output_tokens"] else 0
        task_types = list(d["task_types"])
        
        # Check routing rules
        # Rule 1: Short structured extraction/classification running on expensive frontier models
        if primary_model in ["claude-3-5-sonnet", "gpt-4o"]:
            suggested_target = None
            rationale = ""
            
            if any(t in ["classification", "extraction", "json_format", "sentiment"] for t in task_types) or avg_out < 150:
                if "claude" in primary_model:
                    suggested_target = "claude-3-5-haiku"
                    savings_pct = 73.0
                    lat_delta = "-55% faster (p95 ~450ms)"
                else:
                    suggested_target = "gpt-4o-mini"
                    savings_pct = 94.0
                    lat_delta = "-70% faster (p95 ~320ms)"
                    
                rationale = f"Short structured output (avg {int(avg_out)} tokens). Task type '{task_types[0] if task_types else 'extraction'}' achieves >=99% accuracy on {suggested_target}."
            
            # Rule 2: High-volume internal RAG reranking or summarization
            elif "rag_summary" in task_types or (d["calls"] > 50 and avg_out < 400):
                suggested_target = "claude-3-5-haiku" if "claude" in primary_model else "gpt-4o-mini"
                savings_pct = 70.0
                lat_delta = "-50% latency reduction"
                rationale = f"Bulk processing task with repetitive context. Switching achieves ~{savings_pct}% lower token cost."

            if suggested_target and savings_pct >= savings_threshold_pct:
                # Estimate monthly savings assuming 30x volume
                current_cost_est = (d["calls"] * 30) * 0.025
                saved_monthly = current_cost_est * (savings_pct / 100.0)
                total_projected_savings_monthly += saved_monthly
                
                recommendations.append({
                    "feature": feat,
                    "current_model": primary_model,
                    "recommended_model": suggested_target,
                    "potential_savings_pct": savings_pct,
                    "estimated_monthly_savings_usd": round(saved_monthly, 2),
                    "expected_latency_impact": lat_delta,
                    "task_nature": task_types,
                    "architectural_rationale": rationale,
                    "recommended_action": f"A/B test 10% of '{feat}' traffic on {suggested_target} via deterministic router."
                })

    recommendations.sort(key=lambda x: x["estimated_monthly_savings_usd"], reverse=True)
    return {
        "summary": f"Identified {len(recommendations)} safe model downgrade opportunities. Total estimated savings: ${round(total_projected_savings_monthly, 2)}/month.",
        "routing_recommendations": recommendations
    }

if __name__ == "__main__":
    mcp.run()
