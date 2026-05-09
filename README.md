# NeuroAgent 🧠

> **A production-grade, multi-model AI assistant** powered by LangGraph, Groq, Gemini, Tavily, and Pinecone — with Gmail integration, Sarvam AI audio, voice I/O, and a terminal-biopunk UI.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Available Models](#available-models)
- [Agent Tools](#agent-tools)
- [Agent Modes](#agent-modes)
- [Memory System](#memory-system)
- [Voice & Audio](#voice--audio)
- [Sarvam AI Integration](#sarvam-ai-integration)
- [Gmail Setup](#gmail-setup)
- [API Reference](#api-reference)
- [Frontend Overview](#frontend-overview)
- [Running Tests](#running-tests)
- [Tech Stack](#tech-stack)

---

## Overview

NeuroAgent is a full-stack, multi-agent AI chatbot that combines:

- **Fast inference** via Groq (LLaMA 3.3 70B, Qwen3, GPT-OSS 120B)
- **Reasoning models** via Google Gemini (2.0 Flash, 2.5 Pro) and OpenAI (GPT-4o, o3-mini)
- **Free-tier models** via OpenRouter (NVIDIA Nemotron, Poolside Laguna)
- **Real-time web search** via Tavily
- **Persistent semantic memory** via Pinecone vector store
- **Gmail read/send** via OAuth2
- **Indian language audio** via Sarvam AI (Bulbul v2 TTS, Saarika v2 STT, Mayura translation)
- **Voice I/O** via SpeechRecognition + gTTS/pyttsx3 fallback
- **Shell execution** with safety guardrails
- A **terminal-biopunk single-page frontend** (pure HTML/CSS/JS, no build step)

---

## Architecture

```
User Input (browser)
        │
        ▼
  Flask REST API  (/api/chat)
        │
        ├─ Session Auth (Flask-Session / SQLite)
        ├─ Model selection (Groq / Gemini / OpenAI / OpenRouter)
        │
        ▼
  Orchestrator  (backend/agents/orchestrator.py)
        │
        ├─ Load short-term history  ← SQLite (last 10 turns)
        ├─ Retrieve semantic memories ← Pinecone (top-5 relevant)
        └─ Build LangGraph initial state
                │
                ▼
        LangGraph ReAct Agent Graph
        ┌──────────────────────────┐
        │        agent node        │  ← LLM (Groq / Gemini / OpenAI / OpenRouter)
        │  + system prompt         │    bound with ALL_TOOLS
        │  + history + memories    │
        └───────────┬──────────────┘
                    │  tool_calls present?
           YES ─────┘        NO → END (final reply)
                    │
        ┌───────────▼──────────────┐
        │        tools node        │  web_search · deep_research
        │   (LangGraph ToolNode)   │  read_emails · send_gmail
        └───────────┬──────────────┘  execute_command · calculator
                    │                 sarvam_tts · sarvam_translate
                    └──── loop back → agent node (max 10 iterations)
                                │
                                ▼
                    Save to SQLite + Pinecone
                                │
                                ▼
                    JSON response → frontend
```

---

## Project Structure

```
neuroagent/
├── app.py                          ← Entry point — run this!
├── .env                            ← API keys (copy from .env.example)
├── requirements.txt
├── pyproject.toml
│
├── backend/
│   ├── config.py                   ← All config, model registry, env loading
│   ├── app.py                      ← Flask app factory + all API routes
│   │
│   ├── agents/
│   │   ├── tools.py                ← LangChain @tool definitions (8 tools)
│   │   ├── graph.py                ← LangGraph StateGraph (ReAct loop)
│   │   └── orchestrator.py         ← Single run_chat() entry point
│   │
│   ├── db/
│   │   ├── user_store.py           ← SQLite: users, preferences, history
│   │   └── memory_store.py         ← Pinecone: long-term semantic memory
│   │
│   └── utils/
│       ├── llm_factory.py          ← LLM instantiation by provider
│       ├── gmail_client.py         ← Gmail OAuth2: read + send
│       ├── sarvam_client.py        ← Sarvam AI: TTS, STT, analytics, translate
│       └── voice.py                ← SpeechRecognition + gTTS/pyttsx3
│
├── frontend/
│   ├── templates/
│   │   └── index.html              ← Single Page Application
│   └── static/
│       ├── css/style.css           ← Terminal-biopunk stylesheet
│       └── js/app.js               ← All frontend logic
│
└── tests/
    ├── 1 test.py                   ← Sarvam TTS smoke test
    └── test_sarvam_client.py       ← Unit tests for translate + fallback
```

---

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd neuroagent
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

The only **required** key to get started is `GROQ_API_KEY` (free). All others are optional.

### 3. Run

```bash
python app.py
```

The browser opens automatically at `http://127.0.0.1:5000`.

---

## Environment Variables

| Variable              | Required | Description                                              |
|-----------------------|----------|----------------------------------------------------------|
| `GROQ_API_KEY`        | ✅ Yes   | Fast inference (LLaMA, Qwen, GPT-OSS). Free at [console.groq.com](https://console.groq.com) |
| `GEMINI_API_KEY`      | Optional | Gemini models + Pinecone embeddings. Free at [aistudio.google.com](https://aistudio.google.com) |
| `OPENAI_API_KEY`      | Optional | GPT-4o, o3-mini. Paid. [platform.openai.com](https://platform.openai.com) |
| `OPENROUTER_API_KEY`  | Optional | Free-tier models (Nemotron, Laguna). [openrouter.ai](https://openrouter.ai) |
| `TAVILY_API_KEY`      | Optional | Web search tool. Free tier available at [tavily.com](https://tavily.com) |
| `PINECONE_API_KEY`    | Optional | Long-term memory. Free tier at [pinecone.io](https://pinecone.io) |
| `PINECONE_INDEX_NAME` | Optional | Defaults to `neuroagent-memory` |
| `SARVAM_API_KEY`      | Optional | Indian language TTS/STT/translate. [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `FLASK_SECRET_KEY`    | Optional | Change in production. Defaults to `change-me-in-production` |
| `APP_HOST`            | Optional | Defaults to `127.0.0.1` |
| `APP_PORT`            | Optional | Defaults to `5000` |
| `DEBUG`               | Optional | Defaults to `True` |

> **Security note:** Never commit a filled-in `.env` to version control. The `.gitignore` already excludes it.

---

## Available Models

Models are registered in `backend/config.py` and rendered live in the UI.

| Label                    | ID                                   | Provider    | Context | Notes                        |
|--------------------------|--------------------------------------|-------------|---------|------------------------------|
| LLaMA 3.1 8B Instant     | `llama-3.1-8b-instant`               | Groq        | 128K    | Ultra-fast, best for Q&A     |
| LLaMA 3.3 70B Versatile  | `llama-3.3-70b-versatile`            | Groq        | 128K    | **Default** — best all-round |
| GPT-OSS 120B             | `openai/gpt-oss-120b`                | Groq        | 128K    | OpenAI open-source via Groq  |
| Qwen3 32B                | `qwen/qwen3-32b`                     | Groq        | 32K     | Strong reasoning + code      |
| Nemotron Nano Omni 30B   | `nvidia/nemotron-3-nano-omni-30b-…`  | OpenRouter  | 32K     | Free multimodal reasoning    |
| Laguna XS.2              | `poolside/laguna-xs.2:free`          | OpenRouter  | 16K     | Free code-focused model      |
| GPT-4o                   | `gpt-4o`                             | OpenAI      | 128K    | Flagship multimodal          |
| GPT-4o Mini              | `gpt-4o-mini`                        | OpenAI      | 128K    | Fast + affordable            |
| o3 Mini                  | `o3-mini`                            | OpenAI      | 128K    | Complex multi-step reasoning |
| Gemini 2.0 Flash         | `gemini-2.0-flash`                   | Gemini      | 1M      | General-purpose multimodal   |
| Gemini 2.0 Flash-Lite    | `gemini-2.0-flash-lite`              | Gemini      | 1M      | High-frequency / low-latency |
| Gemini 2.5 Flash         | `gemini-2.5-flash-preview-05-20`     | Gemini      | 1M      | Fast, balanced intelligence  |
| Gemini 2.5 Flash-Lite    | `gemini-2.5-flash-lite-preview-06-17`| Gemini      | 1M      | High-throughput / cost-opt   |
| Gemini 2.5 Pro           | `gemini-2.5-pro-preview-05-06`       | Gemini      | 1M      | Best for complex reasoning   |
| Gemini 3.1 Flash-Lite    | `gemini-3.1-flash-lite`              | Gemini      | 1M      | Latest Gen 3                 |

To add a new model, append an entry to the `MODELS` list in `backend/config.py`.

---

## Agent Tools

Defined in `backend/agents/tools.py` and bound to the LangGraph agent at runtime.

| Tool                    | Description                                                    | Requires              |
|-------------------------|----------------------------------------------------------------|-----------------------|
| `web_search`            | Real-time search via Tavily (5 results, advanced depth)        | `TAVILY_API_KEY`      |
| `deep_research`         | Multi-pass research synthesis via Tavily context API           | `TAVILY_API_KEY`      |
| `read_emails`           | Read Gmail inbox with optional Gmail query syntax              | Gmail credentials     |
| `send_gmail`            | Compose and send email via OAuth2 Gmail                        | Gmail credentials     |
| `execute_command`       | Safe shell execution (blocked: `rm -rf`, `mkfs`, `dd`, forks) | None                  |
| `calculator`            | Evaluate math expressions using Python's `math` module         | None                  |
| `sarvam_text_to_speech` | Generate Indian-language audio (Bulbul v2, 11 langs)           | `SARVAM_API_KEY`      |
| `sarvam_translate`      | Translate between Indian languages (Mayura v1)                 | `SARVAM_API_KEY`      |
| `summarise_text`        | Condense long documents into ~150 words                        | None                  |

---

## Agent Modes

Switch modes from the `+` button in the chat input, or via `POST /api/agent/mode`.

| Mode       | Behaviour                                                                 |
|------------|---------------------------------------------------------------------------|
| `default`  | General-purpose assistant                                                 |
| `deep`     | Prefers `deep_research` for complex queries; synthesises into actionable answers |
| `web`      | Prefers `web_search`; clearly separates verified facts from assumptions   |
| `resched`  | Helps reschedule tasks; asks for constraints; outputs concrete schedules  |

The active mode is shown in the top-bar and persisted in the Flask session.

---

## Memory System

NeuroAgent uses a **two-tier memory architecture**:

### Short-term (SQLite)
- Stored in `backend/db/neuroagent.db`
- Last **20 conversation turns** loaded on every chat request
- Converted to LangChain `HumanMessage` / `AIMessage` objects for the graph

### Long-term (Pinecone)
- Each conversation turn is embedded and upserted into Pinecone
- **Namespace isolation**: each user gets their own Pinecone namespace
- On every turn, the **top-5 semantically similar memories** (score > 0.5) are injected into the system prompt
- **Embedding model**: Gemini `embedding-001` (768-dim) when `GEMINI_API_KEY` is set; falls back to a local deterministic SHA-256 embedding otherwise
- Delete all memories for a user: `memory_store.delete_user_memories(username)`

---

## Voice & Audio

### Voice Input (Speech-to-Text)
- Click the 🎙 microphone button in the chat input
- Captures audio via browser `MediaRecorder`
- Sent to `/api/voice/input` → `SpeechRecognition` → Google Web Speech API
- Auto-fills the input box with the transcript

### Voice Output (Text-to-Speech)
- Click **🔊 Play** on any assistant message
- Or enable "Voice Output" in the sidebar to auto-play all replies
- Engine priority:
  1. **Sarvam Bulbul v2** (if `SARVAM_API_KEY` configured) — Indian accent support
  2. **gTTS** — Google Text-to-Speech, returns MP3
  3. **pyttsx3** — Offline fallback, returns WAV

---

## Sarvam AI Integration

Sarvam AI provides Indian-language AI models. Configure via `SARVAM_API_KEY` in `.env` or enter the key in the sidebar at runtime.

### Text-to-Speech (Bulbul v2)
- 11 languages: Hindi, English (India), Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia
- 12 voices: Meera, Pavithra, Maitreyi, Arvind, Amol, Amartya, Diya, Neel, Misha, Vian, Arjun, Maya
- Endpoint: `POST /api/sarvam/tts`

### Speech-to-Text (Saarika v2)
- Transcribes Indian English and regional language audio
- Endpoint: `POST /api/sarvam/stt`

### Speech Analytics (Saaras v2)
- Diarized transcription with speaker segmentation
- Available via `sarvam_client.speech_analytics_sarvam()`

### Translation (Mayura v1)
- Translate between 10 Indian languages
- SDK-first with HTTP fallback
- Endpoint: `POST /api/sarvam/translate`

---

## Gmail Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable the **Gmail API**
3. Create **OAuth2 credentials** (Desktop App type) → Download `credentials.json`
4. Place it at `backend/gmail_credentials.json` (or set `GMAIL_CREDENTIALS_PATH` in `.env`)
5. On first use, a browser window opens for OAuth consent; a `gmail_token.json` is saved for subsequent runs

Scopes granted: `gmail.readonly`, `gmail.send`, `gmail.modify`

---

## API Reference

### Auth

| Method | Endpoint       | Body                    | Description                        |
|--------|----------------|-------------------------|------------------------------------|
| POST   | `/api/login`   | `{ username }`          | Login or auto-register user        |
| POST   | `/api/logout`  | —                       | Clear session                      |
| GET    | `/api/session` | —                       | Get current session info           |

### Models

| Method | Endpoint              | Body                             | Description               |
|--------|-----------------------|----------------------------------|---------------------------|
| GET    | `/api/models`         | —                                | List all available models |
| POST   | `/api/model/select`   | `{ model_id, *_api_key }`        | Switch active model       |

### Chat

| Method | Endpoint            | Body                        | Description                      |
|--------|---------------------|-----------------------------|----------------------------------|
| POST   | `/api/chat`         | `{ message, model_id }`     | Send message, get agent reply    |
| GET    | `/api/agent/mode`   | —                           | Get current agent mode           |
| POST   | `/api/agent/mode`   | `{ agent_mode }`            | Set agent mode                   |

### Voice

| Method | Endpoint              | Body / Form                          | Description               |
|--------|-----------------------|--------------------------------------|---------------------------|
| POST   | `/api/voice/input`    | multipart: `audio` file              | Audio → transcription     |
| POST   | `/api/voice/output`   | `{ text, language, speaker }`        | Text → base64 MP3/WAV     |
| POST   | `/api/voice/toggle`   | `{ enabled }`                        | Toggle auto-voice output  |

### Sarvam AI

| Method | Endpoint                | Body                                                      | Description           |
|--------|-------------------------|-----------------------------------------------------------|-----------------------|
| POST   | `/api/sarvam/tts`       | `{ text, language, speaker, api_key? }`                   | Generate speech audio |
| POST   | `/api/sarvam/stt`       | multipart: `audio`, `language`, `api_key?`                | Transcribe audio      |
| POST   | `/api/sarvam/translate` | `{ text, source_language, target_language, api_key? }`    | Translate text        |
| GET    | `/api/sarvam/models`    | —                                                         | List Sarvam models    |

### History & Health

| Method | Endpoint               | Body | Description                    |
|--------|------------------------|------|--------------------------------|
| GET    | `/api/history`         | —    | Fetch recent chat history      |
| POST   | `/api/history/clear`   | —    | Delete all history for user    |
| GET    | `/api/health`          | —    | System capabilities status     |

---

## Frontend Overview

The entire frontend is a **no-build, single-page application** (`frontend/templates/index.html`) with:

- **Login screen** — username entry with animated background orbs + grid
- **Model modal** — filterable grid of all models; per-provider API key panels
- **Chat screen**:
  - Collapsible sidebar: active model, Sarvam AI panel, capabilities status, actions
  - Top bar: active model label, intent badge, agent mode badge, live status LED
  - Message thread: role-aware bubbles, tool-trace (blurred), TTS play button
  - Input area: voice mic, agent mode picker (`+`), textarea, send button
- **Toast notifications** — success / error feedback
- **Voice recording overlay** — waveform animation while recording

All state is managed in a plain `S = {}` object in `app.js`. No build step, no npm, no bundler.

---

## Running Tests

```bash
# Sarvam SDK integration test (requires a real API key)
python "tests/1 test.py"

# Unit tests (mocked — no real API calls)
python -m pytest tests/test_sarvam_client.py -v
```

The unit tests cover:
- `translate_text_sarvam` using the SDK when available
- `translate_text_sarvam` falling back to raw HTTP when SDK is absent

---

## Tech Stack

| Layer         | Technology                                             |
|---------------|--------------------------------------------------------|
| Backend       | Python 3.12, Flask 3, Flask-Session, Flask-CORS        |
| Agent         | LangGraph 0.2+, LangChain 0.3+                        |
| LLMs          | Groq, Google Gemini, OpenAI, OpenRouter                |
| Search        | Tavily Python SDK                                      |
| Memory        | Pinecone (serverless), Gemini Embeddings               |
| Email         | Google Gmail API v1, google-auth-oauthlib              |
| Indian Audio  | Sarvam AI (sarvamai SDK + HTTP fallback)               |
| Voice I/O     | SpeechRecognition, gTTS, pyttsx3                       |
| Database      | SQLite (via stdlib `sqlite3`)                          |
| Frontend      | Vanilla HTML5 / CSS3 / ES6 JS (no framework/bundler)  |
| Fonts         | Inter, JetBrains Mono (Google Fonts)                  |

---

## Contributing

1. Fork the repo and create a feature branch.
2. Add/update tests in `tests/` for any new backend logic.
3. Keep tool definitions in `backend/agents/tools.py` and register them in `ALL_TOOLS`.
4. To add a new LLM provider, extend `get_llm()` in `backend/utils/llm_factory.py` and add model entries to `MODELS` in `backend/config.py`.
5. Submit a pull request with a clear description of what changed and why.

---

> Built with ❤️ — combining fast LLMs, semantic memory, real-time search, voice, and Indian language AI into one extensible assistant.
