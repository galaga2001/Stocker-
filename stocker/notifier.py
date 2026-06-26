"""Notifier — desktop, email, and SMS alert delivery."""

from __future__ import annotations

import smtplib
import traceback
from email.message import EmailMessage
from typing import Optional

from stocker.config_manager import NotificationConfig
from stocker.scenario_generator import Scenario


class Notifier:
    def __init__(self, cfg: NotificationConfig):
        self.cfg = cfg
        self._method = cfg.method.lower()

    def alert(self, scenario: Scenario, current_price: float) -> None:
        title = f"Stocker Alert — {scenario.shares_to_sell} shares"
        body = (
            f"Price target HIT: ${current_price:.2f} >= ${scenario.required_price:.2f}\n"
            f"Sell {scenario.shares_to_sell} share(s) to net ${scenario.profit_target:.2f}"
        )
        try:
            if self._method == "desktop":
                self._desktop(title, body)
            elif self._method == "email":
                self._email(title, body)
            elif self._method == "sms":
                self._sms(body)
            # "none" silently skips
        except Exception:
            # Notification failures must never crash the monitor loop
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Delivery backends
    # ------------------------------------------------------------------

    def _desktop(self, title: str, body: str) -> None:
        try:
            from plyer import notification as plyer_notif
            plyer_notif.notify(
                title=title,
                message=body,
                app_name="Stocker",
                timeout=10,
            )
        except ImportError:
            # plyer unavailable — fall back to a terminal bell
            print(f"\a[ALERT] {title}: {body}")

    def _email(self, subject: str, body: str) -> None:
        cfg = self.cfg
        if not all([cfg.smtp_user, cfg.smtp_password, cfg.email_to]):
            raise ValueError("Email notification requires smtp_user, smtp_password, and email_to")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg.smtp_user
        msg["To"] = cfg.email_to
        msg.set_content(body)
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as s:
            s.starttls()
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.send_message(msg)

    def _sms(self, body: str) -> None:
        try:
            from twilio.rest import Client
        except ImportError:
            raise RuntimeError("Install twilio: pip install twilio")
        cfg = self.cfg
        if not all([cfg.twilio_sid, cfg.twilio_token, cfg.twilio_from, cfg.twilio_to]):
            raise ValueError("SMS notification requires twilio_sid, twilio_token, twilio_from, twilio_to")
        client = Client(cfg.twilio_sid, cfg.twilio_token)
        client.messages.create(body=body, from_=cfg.twilio_from, to=cfg.twilio_to)
