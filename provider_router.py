#!/usr/bin/env python3
"""
Provider Router — Multi-Provider LLM Routing (Phase 7)
=======================================================
Routes tasks to the optimal LLM provider based on task type,
with automatic failover when providers hit rate limits or budget caps.

Uses LiteLLM proxy at localhost:4000 as the unified API gateway.

Usage:
    router = ProviderRouter(config)
    model = router.resolve("coding")        # → "claude-sonnet-4-6"
    model = router.resolve("research")      # → "gemini-2.5-flash"
    model = router.resolve("copywriting")   # → "gpt-4o"
"""

import datetime
import json
from pathlib import Path


# Default routing table — overridden by config.yaml
DEFAULT_ROUTING = {
    "coding": {
        "primary": "claude-sonnet-4-6",
        "fallback": ["gpt-4o", "deepseek-coder-v3"],
    },
    "research": {
        "primary": "gemini-2.5-flash",
        "fallback": ["claude-sonnet-4-6", "gpt-4o"],
    },
    "copywriting": {
        "primary": "gpt-4o",
        "fallback": ["claude-sonnet-4-6", "gemini-2.5-flash"],
    },
    "classification": {
        "primary": "deepseek-v3",
        "fallback": ["claude-haiku", "gpt-4o-mini"],
    },
    "default": {
        "primary": "claude-sonnet-4-6",
        "fallback": ["gpt-4o", "gemini-2.5-flash"],
    },
}

# Map model prefixes to provider names for budget tracking
MODEL_TO_PROVIDER = {
    "claude": "anthropic",
    "gpt": "openai",
    "gemini": "google",
    "deepseek": "deepseek",
    "ollama": "ollama",
}

# Default per-provider monthly budgets (USD)
DEFAULT_BUDGETS = {
    "anthropic": 50.00,
    "google": 30.00,
    "openai": 20.00,
    "deepseek": 10.00,
    "ollama": 0.00,  # self-hosted, free
}


class ProviderRouter:
    """Routes tasks to the best LLM provider with fallback support."""

    def __init__(self, config: dict, log_dir: str = "logs"):
        routing_config = config.get("provider_routing", {})
        budget_config = config.get("provider_budgets", {})

        # Merge config over defaults
        self.routing = {**DEFAULT_ROUTING, **routing_config}
        self.budgets = {**DEFAULT_BUDGETS}
        for provider, settings in budget_config.items():
            if isinstance(settings, dict):
                self.budgets[provider] = settings.get("monthly_limit_usd", DEFAULT_BUDGETS.get(provider, 0))
            else:
                self.budgets[provider] = settings

        # Track per-provider spend
        self.spend: dict[str, float] = {provider: 0.0 for provider in self.budgets}

        # Log directory for provider usage
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Load existing spend from log if available
        self._load_spend()

    def resolve(self, task_type: str) -> str:
        """
        Resolve the best model for a given task type.
        Falls back through the chain if the primary provider is over budget.

        Args:
            task_type: One of 'coding', 'research', 'copywriting', 'classification', 'default'

        Returns:
            Model identifier string (e.g., 'claude-sonnet-4-6')
        """
        route = self.routing.get(task_type, self.routing["default"])
        primary = route["primary"]
        fallbacks = route.get("fallback", [])

        # Try primary first
        if not self._is_over_budget(primary):
            return primary

        # Try fallbacks in order
        for model in fallbacks:
            if not self._is_over_budget(model):
                print(f"[ProviderRouter] {task_type}: primary '{primary}' over budget, "
                      f"falling back to '{model}'")
                return model

        # All over budget — return primary anyway with a warning
        print(f"[ProviderRouter] WARNING: All providers for '{task_type}' are over budget. "
              f"Using primary '{primary}' anyway.")
        return primary

    def get_provider(self, model: str) -> str:
        """Get the provider name for a given model."""
        for prefix, provider in MODEL_TO_PROVIDER.items():
            if model.startswith(prefix):
                return provider
        return "unknown"

    def record_cost(self, model: str, cost_usd: float):
        """Record cost against a provider's budget."""
        provider = self.get_provider(model)
        self.spend[provider] = self.spend.get(provider, 0.0) + cost_usd
        self._save_spend()

    def get_budget_status(self) -> dict:
        """Get current budget status for all providers."""
        status = {}
        for provider, limit in self.budgets.items():
            spent = self.spend.get(provider, 0.0)
            status[provider] = {
                "limit_usd": limit,
                "spent_usd": round(spent, 4),
                "remaining_usd": round(limit - spent, 4),
                "utilization_pct": round((spent / limit * 100), 1) if limit > 0 else 0,
            }
        return status

    def _is_over_budget(self, model: str) -> bool:
        """Check if a model's provider has exceeded its budget."""
        provider = self.get_provider(model)
        limit = self.budgets.get(provider, 0)
        if limit <= 0:
            return False  # No budget set = unlimited (e.g., Ollama)
        spent = self.spend.get(provider, 0.0)
        return spent >= limit

    def _load_spend(self):
        """Load provider spend from log file."""
        spend_file = self.log_dir / "provider_spend.json"
        if spend_file.exists():
            try:
                with open(spend_file) as f:
                    data = json.load(f)
                # Only load if from the current month
                if data.get("month") == datetime.datetime.now().strftime("%Y-%m"):
                    self.spend = data.get("spend", self.spend)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_spend(self):
        """Persist provider spend to log file."""
        spend_file = self.log_dir / "provider_spend.json"
        data = {
            "month": datetime.datetime.now().strftime("%Y-%m"),
            "spend": self.spend,
            "updated_at": datetime.datetime.now().isoformat(),
        }
        with open(spend_file, "w") as f:
            json.dump(data, f, indent=2)

    def __repr__(self) -> str:
        status = self.get_budget_status()
        lines = ["ProviderRouter:"]
        for provider, s in status.items():
            lines.append(f"  {provider}: ${s['spent_usd']:.2f} / ${s['limit_usd']:.2f} "
                         f"({s['utilization_pct']:.0f}%)")
        return "\n".join(lines)
