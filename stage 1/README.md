# Support OPS Copilot — Stage 1: Core AI Service Layer

A Python-based AI Service module powered by **Google Gemini** that classifies support tickets, drafts replies, and extracts structured data.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Copy the example env file and add your Gemini API key:

```bash
cp .env.example .env
```

Edit `.env` and replace `your_api_key_here` with your actual key from [Google AI Studio](https://aistudio.google.com/).

## Usage

### Run on Sample Tickets

Processes realistic support tickets through all three AI functions:

```bash
python main.py
```

### Run Adversarial Tests

Runs adversarial tickets designed to stress-test failure modes.
Each ticket has inline comments describing the exact expected behaviour:

```bash
python main.py --adversarial
```

Review the output and document findings in `BREAKING_IT.md`.

## Architecture

```
├── src/
│   ├── ai_service.py          # Core module: classify, draft_reply, extract_data
│   └── prompts.py             # System prompts + few-shot examples
├── data/
│   ├── sample_tickets.py      # Realistic test tickets
│   └── adversarial_tickets.py # Adversarial tickets with expected-behaviour comments
├── main.py                    # Unified runner (--adversarial flag for stress tests)
├── BREAKING_IT.md             # Failure documentation
└── README.md
```

## AI Service Functions

| Function | Input | Output |
|---|---|---|
| `classify_ticket(text)` | Raw ticket text | `{ category, urgency, confidence, reasoning }` |
| `draft_reply(text, classification)` | Ticket + classification | `{ subject, body, tone }` |
| `extract_data(text)` | Raw ticket text | `{ name, email, order_id, issue, product, date_mentioned }` |

All functions use **role-based system prompts** and **few-shot examples** for consistent, structured output.

## Model

Uses `gemini-2.0-flash` with `temperature=0.3` and JSON response mode.
