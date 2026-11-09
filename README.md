# llm-cost-watch

> **The Model Context Protocol (MCP) server for LLM spend & latency intelligence.**  
> *"Ask Claude why our LLM bill jumped."*

[![MCP 2.x](https://img.shields.io/badge/MCP-2.x%20Ready-blue)](https://modelcontextprotocol.io)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-brightgreen.svg)](https://python.org)
[![TrustMRR Verified](https://img.shields.io/badge/TrustMRR-Startup%20Listing%20($25k)-0052FF.svg)](https://trustmrr.com/startup/leadflow-ai)
[![Gumroad](https://img.shields.io/badge/Gumroad-LeadHunter%20Engine%20($149)-FF90E8.svg)](https://balsarohith.gumroad.com/l/LeadHunter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What is `llm-cost-watch`?

Instead of clicking through complex web dashboards, `llm-cost-watch` lets you ask Claude directly inside **Claude Desktop**, **Claude Code**, or **Antigravity**:

```text
You: "Claude, why did our LLM spend jump 40% this week, and where is our latency bottleneck?"

Claude: [Calls llm-cost-watch: cost_by_feature & slow_calls]
"Your 'knowledge_base_rag' pipeline accounts for 66.1% of total spend ($0.082 across 3 test runs) 
and is driving your p95 latency up to 3,120ms due to uncompressed 7k token context windows.

Meanwhile, 'customer_intent_classifier' is currently routed through GPT-4o for 14-token classification. 
Routing it to GPT-4o-mini will cut that feature's spend by 94% and reduce p95 latency to 320ms."
```

---

## 3 Core MCP Tools

1. **`cost_by_feature(timeframe="7d")`**: Identifies which feature or workflow consumes the largest share of your budget.
2. **`slow_calls(limit=5, min_latency_ms=1200)`**: Pinpoints high-latency outliers (p50, p95, p99) and diagnoses the bottleneck (unbounded prompt payload, recursive tool loops, reasoning stalls).
3. **`routing_suggestions(savings_threshold_pct=20)`**: Analyzes short structured prompts running on expensive frontier models and calculates exact dollar savings from moving to Claude 3.5 Haiku or GPT-4o-mini.

---

## Quick Setup (Under 5 Minutes)

### 1. Install & Clone
```bash
git clone https://github.com/rohith0707/llm-cost-watch.git
cd llm-cost-watch
pip install -r requirements.txt
```

### 2. Connect to Claude Desktop
Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "llm-cost-watch": {
      "command": "python",
      "args": ["-m", "tools.llm-cost-watch.server"]
    }
  }
}
```

### 3. Log Calls in Your Code (One Line)
```python
from logger import watch_llm

@watch_llm(feature="customer_intent_classifier", task_type="classification", model="gpt-4o")
def classify_intent(message: str) -> str:
    # Your normal OpenAI / Anthropic call
    return client.chat.completions.create(...)
```

---

## Test Run
```bash
python test_server.py
```

---

## Commercial Licensing & Architecture Audits
- **Free Core:** Open-source under MIT.
- **Acquisition & IP Rights:** Listed on [TrustMRR: AgentControl & Decision Plane ($25,000 asking price)](https://trustmrr.com/startup/leadflow-ai).
- **Self-Hosted Engine:** Get the production [LeadHunter & Concurrency Kit on Gumroad ($149)](https://balsarohith.gumroad.com/l/LeadHunter).
- **Enterprise SLA & 14-Day Concurrency / Cost Audit ($2,500):** Contact Rohith Balsa (`balsarohith5@gmail.com` | [LinkedIn](https://linkedin.com/in/rohithbalsa)).
