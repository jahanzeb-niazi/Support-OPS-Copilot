# Support OPS Copilot — Stage 3: RAG

A Python-based AI Service module powered by **Google Gemini** + **instructor** that classifies support tickets, drafts replies, and extracts structured data — with validated output, automatic retries, confidence-based human review flagging, and **RAG-grounded answers with source citations**.

## What Changed from Stage 2

- **Knowledge Base ingestion** — reads PDF docs from `knowledge base/`, chunks the text (~500 chars with overlap), and stores embeddings in ChromaDB
- **Local embeddings** — uses `all-MiniLM-L6-v2` via sentence-transformers (no API cost for embeddings)
- **RAG retrieval** — before drafting a reply, the system retrieves the top-3 most relevant knowledge base chunks
- **Grounded replies** — the LLM receives knowledge base context and grounds its answer in real product docs/policies
- **Source citations** — every AI reply includes `sources` — a list of `SourceCitation` objects citing which doc, page, and chunk the information came from
- **CLI flags** — `--rebuild-kb` to force re-ingestion, `--no-rag` to run without knowledge base

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

### 3. Knowledge Base

Place your PDF documents in the `knowledge base/` directory. The system will automatically ingest them on first run.

A sample `Support_Ops_Copilot_Knowledge_Base.pdf` is already included.

## Usage

### Run on Sample Tickets (with RAG)

```bash
python main.py
```

### Run Adversarial Tests (with RAG)

```bash
python main.py --adversarial
```

### Force Rebuild Knowledge Base

```bash
python main.py --rebuild-kb
```

### Run Without RAG (Stage 2 behaviour)

```bash
python main.py --no-rag
```

## Architecture

```
├── src/
│   ├── models.py              # Pydantic models (+ SourceCitation for RAG)
│   ├── ai_service.py          # Core module: classify, draft_reply (RAG), extract_data
│   ├── prompts.py             # System prompts + few-shot + RAG context formatting
│   └── knowledge_base.py      # PDF ingestion, chunking, embedding, ChromaDB retrieval
├── data/
│   ├── sample_tickets.py      # Realistic test tickets
│   └── adversarial_tickets.py # Adversarial tickets (13 cases)
├── knowledge base/
│   └── Support_Ops_Copilot_Knowledge_Base.pdf
├── chroma_db/                 # ChromaDB local storage (gitignored)
├── main.py                    # Unified runner (--adversarial, --rebuild-kb, --no-rag)
├── BREAKING_IT.md             # Failure documentation
└── README.md
```

## AI Service Functions

| Function | Input | Output (Pydantic Model) |
|---|---|---|
| `classify_ticket(text)` | Raw ticket text | `ClassificationResult { category, urgency, confidence, reasoning, flagged_for_review }` |
| `draft_reply(text, classification, use_rag)` | Ticket + classification + RAG flag | `DraftReplyResult { subject, body, tone, confidence, flagged_for_review, sources[] }` |
| `extract_data(text)` | Raw ticket text | `ExtractedDataResult { name, email, order_id, issue, product, date_mentioned, confidence, flagged_for_review }` |

## RAG Pipeline

```
PDF docs  →  PyPDF2 extract  →  chunk (~500 chars)  →  embed (all-MiniLM-L6-v2)  →  ChromaDB
                                                                                       ↓
Ticket text  →  embed  →  query ChromaDB  →  top-3 chunks  →  LLM prompt context  →  grounded reply + citations
```

## Source Citations

Every draft reply includes a `sources` list. Each source contains:

| Field | Description |
|---|---|
| `doc_name` | Name of the source PDF document |
| `page_number` | Page number in the source document |
| `chunk_id` | ID of the chunk (e.g., `chunk_0012`) |
| `chunk_preview` | First ~100 characters of the chunk for quick verification |

## Confidence Threshold

```
confidence >= 0.7  →  Auto-approved (safe to send/use)
confidence <  0.7  →  Flagged for human review
```

## Model

Uses `gemini-3.1-flash-lite` via instructor with `mode=JSON` and max 3 retries on validation failure.
Embeddings: `all-MiniLM-L6-v2` via sentence-transformers (runs locally).
