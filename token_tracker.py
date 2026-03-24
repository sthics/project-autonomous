"""
Token Budget Tracker — monitors API usage per task, per agent, and globally.

Integrates with the Alert Manager to send warnings and hard stops.
Logs all usage to a JSONL file for daily summaries.
"""

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path


# Per-model pricing: (input $/M tokens, output $/M tokens)
MODEL_PRICING = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}
DEFAULT_PRICING = (3.0, 15.0)  # Fallback to Sonnet pricing


@dataclass
class TaskUsage:
    """Token usage for a single task."""
    task_id: str
    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    started_at: str = ""
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Cost estimate based on model-specific pricing."""
        input_rate, output_rate = MODEL_PRICING.get(self.model, DEFAULT_PRICING)
        return (self.input_tokens * input_rate / 1_000_000) + (self.output_tokens * output_rate / 1_000_000)


class TokenTracker:
    def __init__(self, budgets: dict, alert_manager=None, log_dir: str = "logs"):
        self.budgets = budgets
        self.alert_manager = alert_manager
        self.log_path = Path(log_dir) / "token_usage.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Current cycle tracking
        self.cycle_tokens = 0
        self.daily_tokens = 0
        self.daily_reset_date = datetime.date.today()
        self.active_tasks: dict[str, TaskUsage] = {}
        self.completed_tasks: list[TaskUsage] = []

        # Load today's existing usage from log
        self._load_daily_usage()

    def _load_daily_usage(self):
        """Load today's token usage from the log file."""
        if not self.log_path.exists():
            return

        today = datetime.date.today().isoformat()
        try:
            with open(self.log_path) as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get("timestamp", "").startswith(today):
                        self.daily_tokens += entry.get("input_tokens", 0) + entry.get("output_tokens", 0)
        except Exception:
            pass

    def _check_daily_reset(self):
        """Reset daily counter on new day."""
        today = datetime.date.today()
        if today != self.daily_reset_date:
            self.daily_tokens = 0
            self.daily_reset_date = today
            self.completed_tasks.clear()

    def start_task(self, task_id: str, agent: str, model: str = ""):
        """Begin tracking a new task."""
        self.active_tasks[task_id] = TaskUsage(
            task_id=task_id,
            agent=agent,
            model=model,
            started_at=datetime.datetime.now().isoformat(),
        )

    def record_usage(self, task_id: str, input_tokens: int, output_tokens: int) -> dict:
        """
        Record token usage for a task. Returns status dict:
        {"ok": True} or {"ok": False, "reason": "...", "action": "warn"|"stop"}
        """
        self._check_daily_reset()

        task = self.active_tasks.get(task_id)
        if not task:
            return {"ok": True, "warning": "Unknown task, no tracking applied"}

        task.input_tokens += input_tokens
        task.output_tokens += output_tokens
        task.calls += 1

        total = input_tokens + output_tokens
        self.cycle_tokens += total
        self.daily_tokens += total

        # Log the call
        self._log_usage(task_id, task.agent, input_tokens, output_tokens, task.model)

        # Check budgets
        return self._check_budgets(task)

    def _check_budgets(self, task: TaskUsage) -> dict:
        """Check all budget levels and return status."""
        warning_threshold = self.budgets.get("warning_threshold", 0.8)
        hard_stop = self.budgets.get("hard_stop_threshold", 1.0)

        # Per-task limit
        task_limit = self.budgets.get("per_subagent_task_limit", 100_000)
        task_ratio = task.total_tokens / task_limit if task_limit else 0

        if task_ratio >= hard_stop:
            msg = f"Task '{task.task_id}' ({task.agent}) hit token limit: {task.total_tokens:,}/{task_limit:,}"
            if self.alert_manager:
                self.alert_manager.critical("Token Hard Stop", msg)
            return {"ok": False, "reason": msg, "action": "stop"}

        if task_ratio >= warning_threshold:
            msg = f"Task '{task.task_id}' at {task_ratio:.0%} of budget ({task.total_tokens:,}/{task_limit:,})"
            if self.alert_manager:
                self.alert_manager.action_needed("Token Warning", msg)
            return {"ok": True, "warning": msg}

        # Per-cycle limit
        cycle_limit = self.budgets.get("per_cycle_limit", 500_000)
        cycle_ratio = self.cycle_tokens / cycle_limit if cycle_limit else 0

        if cycle_ratio >= hard_stop:
            msg = f"Cycle token limit reached: {self.cycle_tokens:,}/{cycle_limit:,}"
            if self.alert_manager:
                self.alert_manager.critical("Cycle Budget Exhausted", msg)
            return {"ok": False, "reason": msg, "action": "stop"}

        # Daily limit
        daily_limit = self.budgets.get("global_daily_limit", 2_000_000)
        daily_ratio = self.daily_tokens / daily_limit if daily_limit else 0

        if daily_ratio >= hard_stop:
            msg = f"Daily token limit reached: {self.daily_tokens:,}/{daily_limit:,}"
            if self.alert_manager:
                self.alert_manager.critical("Daily Budget Exhausted", msg)
            return {"ok": False, "reason": msg, "action": "stop"}

        if daily_ratio >= warning_threshold:
            msg = f"Daily usage at {daily_ratio:.0%}: {self.daily_tokens:,}/{daily_limit:,}"
            if self.alert_manager:
                self.alert_manager.action_needed("Daily Budget Warning", msg)

        return {"ok": True}

    def end_task(self, task_id: str) -> TaskUsage | None:
        """End tracking for a task, move to completed list, and return its final usage."""
        task = self.active_tasks.pop(task_id, None)
        if task:
            self.completed_tasks.append(task)
        return task

    def _log_usage(self, task_id: str, agent: str, input_tokens: int, output_tokens: int, model: str):
        """Append usage entry to log file."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "task_id": task_id,
            "agent": agent,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
            "cycle_total": self.cycle_tokens,
            "daily_total": self.daily_tokens,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_daily_summary(self) -> dict:
        """Generate a summary of today's token usage by agent (active + completed)."""
        summary = {
            "date": datetime.date.today().isoformat(),
            "total_tokens": self.daily_tokens,
            "estimated_cost_usd": 0.0,
            "by_agent": {},
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
        }

        all_tasks = list(self.active_tasks.values()) + self.completed_tasks
        for task in all_tasks:
            agent = task.agent
            if agent not in summary["by_agent"]:
                summary["by_agent"][agent] = {"tokens": 0, "cost_usd": 0.0, "tasks": 0}
            summary["by_agent"][agent]["tokens"] += task.total_tokens
            summary["by_agent"][agent]["cost_usd"] += task.estimated_cost_usd
            summary["by_agent"][agent]["tasks"] += 1

        summary["estimated_cost_usd"] = sum(
            a["cost_usd"] for a in summary["by_agent"].values()
        )

        return summary

    def reset_cycle(self):
        """Reset cycle token counter (call between overseer cycles)."""
        self.cycle_tokens = 0
