from livekit.agents import Agent
from livekit.agents.llm import function_tool

from agent_config_format import (
    ESCALATION_VOICE_ID,
    FEEDBACK_VOICE_ID,
    SUPPORT_VOICE_ID,
    build_tts,
    escalation_instructions,
    feedback_instructions,
)
from feedback_ops import store_feedback_and_notify


class BaseCallCenterAgent(Agent):
    """Shared call-center behaviors for role agents."""

    def __init__(self, *, instructions: str, voice_id: str, chat_ctx=None) -> None:
        super().__init__(
            instructions=instructions,
            chat_ctx=chat_ctx,
            tts=build_tts(voice_id),
        )

    def _transfer_to_feedback(self, topic: str):
        feedback_agent = FeedbackAgent(
            topic=topic,
            chat_ctx=self.chat_ctx,
        )
        return (
            feedback_agent,
            "Please hold while I connect you to our feedback specialist.",
        )

    def _end_no_feedback(self, closing_line: str) -> str:
        self.session.say(closing_line)
        self.session.shutdown(drain=True)
        return ""

    def _no_feedback_closing_line(self) -> str:
        return (
            "No problem at all. Thank you for your time today. "
            "If you need anything else, we are here to help. Goodbye."
        )

    @function_tool
    async def endCallNoFeedback(self):
        """Called when the caller declines feedback and wants to end the call."""
        return self._end_no_feedback(self._no_feedback_closing_line())


class CallAgent(BaseCallCenterAgent):
    """Tier 1 support agent — first point of contact."""

    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions, voice_id=SUPPORT_VOICE_ID)

    async def on_enter(self):
        """Generate a greeting when this agent takes control of the session."""
        self.session.say(
            "Thank you for calling our support center. This is Zephyr, your Tier 1 frontline support agent. How can I help you today?"
        )

    @function_tool
    async def callEscalationAgent(self, topic: str):
        """
        Called to connect to escalation agent when the user wants to escalate the issue.
        Args:
            topic: The topic of the issue.
        """
        escalation_agent = EscalationAgent(
            topic=topic,
            chat_ctx=self.chat_ctx,
        )
        return (
            escalation_agent,
            "Please hold while I connect you to our escalation specialist.",
        )

    @function_tool
    async def supportToFeedback(self, topic: str):
        """
        Called when the issue is resolved at frontline support and the caller agrees
        to provide feedback without escalation.
        Args:
            topic: A short summary of the resolved issue.
        """
        return self._transfer_to_feedback(topic)

    def _no_feedback_closing_line(self) -> str:
        return (
            "No problem at all. Thank you for calling support today. "
            "If you need anything else, we are here to help. Goodbye."
        )


class EscalationAgent(BaseCallCenterAgent):
    """Escalation agent — handles escalated issues."""

    def __init__(self, topic: str, chat_ctx=None) -> None:
        self.topic = topic
        super().__init__(
            instructions=escalation_instructions(topic),
            voice_id=ESCALATION_VOICE_ID,
            chat_ctx=chat_ctx,
        )

    async def on_enter(self):
        """Generate a greeting when this agent takes control of the session."""
        self.session.say(
            "Hi, this is Orion, your Tier 2 escalation specialist. I handle advanced troubleshooting and escalated concerns."
        )
        self.session.generate_reply(
            instructions=f"Continue immediately after the introduction for {self.topic}. Do not say thank you, got it, understood, I understand, or any other filler acknowledgement. Do not repeat the introduction. Start directly with one focused diagnostic question. Do not transfer to feedback now. In this first escalation turn, do not call any tools. Any prior yes/no before this handoff is not feedback consent."
        )

    @function_tool
    async def escalationToFeedback(self, topic: str):
        """
        Called only when the user clearly agrees to transfer to the feedback agent.
        Never call this on the first escalation response.
        Call this immediately after consent.
        Args:
            topic: The topic of the issue.
        """
        return self._transfer_to_feedback(topic)

    def _no_feedback_closing_line(self) -> str:
        return (
            "Understood. Thank you for your time today. "
            "If you need further support, please call us anytime. Goodbye."
        )


class FeedbackAgent(BaseCallCenterAgent):
    """Feedback agent — handles feedback from the user."""

    def __init__(self, topic: str, chat_ctx=None) -> None:
        self.topic = topic
        super().__init__(
            instructions=feedback_instructions(topic),
            voice_id=FEEDBACK_VOICE_ID,
            chat_ctx=chat_ctx,
        )

    async def on_enter(self):
        """Generate a greeting when this agent takes control of the session."""
        self.session.say(
            "Hello, this is Thalia from the feedback team. I am here to collect your feedback on your previous issue."
        )
        self.session.generate_reply(
            instructions=f"The issue topic was: {self.topic}. Continue immediately after this introduction. Do not say thank you, got it, understood, or any other filler acknowledgement. Do not repeat the introduction. Begin feedback immediately with the first feedback question. Ask one question at a time and keep it brief."
        )

    @function_tool
    async def submitFeedbackAndEndCall(
        self,
        caller_name: str,
        caller_email: str,
        satisfied: bool,
        reason: str,
        rating: int,
    ):
        """Persist feedback to Google Sheets, email the caller, then end the call."""
        if rating < 1 or rating > 10:
            return "Please provide a valid rating from 1 to 10."

        self.session.say(
            "Thank you. Please give me a brief moment while I create your ticket and submit your feedback."
        )

        ticket_number, errors = store_feedback_and_notify(
            caller_name=caller_name.strip(),
            caller_email=caller_email.strip(),
            satisfied=satisfied,
            reason=reason.strip(),
            rating=rating,
            topic=self.topic,
        )

        if errors:
            failed_parts = ", ".join(errors)
            self.session.say(
                f"Thank you, {caller_name}. I created ticket {ticket_number}, but there was a system issue while saving or sending confirmation. Your feedback is still important to us and our team will follow up."
            )
            self.session.shutdown(drain=True)
            return f"Ticket {ticket_number} created, but integrations failed: {failed_parts}"

        self.session.say(
            f"Thank you, {caller_name}. Your feedback has been recorded under ticket {ticket_number}. We have sent a confirmation email to {caller_email}. Your voice is important to us."
        )
        self.session.shutdown(drain=True)
        return f"Feedback captured, stored, and emailed. Ticket {ticket_number}."

    def _no_feedback_closing_line(self) -> str:
        return (
            "Understood. No problem at all. Thank you for your time today. "
            "If you need anything else, we are here to help. Goodbye."
        )
