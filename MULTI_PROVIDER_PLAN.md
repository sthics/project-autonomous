# 🌐 Multi-Provider LLM Strategy (Phase 7)

> **Status**: Planned — implement after core system is running  
> **Notion Page**: [Multi-provider LLM strategy](https://www.notion.so/32e04e7225c481479270f5ee38b6e39f)

## Overview

A hybrid multi-provider architecture that routes tasks to the best model for the job, with automatic failover and parallel execution across providers. The stack is:

```
Orchestrator → Provider Router → LiteLLM Proxy → Multiple APIs
```

## Three Layered Strategies

### Strategy 1 — Specialization Routing
Each task type gets routed to the model that's best at it:
- **Claude** → Coding, complex reasoning, architecture decisions
- **Gemini** → Web search, research (native Google Search grounding)
- **GPT** → Structured output, copywriting
- **DeepSeek/Ollama** → Cheap routine tasks (classification, summarization)

### Strategy 2 — Automatic Failover
When one provider hits rate limits, is down, or budget runs out, requests cascade to the next provider. LiteLLM handles this natively with fallback chains. No code changes needed — the proxy handles it.

### Strategy 3 — Parallel Execution
Different agents run on different providers simultaneously:
- Idea Generator → Gemini (great at search)
- Code Builder → Claude (best at code)
- Marketing Agent → GPT (solid at copywriting)

If any provider rate-limits, the proxy falls back transparently.

## Architecture

```
You (nightly review)
    ↓
Primary Overseer Agent ←→ Skill Router ←→ Token Monitor
    ↓                         ↓
Provider Router ────────→ LiteLLM Proxy (localhost:4000)
    ↓                         ↓
┌───────────┬──────────────┬───────────┐
│ Anthropic │   Google     │  OpenAI   │
│ (Claude)  │  (Gemini)    │  (GPT)    │
├───────────┼──────────────┼───────────┤
│ coding    │  research    │ copywrite │
│ architect │  web search  │ structure │
└───────────┴──────────────┴───────────┘
         ↓           ↓          ↓
    DeepSeek / Ollama (cheap fallback)
```

## Provider Routing Config

Defined in `config.yaml` under `provider_routing`:

```yaml
provider_routing:
  coding:
    primary: claude-sonnet-4-6
    fallback: [gpt-4o, deepseek-coder-v3]
  research:
    primary: gemini-2.5-flash
    fallback: [claude-sonnet-4-6, gpt-4o]
  copywriting:
    primary: gpt-4o
    fallback: [claude-sonnet-4-6, gemini-2.5-flash]
  classification:
    primary: deepseek-v3
    fallback: [claude-haiku, gpt-4o-mini]
  default:
    primary: claude-sonnet-4-6
    fallback: [gpt-4o, gemini-2.5-flash]
```

## Per-Provider Budgets

```yaml
provider_budgets:
  anthropic:
    monthly_limit_usd: 50.00
  google:
    monthly_limit_usd: 30.00
  openai:
    monthly_limit_usd: 20.00
  deepseek:
    monthly_limit_usd: 10.00
```

## LiteLLM Proxy Setup

Runs as a Docker container on `localhost:4000`:

```bash
docker run -d \
  --name litellm-proxy \
  -p 4000:4000 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e GOOGLE_API_KEY=$GOOGLE_API_KEY \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $(pwd)/litellm_config.yaml:/app/config.yaml \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml
```

All agents send requests to `http://localhost:4000` using the standard OpenAI chat completions format. LiteLLM translates to each provider's API.

## The Claude Agent SDK Question

The Claude Agent SDK provides the full agent loop (bash, file editing, git, context management) — but it's **Claude-only**. The hybrid approach:

| Agent | Engine | Reason |
|-------|--------|--------|
| Code Builder | Claude Agent SDK | Needs full agent loop (bash, edit, git) |
| Idea Generator | LiteLLM completion | Mostly "search + write text" — any model works |
| Marketing | LiteLLM completion | Mostly "search + write text" — any model works |
| Overseer | Claude Agent SDK | Complex orchestration, subagent delegation |

**Alternative**: Use [GoClaw](https://github.com/goclaw/goclaw) for a unified multi-provider agent framework with 20+ providers, agent teams, and inter-agent delegation.

## Implementation Steps

1. Set up LiteLLM proxy via Docker with API keys for all providers.
2. Create `provider_router.py` module with config-driven task→model mapping.
3. Add `provider_routing` and `provider_budgets` sections to `config.yaml`.
4. Update `orchestrator.py` to route non-SDK agents through LiteLLM completions.
5. Refactor idea-generator and marketing agents to use plain async LiteLLM calls.
6. Add per-provider budget tracking to `token_tracker.py`.
7. Test failover by simulating rate limits.
8. Document the LiteLLM Docker setup in `README.md`.

## Key Decision

> **Build this AFTER the core system (Phases 1–6) is running.** The current single-provider (Claude) setup works fine for development. Multi-provider adds resilience and cost optimization but is not a blocker.
