"""Structured JSON logging for the call center agent.

LiveKit Cloud can forward these runtime logs to CloudWatch when the required
AWS deployment secrets are configured.
"""

import json
import logging

from livekit.agents import AgentSession
from livekit.agents.metrics import UsageCollector
from livekit.agents.metrics.base import EOUMetrics, LLMMetrics, TTSMetrics


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
    pending_turns: dict[str, dict[str, float]] = {}

    def _maybe_log_turn_latency(speech_id: str) -> None:
        turn = pending_turns.get(speech_id)
        if turn is None:
            return

        required = ("stt_sec", "eou_sec", "llm_ttft_sec", "tts_ttfb_sec")
        if not all(key in turn for key in required):
            return

        log_event(
            "turn.latency",
            speech_id=speech_id,
            stt_sec=round(turn["stt_sec"], 4),
            eou_sec=round(turn["eou_sec"], 4),
            llm_ttft_sec=round(turn["llm_ttft_sec"], 4),
            tts_ttfb_sec=round(turn["tts_ttfb_sec"], 4),
            total_to_first_audio_sec=round(
                turn["stt_sec"]
                + turn["eou_sec"]
                + turn["llm_ttft_sec"]
                + turn["tts_ttfb_sec"],
                4,
            ),
        )
        pending_turns.pop(speech_id, None)

    @session.on("metrics_collected")
    def _on_metrics(event):
        metrics = event.metrics
        usage.collect(metrics)

        speech_id = getattr(metrics, "speech_id", None)
        if speech_id:
            turn = pending_turns.setdefault(speech_id, {})
            if isinstance(metrics, EOUMetrics):
                turn["stt_sec"] = metrics.transcription_delay
                turn["eou_sec"] = metrics.end_of_utterance_delay
            elif isinstance(metrics, LLMMetrics) and "llm_ttft_sec" not in turn:
                turn["llm_ttft_sec"] = metrics.ttft
            elif isinstance(metrics, TTSMetrics) and "tts_ttfb_sec" not in turn:
                turn["tts_ttfb_sec"] = metrics.ttfb

            _maybe_log_turn_latency(speech_id)

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
