# Voice Agent

A LiveKit-based call center voice agent with three role-based agents:
- Tier 1 support
- Tier 2 escalation
- Feedback collection

## Tech Stack

- Python 3.12+
- LiveKit Agents
- Deepgram STT
- OpenAI LLM via LiveKit inference string
- Cartesia TTS via LiveKit Inference
- Google Sheets API for feedback logging
- SMTP email for feedback confirmation
- `uv` for dependency management

## Project Flow

- `CallAgent` handles frontline support
- `EscalationAgent` handles advanced troubleshooting and escalations
- `FeedbackAgent` collects feedback, writes to Google Sheets, sends email, and closes the call

## Local Setup

1. Install Python 3.12+
2. Install `uv`
3. Install dependencies:

```bash
uv sync
```

4. Create your local env file from the example:

```bash
copy .env.example .env.local
```

5. Fill in your secrets in `.env.local`
   - LiveKit credentials
   - Deepgram API key
   - Google API key
   - SMTP settings
   - Google Sheets spreadsheet ID
   - Google service account JSON path

6. Share your target Google Sheet with the service account email as an editor

## Running Locally

Start the worker in dev mode:

```bash
uv run agent.py dev
```

Then connect to your LiveKit room or Playground and talk to the agent.

## Main Files

- `agent.py` - worker entrypoint and session setup
- `call_agent.py` - agent classes and transfer tools
- `agent_config_format.py` - prompts and model config
- `feedback_ops.py` - Google Sheets + email integration
- `.env.example` - env variable template

## Thoughts

WIP.

## Future Updates

WIP.
