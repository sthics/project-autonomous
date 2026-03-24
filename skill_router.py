"""
Skill Router — automatically selects the best skill(s) for any given task.

Sits between the overseer and every prompt. Reads the task description,
matches against a registry of skill .md files, and returns the skill
content to inject into the agent's system prompt.
"""

import json
import os
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SkillMatch:
    """A matched skill with relevance score."""
    skill_id: str
    name: str
    file_path: str
    score: float
    matched_triggers: list[str]


class SkillRouter:
    def __init__(self, project_root: str, registry_path: str = "skills/registry.json"):
        self.project_root = Path(project_root)
        self.registry_path = self.project_root / registry_path
        self.skills = []
        self._load_registry()

    def _load_registry(self):
        """Load the skill registry from JSON."""
        if not self.registry_path.exists():
            print(f"[SkillRouter] Warning: Registry not found at {self.registry_path}")
            return
        with open(self.registry_path) as f:
            data = json.load(f)
            self.skills = data.get("skills", [])
        print(f"[SkillRouter] Loaded {len(self.skills)} skills from registry")

    def match(self, task_description: str, max_skills: int = 2) -> list[SkillMatch]:
        """
        Match a task description against the skill registry.
        Returns the top N matching skills, sorted by relevance score.
        """
        task_lower = task_description.lower()
        task_words = set(re.findall(r'\b\w+\b', task_lower))
        matches = []

        for skill in self.skills:
            matched_triggers = []
            score = 0.0

            for trigger in skill["triggers"]:
                trigger_lower = trigger.lower()
                # Exact word match (higher score)
                if trigger_lower in task_words:
                    score += 2.0
                    matched_triggers.append(trigger)
                # Substring match (lower score)
                elif trigger_lower in task_lower:
                    score += 1.0
                    matched_triggers.append(trigger)

            if score > 0:
                matches.append(SkillMatch(
                    skill_id=skill["id"],
                    name=skill["name"],
                    file_path=skill["file"],
                    score=score,
                    matched_triggers=matched_triggers,
                ))

        # Sort by score descending, return top N
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:max_skills]

    def load_skill_content(self, skill_match: SkillMatch) -> str | None:
        """Load the actual .md content of a matched skill."""
        skill_path = self.project_root / skill_match.file_path
        if not skill_path.exists():
            print(f"[SkillRouter] Skill file not found: {skill_path}")
            return None
        return skill_path.read_text()

    def route(self, task_description: str, max_skills: int = 2) -> str:
        """
        Main entry point: match skills and return combined content to inject
        into the agent's system prompt.
        """
        matches = self.match(task_description, max_skills)

        if not matches:
            return ""

        sections = []
        for m in matches:
            content = self.load_skill_content(m)
            if content:
                sections.append(
                    f"--- SKILL: {m.name} (matched: {', '.join(m.matched_triggers)}) ---\n"
                    f"{content}\n"
                    f"--- END SKILL ---"
                )
                print(f"[SkillRouter] Injecting skill: {m.name} (score={m.score}, triggers={m.matched_triggers})")

        if not sections:
            self.log_usage(task_description, [])
            return ""

        self.log_usage(task_description, matches)

        return (
            "\n\n# Relevant Skills (auto-selected by skill router)\n"
            "Use these best practices for this task:\n\n"
            + "\n\n".join(sections)
        )

    def log_usage(self, task_description: str, matches: list[SkillMatch], log_dir: str = "logs"):
        """Log skill routing decisions for later analysis."""
        log_path = Path(self.project_root) / log_dir / "skill_router.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        import datetime
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "task_preview": task_description[:200],
            "matched_skills": [
                {"id": m.skill_id, "score": m.score, "triggers": m.matched_triggers}
                for m in matches
            ],
            "no_match": len(matches) == 0,
        }

        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


# Quick self-test
if __name__ == "__main__":
    router = SkillRouter(project_root=".")
    
    test_tasks = [
        "Design the database schema for a permit tracking system",
        "Build a React landing page with a sign-up form",
        "Write cold outreach emails for HVAC companies",
        "Set up Docker deployment with CI/CD",
        "Research the pest control industry market size",
    ]

    for task in test_tasks:
        print(f"\nTask: {task}")
        matches = router.match(task)
        for m in matches:
            print(f"  → {m.name} (score={m.score}, triggers={m.matched_triggers})")
        if not matches:
            print("  → No skills matched")
