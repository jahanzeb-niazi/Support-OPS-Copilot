# Support OPS Copilot — Stage 2: Reliability

A Python-based AI Service module powered by **Google Gemini** + **instructor** that classifies support tickets, drafts replies, and extracts structured data — with validated output, automatic retries, and confidence-based human review flagging.

## What Changed from Stage 1

- **instructor library** patches Gemini to return validated Pydantic models (not raw dicts)
- **Automatic retries** — if Pydantic validation fails, instructor re-prompts the LLM (max 3 attempts)
- **Graceful fallback** — if all retries fail, returns a safe default (no crash)
- **Confidence scoring** — every response includes a confidence score (0.0–1.0)
- **Human review flagging** — confidence < 0.7 auto-flags the result for human review (server-side enforcement)
- **New adversarial tickets** — mixed languages, emotional rants, code injection, wrong-domain content

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

```bash
python main.py
```

### Run Adversarial Tests

Runs 13 adversarial tickets designed to stress-test failure modes.
Each ticket has inline comments describing the exact expected behaviour:

```bash
python main.py --adversarial
```

Review the output and document findings in `BREAKING_IT.md`.

## Architecture

```
├── src/
│   ├── models.py              # Pydantic models for validated AI output
│   ├── ai_service.py          # Core module: classify, draft_reply, extract_data (instructor)
│   └── prompts.py             # System prompts + few-shot examples
├── data/
│   ├── sample_tickets.py      # Realistic test tickets
│   └── adversarial_tickets.py # Adversarial tickets (13 cases)
├── main.py                    # Unified runner (--adversarial flag for stress tests)
├── BREAKING_IT.md             # Failure documentation
└── README.md
```

## AI Service Functions

| Function | Input | Output (Pydantic Model) |
|---|---|---|
| `classify_ticket(text)` | Raw ticket text | `ClassificationResult { category, urgency, confidence, reasoning, flagged_for_review }` |
| `draft_reply(text, classification)` | Ticket + classification | `DraftReplyResult { subject, body, tone, confidence, flagged_for_review }` |
| `extract_data(text)` | Raw ticket text | `ExtractedDataResult { name, email, order_id, issue, product, date_mentioned, confidence, flagged_for_review }` |

## Confidence Threshold

```
confidence >= 0.7  →  Auto-approved (safe to send/use)
confidence <  0.7  →  Flagged for human review
```

The `flagged_for_review` field is enforced server-side — even if the LLM sets confidence to 0.65 but forgets to flag, the Pydantic model validator overrides it to `True`.

## Model

Uses `gemini-2.5-flash` via instructor with `mode=GEMINI_JSON` and max 3 retries on validation failure.
