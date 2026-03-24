#!/usr/bin/env python3
"""
Project Autonomous — Orchestrator
==================================
The primary overseer agent. Coordinates subagents, manages the work cycle,
tracks budgets, and writes reviews to Notion.

Usage:
    python orchestrator.py                    # Interactive mode
    python orchestrator.py --cycle            # Run one autonomous cycle
    python orchestrator.py --task "Build X"   # Run a specific task
    python orchestrator.py --ideas            # Generate new ideas only
    python orchestrator.py --summary          # Generate daily summary only
"""

import argparse
import asyncio
import datetime
import json
import sys
from pathlib import Path

import yaml

# These imports will work once claude-agent-sdk is installed
# pip install claude-agent-sdk
try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        TextBlock,
    )

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("[Orchestrator] Claude Agent SDK not installed.")
    print("  Run: pip install claude-agent-sdk")
    print("  Continuing in dry-run mode...\n")

from skill_router import SkillRouter
from alerts import AlertManager
from token_tracker import TokenTracker

# Agent-specific tool restrictions (match .claude/agents/*.md definitions)
AGENT_ALLOWED_TOOLS: dict[str, list[str]] = {
    "overseer": ["Read", "Write", "Edit", "Bash", "Glob", "Agent", "WebSearch"],
    "idea-generator": ["Read", "Write", "WebSearch"],
    "code-builder": ["Read", "Write", "Edit", "Bash", "Glob"],
    "marketing": ["Read", "Write", "WebSearch"],
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config(path: str = "config.yaml") -> dict:
    """Load configuration from YAML."""
    config_path = Path(path)
    if not config_path.exists():
        print(f"[Orchestrator] Config not found at {path}, using defaults")
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

OVERSEER_SYSTEM_PROMPT = """You are the Primary Overseer of Project Autonomous — an autonomous AI agent system
that builds products for niche industries.

## Your Role
You are the central coordinator. You decide what gets built, assign work to subagents,
and ensure quality. Think like a senior engineering manager who also has great product taste.

## Core Directives
1. NEVER BUILD GENERIC AI SLOP — No todo apps, chatbots, AI wrappers, or anything with 10+ competitors.
   Find genuine gaps in niche industries: construction, logistics, agriculture, healthcare admin,
   legal ops, marine, HVAC, plumbing, pest control, landscaping, property management, etc.

2. ALWAYS DOCUMENT — Every decision, insight, and outcome goes to Notion review pages.

3. ESCALATE WHEN UNCERTAIN — If a decision could cost >$5, affect users, or is architecturally
   significant, write it to the review page for human decision.

4. SHIP FAST — MVPs over perfection. Get something working, then iterate.

## Available Subagents
- **idea-generator**: Researches niche industries, produces PRDs. Use for ideation.
- **code-builder**: Full-stack dev that builds MVPs from PRDs. Use for implementation.
- **marketing**: Finds customers, drafts outreach. Use for go-to-market prep.

## Your Decision Loop
1. Check Notion for any pending human decisions from last review
2. If no active project: spawn idea-generator for new ideas
3. Evaluate ideas against niche criteria
4. Present top ideas as PRDs for human review
5. For approved ideas: spawn code-builder + marketing in parallel
6. Monitor progress, track token budgets
7. Write cycle summary to Notion
8. Alert human if anything needs attention

## Safety Rules
- Never delete files (move to dump/ instead)
- Never exceed token budgets without approval
- Never send real outreach without human approval
- Never push to production without human review
- Stay within ~/project-autonomous/ and /tmp/
"""


# ---------------------------------------------------------------------------
# Orchestrator Core
# ---------------------------------------------------------------------------

class Orchestrator:
    def __init__(self, config: dict):
        self.config = config
        self.project_root = Path(__file__).parent

        # Initialize components
        self.skill_router = SkillRouter(str(self.project_root))
        self.alert_manager = AlertManager(
            config.get("notifications", {}),
            log_dir=str(self.project_root / "logs"),
        )
        self.token_tracker = TokenTracker(
            config.get("budgets", {}),
            alert_manager=self.alert_manager,
            log_dir=str(self.project_root / "logs"),
        )

        # Ensure required directories exist
        for d in ["projects", "projects/ideas", "dump", "logs"]:
            (self.project_root / d).mkdir(parents=True, exist_ok=True)

        self.model = config.get("overseer", {}).get("model", "claude-sonnet-4-6")
        self.subagent_model = config.get("overseer", {}).get("subagent_model", "claude-sonnet-4-6")

        print(f"[Orchestrator] Initialized")
        print(f"  Model: {self.model}")
        print(f"  Project root: {self.project_root}")
        print(f"  Skills loaded: {len(self.skill_router.skills)}")

    async def run_agent(
        self,
        prompt: str,
        task_id: str = "default",
        agent_name: str = "overseer",
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int = 50,
    ) -> str:
        """
        Run a single agent query with budget tracking and skill routing.
        Returns the agent's final text output.
        """
        if not SDK_AVAILABLE:
            print(f"\n[DRY RUN] Agent: {agent_name}")
            print(f"[DRY RUN] Task: {task_id}")
            print(f"[DRY RUN] Prompt: {prompt[:200]}...")
            return "[DRY RUN] SDK not available — install claude-agent-sdk to run for real."

        # Skill routing: inject relevant skills into prompt
        skill_context = self.skill_router.route(prompt)
        if skill_context:
            print(f"[Orchestrator] Skill router injected context for task: {task_id}")

        # Build the full system prompt
        full_system = (system_prompt or OVERSEER_SYSTEM_PROMPT) + skill_context

        # Start tracking
        self.token_tracker.start_task(task_id, agent_name, self.model)

        # Build options — use agent-specific tool restrictions if not overridden
        effective_tools = allowed_tools or AGENT_ALLOWED_TOOLS.get(
            agent_name, ["Read", "Write", "Edit", "Bash", "Glob", "Agent", "WebSearch"]
        )
        options = ClaudeAgentOptions(
            system_prompt=full_system,
            max_turns=max_turns,
            allowed_tools=effective_tools,
        )

        # Run the agent loop
        output_parts = []
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            output_parts.append(block.text)
                            print(block.text, end="", flush=True)

                elif isinstance(message, ResultMessage):
                    # Track token usage from the result
                    usage = getattr(message, "usage", None)
                    if usage:
                        status = self.token_tracker.record_usage(
                            task_id,
                            input_tokens=getattr(usage, "input_tokens", 0),
                            output_tokens=getattr(usage, "output_tokens", 0),
                        )
                        if not status["ok"] and status.get("action") == "stop":
                            print(f"\n[Orchestrator] BUDGET STOP: {status['reason']}")
                            break

        except Exception as e:
            error_msg = f"Agent '{agent_name}' failed on task '{task_id}': {e}"
            self.alert_manager.critical("Agent Error", error_msg)
            output_parts.append(f"\n\nERROR: {error_msg}")

        # End tracking
        task_usage = self.token_tracker.end_task(task_id)
        if task_usage:
            print(f"\n[Orchestrator] Task '{task_id}' used {task_usage.total_tokens:,} tokens "
                  f"(~${task_usage.estimated_cost_usd:.3f})")

        return "\n".join(output_parts)

    async def run_cycle(self):
        """Run one full autonomous cycle."""
        print("=" * 60)
        print(f" Project Autonomous — Cycle Start")
        print(f" {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        self.token_tracker.reset_cycle()

        # Step 1: Check for pending human decisions
        print("\n[Step 1] Checking Notion for pending decisions...")
        result = await self.run_agent(
            prompt=(
                "Check the Notion master hub page for any pending human decisions "
                "or approvals from the last review cycle. Summarize what needs attention "
                "and what has been approved. If there are approved ideas or tasks, "
                "list them so we can start working on them."
            ),
            task_id="check-decisions",
            agent_name="overseer",
            max_turns=10,
        )

        # Step 2: Generate ideas if no active project
        print("\n\n[Step 2] Checking for active projects or generating ideas...")
        result = await self.run_agent(
            prompt=(
                "Check projects/ directory for any active projects. "
                "If there are none or all are completed, use the idea-generator agent "
                "to research 3 niche industry product ideas. Save PRDs to projects/ideas/. "
                "Focus on industries where manual processes still dominate: "
                "construction permits, HVAC scheduling, fleet maintenance, etc."
            ),
            task_id="ideation",
            agent_name="overseer",
            max_turns=30,
        )

        # Step 3: Write cycle summary
        print("\n\n[Step 3] Writing cycle summary...")
        summary = self.token_tracker.get_daily_summary()
        await self.run_agent(
            prompt=(
                f"Write a cycle summary to Notion. Here's the token usage data:\n"
                f"{json.dumps(summary, indent=2)}\n\n"
                "Create a summary that includes:\n"
                "- What was accomplished this cycle\n"
                "- Token usage breakdown\n"
                "- What needs human attention\n"
                "- Recommended next steps"
            ),
            task_id="summary",
            agent_name="overseer",
            max_turns=10,
        )

        # Notify
        self.alert_manager.action_needed(
            "Cycle Complete",
            f"Used {summary['total_tokens']:,} tokens (~${summary['estimated_cost_usd']:.2f}). "
            "Review summary in Notion."
        )

        print("\n" + "=" * 60)
        print(" Cycle Complete")
        print("=" * 60)

    async def run_task(self, task_description: str):
        """Run a specific task described in natural language."""
        print(f"[Orchestrator] Running task: {task_description}\n")
        result = await self.run_agent(
            prompt=task_description,
            task_id=f"task-{datetime.datetime.now().strftime('%H%M%S')}",
            agent_name="overseer",
        )
        return result

    async def generate_ideas(self):
        """Run idea generation only."""
        print("[Orchestrator] Generating new product ideas...\n")
        result = await self.run_agent(
            prompt=(
                "Use the idea-generator agent to research and generate 5 niche industry "
                "product ideas. For each idea, create a full PRD and save it to projects/ideas/. "
                "Focus on underserved industries where existing software is outdated or nonexistent. "
                "After generating ideas, rank them by feasibility and market potential."
            ),
            task_id="idea-gen",
            agent_name="overseer",
            max_turns=40,
        )
        return result

    async def generate_summary(self):
        """Generate daily summary only."""
        summary = self.token_tracker.get_daily_summary()
        print(f"[Orchestrator] Daily summary:\n{json.dumps(summary, indent=2)}")

        if SDK_AVAILABLE:
            await self.run_agent(
                prompt=(
                    f"Generate a daily summary and write it to Notion. "
                    f"Token data: {json.dumps(summary, indent=2)}\n"
                    "Review all activity in projects/ and logs/ to compile the summary."
                ),
                task_id="daily-summary",
                agent_name="overseer",
                max_turns=15,
            )

        return summary


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Project Autonomous — Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator.py                    # Interactive mode
  python orchestrator.py --cycle            # Run one autonomous cycle
  python orchestrator.py --task "Build X"   # Run a specific task
  python orchestrator.py --ideas            # Generate new ideas only
  python orchestrator.py --summary          # Generate daily summary
        """,
    )
    parser.add_argument("--cycle", action="store_true", help="Run one autonomous cycle")
    parser.add_argument("--task", type=str, help="Run a specific task")
    parser.add_argument("--ideas", action="store_true", help="Generate new product ideas")
    parser.add_argument("--summary", action="store_true", help="Generate daily summary")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without executing")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Honor --dry-run flag
    global SDK_AVAILABLE
    if args.dry_run:
        SDK_AVAILABLE = False
        print("[Orchestrator] Dry-run mode enabled — no SDK calls will be made.\n")

    # Initialize orchestrator
    orchestrator = Orchestrator(config)

    # Route to appropriate command
    if args.cycle:
        asyncio.run(orchestrator.run_cycle())
    elif args.task:
        asyncio.run(orchestrator.run_task(args.task))
    elif args.ideas:
        asyncio.run(orchestrator.generate_ideas())
    elif args.summary:
        asyncio.run(orchestrator.generate_summary())
    else:
        # Interactive mode
        print("\n" + "=" * 60)
        print(" Project Autonomous — Interactive Mode")
        print("=" * 60)
        print("Type a task or command. Special commands:")
        print("  /cycle   — Run a full autonomous cycle")
        print("  /ideas   — Generate new product ideas")
        print("  /summary — Generate daily summary")
        print("  /status  — Show token usage status")
        print("  /quit    — Exit\n")

        while True:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input:
                continue

            if user_input == "/quit":
                break
            elif user_input == "/cycle":
                asyncio.run(orchestrator.run_cycle())
            elif user_input == "/ideas":
                asyncio.run(orchestrator.generate_ideas())
            elif user_input == "/summary":
                asyncio.run(orchestrator.generate_summary())
            elif user_input == "/status":
                summary = orchestrator.token_tracker.get_daily_summary()
                print(json.dumps(summary, indent=2))
            else:
                asyncio.run(orchestrator.run_task(user_input))


if __name__ == "__main__":
    main()
