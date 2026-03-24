"""
Alert Manager — sends notifications to phone and macOS.

Supports Ntfy, Pushover, and Telegram backends.
Includes quiet hours, deduplication, and rate limiting.
"""

import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

import requests


class AlertManager:
    def __init__(self, config: dict, log_dir: str = "logs"):
        self.service = config.get("service", "ntfy")
        raw_endpoint = config.get("endpoint", "")
        # Resolve env var references like "${NOTIFY_ENDPOINT}"
        if raw_endpoint.startswith("${") and raw_endpoint.endswith("}"):
            env_key = raw_endpoint[2:-1]
            self.endpoint = os.environ.get(env_key, "")
        else:
            self.endpoint = raw_endpoint
        self.quiet_start = config.get("quiet_hours", {}).get("start", "23:00")
        self.quiet_end = config.get("quiet_hours", {}).get("end", "08:00")
        self.max_daily = config.get("max_daily_alerts", 20)

        self.log_path = Path(log_dir) / "alerts.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._recent_hashes: dict[str, datetime.datetime] = {}
        self._daily_count = 0
        self._daily_reset_date = datetime.date.today()

    def _is_quiet_hours(self) -> bool:
        """Check if current time falls in quiet hours."""
        now = datetime.datetime.now().time()
        start = datetime.time.fromisoformat(self.quiet_start)
        end = datetime.time.fromisoformat(self.quiet_end)

        if start <= end:
            return start <= now <= end
        else:  # Wraps past midnight (e.g. 23:00 to 08:00)
            return now >= start or now <= end

    def _is_duplicate(self, title: str, message: str, window_minutes: int = 5) -> bool:
        """Check if same alert was sent recently."""
        h = hashlib.md5(f"{title}:{message}".encode()).hexdigest()
        now = datetime.datetime.now()

        # Prune entries older than the dedup window
        cutoff = now - datetime.timedelta(minutes=window_minutes)
        self._recent_hashes = {
            k: v for k, v in self._recent_hashes.items() if v > cutoff
        }

        if h in self._recent_hashes:
            return True

        self._recent_hashes[h] = now
        return False

    def _check_daily_limit(self) -> bool:
        """Reset daily counter if new day, check limit."""
        today = datetime.date.today()
        if today != self._daily_reset_date:
            self._daily_count = 0
            self._daily_reset_date = today

        return self._daily_count < self.max_daily

    def _send_phone(self, title: str, message: str, priority: str = "default"):
        """Send phone notification via configured service."""
        try:
            if self.service == "ntfy":
                requests.post(
                    f"https://{self.endpoint}",
                    data=message.encode("utf-8"),
                    headers={
                        "Title": title,
                        "Priority": {"high": "urgent", "normal": "default", "low": "low"}.get(priority, "default"),
                        "Tags": "robot",
                    },
                    timeout=10,
                )
            elif self.service == "pushover":
                # Expects endpoint = "user_key:api_token"
                user_key, api_token = self.endpoint.split(":")
                requests.post(
                    "https://api.pushover.net/1/messages.json",
                    data={
                        "token": api_token,
                        "user": user_key,
                        "title": title,
                        "message": message,
                        "priority": {"high": 1, "normal": 0, "low": -1}.get(priority, 0),
                    },
                    timeout=10,
                )
            elif self.service == "telegram":
                # Expects endpoint = "bot_token:chat_id"
                bot_token, chat_id = self.endpoint.split(":")
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": f"*{title}*\n{message}",
                        "parse_mode": "Markdown",
                    },
                    timeout=10,
                )
        except Exception as e:
            print(f"[AlertManager] Failed to send phone alert: {e}")

    @staticmethod
    def _escape_applescript(s: str) -> str:
        """Escape a string for safe embedding in AppleScript double quotes."""
        return s.replace("\\", "\\\\").replace('"', '\\"')

    def _send_mac(self, title: str, message: str):
        """Send macOS notification via osascript."""
        try:
            safe_msg = self._escape_applescript(message[:200])
            safe_title = self._escape_applescript(title[:100])
            subprocess.run(
                [
                    "osascript", "-e",
                    f'display notification "{safe_msg}" with title "{safe_title}"',
                ],
                timeout=5,
                capture_output=True,
            )
        except Exception:
            pass  # Not on macOS or osascript not available

    def _log_alert(self, level: str, title: str, message: str, sent_phone: bool, sent_mac: bool):
        """Log alert for tracking."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "level": level,
            "title": title,
            "message": message[:200],
            "sent_phone": sent_phone,
            "sent_mac": sent_mac,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def critical(self, title: str, message: str):
        """
        Critical alert — always sends to phone (even in quiet hours).
        Use for: token hard stops, crashes, security issues.
        """
        if self._is_duplicate(title, message):
            return

        self._send_phone(title, message, priority="high")
        self._send_mac(title, message)
        self._daily_count += 1
        self._log_alert("critical", title, message, True, True)
        print(f"[ALERT:CRITICAL] {title}: {message}")

    def action_needed(self, title: str, message: str):
        """
        Action needed — sends to phone unless quiet hours.
        Use for: PRD reviews, outreach approvals, stuck tasks.
        """
        if self._is_duplicate(title, message):
            return
        if not self._check_daily_limit():
            print(f"[AlertManager] Daily limit reached, skipping: {title}")
            return

        sent_phone = False
        if not self._is_quiet_hours():
            self._send_phone(title, message, priority="normal")
            sent_phone = True
            self._daily_count += 1

        self._send_mac(title, message)
        self._log_alert("action_needed", title, message, sent_phone, True)
        print(f"[ALERT:ACTION] {title}: {message}")

    def info(self, title: str, message: str):
        """
        Info — macOS notification only, no phone.
        Use for: task completions, git pushes, routine updates.
        """
        if self._is_duplicate(title, message, window_minutes=2):
            return

        self._send_mac(title, message)
        self._log_alert("info", title, message, False, True)
        print(f"[ALERT:INFO] {title}: {message}")
