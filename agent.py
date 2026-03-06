from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.agents import room_io
from livekit.plugins import noise_cancellation
from livekit import rtc
from dotenv import load_dotenv
from pathlib import Path
from agent_config_format import (
    LLM_MODEL,
    SESSION_MAX_ENDPOINTING_DELAY,
    SESSION_MIN_ENDPOINTING_DELAY,
    SESSION_PREEMPTIVE_GENERATION,
    SUPPORT_AGENT_INSTRUCTIONS,
    build_stt,
)


load_dotenv(Path(__file__).resolve().parent / ".env.local")

from call_agent import CallAgent


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=build_stt(),
        llm=LLM_MODEL,
        preemptive_generation=SESSION_PREEMPTIVE_GENERATION,
        min_endpointing_delay=SESSION_MIN_ENDPOINTING_DELAY,
        max_endpointing_delay=SESSION_MAX_ENDPOINTING_DELAY,
    )

    await session.start(
        room=ctx.room,
        agent=CallAgent(
            instructions=SUPPORT_AGENT_INSTRUCTIONS,
        ),
        room_options=room_io.RoomOptions(
            video_input=False,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            num_idle_processes=1,
        )
    )
