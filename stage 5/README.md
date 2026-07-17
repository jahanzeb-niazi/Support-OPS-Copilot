# 🎧 Support Ops Copilot

An AI-powered support-ticket copilot built on Google Gemini. It classifies incoming
tickets, extracts structured data, retrieves grounded context from a knowledge base
(RAG), plans and executes backend tools with human-in-the-loop approval for
destructive actions, and drafts a customer reply with cited sources — all through a
Streamlit review UI.

## Features

- **Classification** — category + urgency, with confidence scoring and auto-flagging
  of low-confidence results for human review.
- **Structured extraction** — pulls name, email, order ID, product, and issue summary
  out of raw ticket text.
- **RAG-grounded replies** — retrieves relevant chunks from a PDF knowledge base
  (ChromaDB + sentence-transformers) and cites sources in the drafted reply.
- **Agent + tools** — an LLM plans which backend tools to call (order lookup,
  warranty check, refund, cancellation, escalation), then executes them.
- **Human-in-the-loop approval** — destructive tools (`issue_refund`, `cancel_order`)
  always pause for an explicit approve/reject decision before running.
- **Full audit log** — every tool call (inputs, outputs, approval decision, timing,
  errors) is logged and viewable in the sidebar.
- **Validated output everywhere** — every LLM call is wrapped in `instructor` +
  Pydantic, with automatic retries and graceful fallbacks on failure.

## Project structure

```
support-ops-copilot/
├── Streamlit_app.py          # Streamlit UI — entry point for interactive use
├── requirements.txt          # Python dependencies
├── .env                      # GEMINI_API_KEY (you create this — not committed)
│
├── src/                      # Application package
│   ├── __init__.py
│   ├── agent.py               # Orchestrator: _execute_tool() + run_agent() pipeline
│   ├── ai_service.py           # Gemini calls via instructor: classify / extract / plan / draft
│   ├── prompts.py              # System prompts, few-shot examples, context formatters
│   ├── models.py                # Pydantic schemas for all validated LLM output
│   ├── tools.py                  # Mock backend tools + TOOL_REGISTRY
│   ├── tool_logger.py             # In-memory audit log for tool calls
│   └── knowledge_base.py           # PDF ingestion, chunking, ChromaDB storage + retrieval
│
├── knowledge base/            # PDF(s) ingested into the RAG knowledge base
│   └── *.pdf
│
├── data/                      # Ticket fixtures for testing/demo
│   ├── sample_tickets.py       # SAMPLE_TICKETS — loaded into the UI's sample picker
│   └── adversarial_testing.py  # Edge-case / adversarial ticket examples
│
└── chroma_db/                 # ChromaDB persistent storage (auto-created on first run)
```

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set your Gemini API key**

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

**3. Add a knowledge base PDF**

Drop one or more PDFs into the `knowledge base/` folder. They're auto-ingested and
chunked the first time the app starts with RAG enabled.

**4. Run the app**

```bash
streamlit run Streamlit_app.py
```

## How a ticket flows through the system

1. **Submit** — raw ticket text goes in via the form (or picked from
   `data/sample_tickets.py`).
2. **Classify** — `classify_ticket()` returns category, urgency, and confidence.
3. **Extract** — `extract_data()` pulls structured fields (name, email, order ID, etc.).
4. **Plan** — `plan_agent_actions()` asks the LLM which tools (if any) are needed,
   given the ticket, classification, and extracted data.
5. **Approve** — read-only tools (`lookup_order_status`, `check_warranty`,
   `escalate_to_human`) auto-run. Destructive tools (`issue_refund`, `cancel_order`)
   wait for a reviewer to click Approve/Reject in the UI.
6. **Execute** — approved tools run via `_execute_tool()`, with every call logged by
   `ToolLogger`.
7. **Draft reply** — `draft_reply()` combines the ticket, classification, RAG context,
   and tool results into a cited, confidence-scored customer reply.
8. **Review** — the reviewer approves the reply for sending or flags it for a human
   rewrite.

## Tool registry

| Tool | Destructive? | Purpose |
|---|---|---|
| `lookup_order_status` | No | Look up an order's status, product, amount, tracking |
| `check_warranty` | No | Check warranty status/coverage for an order |
| `issue_refund` | **Yes** | Process a refund — requires approval |
| `cancel_order` | **Yes** | Cancel an active/processing order — requires approval |
| `escalate_to_human` | No | Route the ticket to a human agent queue |

## Testing

Use `data/sample_tickets.py` for a quick demo run through the UI's sample picker, and
`data/adversarial_testing.py` for edge cases (vague/gibberish tickets, prompt-injection
attempts, missing data) to verify confidence flagging and graceful fallbacks behave
correctly.

## Notes

- All LLM calls retry up to 3 times on validation failure, then fall back to a safe,
  flagged-for-review default rather than crashing.
- Results with confidence below `CONFIDENCE_THRESHOLD` (0.7, in `models.py`) are
  automatically flagged for human review.
- If `GEMINI_API_KEY` is missing, the UI will warn you but won't block the page load.
- If the knowledge base is empty or unavailable, replies proceed without RAG context
  rather than failing.
