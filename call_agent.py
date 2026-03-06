from livekit.agents import Agent
from livekit.agents.llm import function_tool

from agent_config_format import (
    ESCALATION_VOICE_ID,
    FEEDBACK_VOICE_ID,
    ONBOARDING_VOICE_ID,
    SUPPORT_AGENT_INSTRUCTIONS,
    SUPPORT_VOICE_ID,
    ONBOARDING_AGENT_INSTRUCTIONS,
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


class OnboardingAgent(BaseCallCenterAgent):
    """Onboarding agent that introduces the system before support."""

    def __init__(self) -> None:
        super().__init__(
            instructions=ONBOARDING_AGENT_INSTRUCTIONS,
            voice_id=ONBOARDING_VOICE_ID,
        )

    async def on_enter(self):
        self.session.say(
            "Hello, this is Nova. Before we begin, would you like a short description of how this call center system works?"
        )

    @function_tool
    async def explainSystemAndContinue(self):
        """Explain the system briefly, then transfer to frontline support."""
        self.session.say(
            "This system uses specialized agents. Tier 1 support helps with general troubleshooting, Tier 2 handles escalations, and our feedback agent collects your feedback at the end if you would like to provide it."
        )
        return CallAgent(instructions=CallAgent.support_instructions()), ""

    @function_tool
    async def continueToSupport(self):
        """Transfer directly to frontline support without explaining the system."""
        return CallAgent(instructions=CallAgent.support_instructions()), ""


class CallAgent(BaseCallCenterAgent):
    """Tier 1 support agent — first point of contact."""

    @staticmethod
    def support_instructions() -> str:
        return SUPPORT_AGENT_INSTRUCTIONS

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
            f"Hi, this is Orion, your Tier 2 escalation specialist. I handle advanced troubleshooting and escalated concerns. For the {self.topic} issue, what exactly happens when you try to use it?"
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
            f"Hello, this is Thalia from the feedback team. I am here to collect your feedback about {self.topic}. May I have your full name, please?"
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
