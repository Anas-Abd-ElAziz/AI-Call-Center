"""Structured JSON logging for the call center agent.

LiveKit Cloud can forward these runtime logs to CloudWatch when the required
AWS deployment secrets are configured.
"""

import json
import logging

from livekit.agents import AgentSession
from livekit.agents.metrics import UsageCollector


class _JSONFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object."""

    def format(self, record):
        entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "event": getattr(record, "event_name", record.getMessage()),
        }
        extra = getattr(record, "event_data", None)
        if extra:
            entry.update(extra)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


logger = logging.getLogger("call_center")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    _console = logging.StreamHandler()
    _console.setFormatter(_JSONFormatter())
    logger.addHandler(_console)


def log_event(event: str, **data) -> None:
    """Log a structured event with optional key-value data."""
    logger.info(event, extra={"event_name": event, "event_data": data})


def setup_session_logging(session: AgentSession) -> None:
    """Subscribe to session events for aggregate lifecycle logging."""
    usage = UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(event):
        usage.collect(event.metrics)

    @session.on("error")
    def _on_error(event):
        log_event(
            "session.error",
            error_type=type(event.error).__name__,
            error=str(event.error),
            source=type(event.source).__name__,
        )

    @session.on("close")
    def _on_close(event):
        s = usage.get_summary()
        log_event(
            "call.ended",
            reason=event.reason.value,
            total_prompt_tokens=s.llm_prompt_tokens,
            total_completion_tokens=s.llm_completion_tokens,
            total_tts_characters=s.tts_characters_count,
            total_tts_audio_sec=round(s.tts_audio_duration, 2),
            total_stt_audio_sec=round(s.stt_audio_duration, 2),
        )
