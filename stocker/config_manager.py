"""Config manager — load/save YAML config and merge with CLI args."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml


DEFAULT_CONFIG_PATH = Path("~/.stocker/config.yaml").expanduser()


@dataclass
class NotificationConfig:
    method: str = "desktop"          # desktop | email | sms | none
    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""
    # Twilio SMS
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""
    twilio_to: str = ""


@dataclass
class PositionConfig:
    ticker: str = ""
    shares: float = 0.0
    cost_basis: float = 0.0         # average price paid per share
    profit_target: float = 0.0      # dollar amount to net


@dataclass
class AppConfig:
    position: PositionConfig = field(default_factory=PositionConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    poll_interval: int = 10         # seconds between price checks
    scenario_step: int = 1          # share increment between scenarios


def load_config(path: Optional[Path] = None) -> AppConfig:
    """Load config from *path* (or the default path if it exists)."""
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        return AppConfig()

    with open(target) as fh:
        raw = yaml.safe_load(fh) or {}

    position = PositionConfig(**raw.get("position", {}))
    notification = NotificationConfig(**raw.get("notification", {}))
    return AppConfig(
        position=position,
        notification=notification,
        poll_interval=raw.get("poll_interval", 10),
        scenario_step=raw.get("scenario_step", 1),
    )


def save_config(cfg: AppConfig, path: Optional[Path] = None) -> None:
    """Persist *cfg* to *path* (or the default path)."""
    target = path or DEFAULT_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "position": asdict(cfg.position),
        "notification": asdict(cfg.notification),
        "poll_interval": cfg.poll_interval,
        "scenario_step": cfg.scenario_step,
    }
    with open(target, "w") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False)
