# 🤖 Project Autonomous

An autonomous AI agent system that generates product ideas for niche industries, builds them, markets them, and iterates — all with minimal human oversight.

## Quick Start

```bash
# 1. Clone or navigate to the project
cd ~/project-autonomous

# 2. Set up Python environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 5. Run in interactive mode
python orchestrator.py

# Or run a full autonomous cycle
python orchestrator.py --cycle
```

## Commands

```bash
python orchestrator.py                    # Interactive mode (REPL)
python orchestrator.py --cycle            # Run one autonomous cycle
python orchestrator.py --task "Build X"   # Run a specific task
python orchestrator.py --ideas            # Generate new ideas only
python orchestrator.py --summary          # Daily token/activity summary
```

### Interactive Commands
Once in interactive mode:
- `/cycle`   — Run a full autonomous cycle
- `/ideas`   — Generate new product ideas
- `/summary` — Generate daily summary
- `/status`  — Show token usage
- `/quit`    — Exit

## Architecture

```
You (nightly review)
    ↓
Primary Overseer Agent ←→ Skill Router ←→ Token Monitor
    ↓           ↓           ↓
Idea Gen    Code Builder   Marketing
    ↓           ↓           ↓
   PRDs      Projects     Outreach
    ↓           ↓           ↓
         Notion Review Pages
              ↓
         Phone Alerts
```

## Directory Structure

```
project-autonomous/
├── orchestrator.py          # Main entry point
├── config.yaml              # Configuration
├── skill_router.py          # Auto-selects skills per task
├── alerts.py                # Phone + macOS notifications
├── token_tracker.py         # Budget monitoring
├── requirements.txt         # Python dependencies
├── .claude/
│   ├── CLAUDE.md            # Project context for all agents
│   ├── settings.json        # Claude Code + Agent Teams config
│   └── agents/              # Subagent definitions
│       ├── idea-generator.md
│       ├── code-builder.md
│       └── marketing.md
├── skills/
│   └── registry.json        # Skill index for the router
├── projects/                # Generated project workspaces
│   └── ideas/               # PRDs from idea generator
├── dump/                    # Never-delete archive
└── logs/                    # Execution logs, token usage
```

## Configuration

Edit `config.yaml` to customize:
- Token budgets and limits
- Notification service (ntfy/pushover/telegram)
- Model selection
- Quiet hours for alerts
- Auto-approve settings

## Notion Integration

The system writes all reviews to your Notion workspace:
- **Master Hub**: [Project Autonomous](https://www.notion.so/32d04e7225c4816e8c94d25c768ab046)
- Marketing review, Code review, Ideas review pages
- Daily summaries with token breakdowns

## Safety Rules

1. **Never deletes data** — moves to `dump/` instead
2. **Token budgets** — hard stops when limits are reached
3. **Human approval required** for outreach and production deploys
4. **Directory sandboxing** — agents stay within project root
5. **All activity logged** to Notion and local files
