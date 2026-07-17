# Support OPS Copilot — Stage 4: Agent + Tools

A Python-based AI Service module powered by **Google Gemini** + **instructor** that classifies support tickets, drafts replies, extracts data, and now **takes actions** via a tool-calling agent — with human-in-the-loop approval for destructive operations, full audit logging, and RAG-grounded answers with source citations.

## What Changed from Stage 3

- **Tool-calling agent** — the LLM now decides which tools to call based on ticket context
- **5 mock tools** — `lookup_order_status`, `check_warranty`, `issue_refund`, `cancel_order`, `escalate_to_human`
- **Human-in-the-loop** — destructive tools (`issue_refund`, `cancel_order`) require terminal approval (`y/n`) before execution
- **Audit logging** — every tool call is logged with inputs, outputs, approval decisions, errors, and timing
- **Graceful error handling** — unknown tools, tool exceptions, and denied actions are logged and handled (no silent failures)
- **Tool-aware replies** — the draft reply now includes tool execution results so the customer gets real data (e.g., "Your refund REF-123456 has been processed")

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key from [Google AI Studio](https://aistudio.google.com/).

### 3. Knowledge Base

Place PDF documents in `knowledge base/`. Auto-ingested on first run.

## Usage

### Agent Mode (default)

```bash
python main.py
```

Runs the full pipeline: classify → extract → plan tools → execute → draft reply.  
**Destructive tools prompt for approval.**

### Auto-Approve Mode

```bash
python main.py --auto-approve
```

Skips human approval prompts (for batch testing only).

### Adversarial Tests

```bash
python main.py --adversarial
```

### Fall Back to Stage 3 (no tools)

```bash
python main.py --no-agent
```

### Other Flags

```bash
python main.py --no-rag          # disable RAG
python main.py --rebuild-kb      # force re-ingest knowledge base
```

## Architecture

```
├── src/
│   ├── models.py              # Pydantic models (+ ToolCallRequest, AgentPlan)
│   ├── ai_service.py          # Core AI: classify, draft_reply, extract, plan_agent_actions
│   ├── prompts.py             # System prompts + RAG/tool formatting helpers
│   ├── knowledge_base.py      # PDF ingestion, chunking, ChromaDB retrieval
│   ├── tools.py               # 5 mock tools + TOOL_REGISTRY
│   ├── tool_logger.py         # Audit logger for all tool invocations
│   └── agent.py               # Agent orchestrator (classify → plan → execute → reply)
├── data/
│   ├── sample_tickets.py      # Test tickets (tool-triggering scenarios)
│   └── adversarial_tickets.py # Adversarial tickets (13 cases)
├── knowledge base/
│   └── Support_Ops_Copilot_Knowledge_Base.pdf
├── chroma_db/                 # ChromaDB local storage (gitignored)
├── main.py                    # Runner (--auto-approve, --no-agent, --adversarial, etc.)
└── README.md
```

## Agent Pipeline

```
Ticket
  │
  ├── 1. classify_ticket()         → ClassificationResult
  ├── 2. extract_data()            → ExtractedDataResult
  ├── 3. plan_agent_actions()      → AgentPlan (list of ToolCallRequests)
  ├── 4. Execute tools             → ToolResults[]
  │      ├── Read-only: auto-approved
  │      └── Destructive: human approval gate (y/n)
  └── 5. draft_reply()             → DraftReplyResult (with sources + tool context)
```

## Tools

| Tool | Type | Description |
|---|---|---|
| `lookup_order_status` | Read-only | Look up order details by ID |
| `check_warranty` | Read-only | Check warranty status for an order |
| `issue_refund` | **Destructive** | Process a refund (requires approval) |
| `cancel_order` | **Destructive** | Cancel an order (requires approval) |
| `escalate_to_human` | Action | Hand off to human agent queue |

## Audit Log

Every tool call is logged with:
- Timestamp
- Tool name and arguments
- Whether approval was required / granted / denied
- Result (success/failure/error)
- Execution duration (ms)

## Model

Uses `gemini-3.1-flash-lite` via instructor with `mode=JSON` and max 3 retries.  
Embeddings: `all-MiniLM-L6-v2` via sentence-transformers (local).
