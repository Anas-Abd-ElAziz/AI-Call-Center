# Voice Agent

A LiveKit-based call center voice agent with three role-based agents:
- Onboarding / system introduction
- Tier 1 support
- Tier 2 escalation
- Feedback collection

## Live Demo

Try the deployed agent here:

- [AI Call Center Sandbox](https://ai-call-center-2jw2lw.sandbox.livekit.io)

## Features

- Multi-agent phone support flow with support, escalation, and feedback roles
- Onboarding agent that can explain the system before routing the caller to support
- Role-based voice output using LiveKit Inference TTS
- Live call handoff tools between agents
- Tier 1 to feedback path for resolved issues without escalation
- Feedback logging to Google Sheets
- Follow-up confirmation email after feedback submission
- Email confirmation step before feedback submission
- Ticket creation tied to feedback records
- Structured runtime logs that LiveKit can forward to CloudWatch
- Local development workflow with `uv` and LiveKit Playground
- Deployed with Docker on LiveKit Cloud

## Tech Stack

- Python 3.12+
- LiveKit Agents
- Deepgram STT
- Silero VAD
- OpenAI LLM via LiveKit inference string
- Cartesia TTS via LiveKit Inference
- Google Sheets API for feedback logging
- SMTP email for feedback confirmation
- Docker
- LiveKit Cloud
- `uv` for dependency management

## Project Flow

- `OnboardingAgent` welcomes the caller and optionally explains the system
- `CallAgent` handles frontline support
- `EscalationAgent` handles advanced troubleshooting and escalations
- `FeedbackAgent` confirms caller email, collects feedback, writes to Google Sheets, sends email, and closes the call

## Architecture

```text
Caller
  |
  v
LiveKit Room / Playground
  |
  v
agent.py
  |
  v
AgentSession
  |- STT: Deepgram
  |- VAD: Silero
  |- LLM: OpenAI via LiveKit inference string
  |- TTS: Cartesia via LiveKit Inference
  |
  v
call_agent.py
  |- OnboardingAgent
  |- CallAgent
  |- EscalationAgent
  |- FeedbackAgent
  |
  v
feedback_ops.py
  |- Google Sheets append
  |- SMTP confirmation email

Deployment
  |- Docker container
  |- LiveKit Cloud
```

## Deployment

This project is packaged with Docker for LiveKit Cloud agent deployment.

Helpful LiveKit deployment references:

- [LiveKit Agent Deployment Overview](https://docs.livekit.io/deploy/agents/)
- [LiveKit Agent Deployment Quickstart](https://docs.livekit.io/deploy/agents/quickstart/)
- [LiveKit Builds and Dockerfiles](https://docs.livekit.io/deploy/agents/builds/)
- [LiveKit Log Collection](https://docs.livekit.io/deploy/agents/logs/)

Basic deployment flow:

```bash
lk cloud auth
lk agent create
lk agent deploy
```

Useful follow-up commands:

```bash
lk agent status
lk agent logs
lk agent logs --log-type=build
```

For new versions, run the deploy command again from the project root after updating your code.

This deployment setup uses the project Dockerfile, and your deployment environment is configured from `.env.local` in your current workflow.
When `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_REGION` are present in LiveKit deployment secrets, LiveKit forwards runtime stdout and stderr logs to CloudWatch automatically.

## GitHub Auto Deploy

This repo includes a GitHub Actions workflow at `.github/workflows/deploy.yml` that can deploy the agent automatically on pushes to `main`.

Required GitHub repository secrets:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `DEEPGRAM_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `GOOGLE_SERVICE_ACCOUNT_INFO`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_RANGE`
- `AWS_ACCESS_KEY_ID` (optional, enables CloudWatch forwarding)
- `AWS_SECRET_ACCESS_KEY` (optional, enables CloudWatch forwarding)
- `AWS_REGION` (optional, defaults to `us-west-2` in LiveKit)

The workflow:

- installs the LiveKit CLI
- adds your LiveKit Cloud project to the CLI
- builds a deployment secrets file from GitHub secrets
- runs `lk agent deploy`

After the workflow and repository secrets are configured, each push to `main` triggers a new deployment automatically.

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
    - SMTP settings
    - Google Sheets spreadsheet ID
    - Google service account credentials as raw JSON in `GOOGLE_SERVICE_ACCOUNT_INFO`

6. Share your target Google Sheet with the service account email as an editor

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `LIVEKIT_API_KEY` | Yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | Yes | LiveKit API secret |
| `LIVEKIT_URL` | Yes | LiveKit server URL |
| `NEXT_PUBLIC_LIVEKIT_URL` | Optional | Client-facing LiveKit URL |
| `DEEPGRAM_API_KEY` | Yes | Speech-to-text provider key |
| `SMTP_HOST` | Yes | SMTP server host |
| `SMTP_PORT` | Yes | SMTP server port |
| `SMTP_USER` | Yes | SMTP username/email |
| `SMTP_PASSWORD` | Yes | SMTP password or app password |
| `SMTP_FROM` | Yes | Sender email address |
| `GOOGLE_SERVICE_ACCOUNT_INFO` | Yes | Full Google service account JSON stored as a single secret/env var |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Yes | Google Sheets document ID |
| `GOOGLE_SHEETS_RANGE` | Optional | Target sheet range, e.g. `Calls!A:G` |
| `AWS_ACCESS_KEY_ID` | Optional | Enables LiveKit runtime log forwarding to CloudWatch |
| `AWS_SECRET_ACCESS_KEY` | Optional | Enables LiveKit runtime log forwarding to CloudWatch |
| `AWS_REGION` | Optional | AWS region for CloudWatch forwarding |

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

## Notes

- `.env.local` and service account credentials must stay local or in your cloud secret manager and should never be committed
- Rotate any credentials that were exposed during development before publishing
- Screen sharing is currently disabled in this version
- The Dockerfile is intended for LiveKit Cloud agent deployment

## Thoughts

WIP.

## Future Updates

WIP.
