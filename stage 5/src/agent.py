"""
Agent Orchestrator — Stage 4: Agent + Tools.
The brain that chains: classify → extract → plan tools → execute → draft reply.
Handles human-in-the-loop approval for destructive actions and graceful error handling.
"""

import time
import logging
from typing import Optional

from src.ai_service import classify_ticket, extract_data, plan_agent_actions, draft_reply
from src.tools import TOOL_REGISTRY
from src.tool_logger import ToolLogger
from src.models import ClassificationResult, ExtractedDataResult, DraftReplyResult, AgentPlan

logger = logging.getLogger(__name__)


class AgentResult:
    """Container for the full result of processing a ticket through the agent."""

    def __init__(self):
        self.ticket_id: str = ""
        self.ticket_text: str = ""
        self.classification: Optional[ClassificationResult] = None
        self.extracted: Optional[ExtractedDataResult] = None
        self.agent_plan: Optional[AgentPlan] = None
        self.tool_results: list[dict] = []
        self.reply: Optional[DraftReplyResult] = None
        self.errors: list[str] = []


def _execute_tool(
    tool_name: str,
    arguments: dict,
    ticket_id: str,
    tool_logger: ToolLogger,
    auto_approve: bool = False,
    approved: Optional[bool] = None,
) -> Optional[dict]:
    """
    Execute a single tool with approval gating and logging.

    For destructive tools:
      - If `approved` is explicitly True/False (e.g. supplied by a UI like Streamlit),
        that decision is used and no terminal prompt is shown.
      - Otherwise, if auto_approve is False, prompts the human for y/n approval on the terminal.
      - If denied, logs and returns a result dict with success=False.

    For non-destructive tools:
      - Auto-approved, executed immediately

    All tool calls (input + output) are logged via tool_logger.
    Errors are caught and logged — never silently swallowed.
    """
    # Check if tool exists
    tool_info = TOOL_REGISTRY.get(tool_name)
    if tool_info is None:
        logger.warning(f"Unknown tool '{tool_name}' — skipping")
        record = tool_logger.create_record(
            ticket_id=ticket_id,
            tool_name=tool_name,
            arguments=arguments,
            requires_approval=False,
        )
        tool_logger.record_error(record, f"Unknown tool: '{tool_name}'")
        return {
            "tool_name": tool_name,
            "success": False,
            "data": None,
            "error": f"Unknown tool: '{tool_name}'",
        }

    is_destructive = tool_info["destructive"]
    tool_fn = tool_info["fn"]

    # Create log record
    record = tool_logger.create_record(
        ticket_id=ticket_id,
        tool_name=tool_name,
        arguments=arguments,
        requires_approval=is_destructive,
    )

    # --- Approval gate for destructive tools ---
    if is_destructive and not auto_approve:
        if approved is not None:
            # Decision already supplied by an external caller (e.g. a Streamlit UI
            # approve/reject button) — skip the terminal prompt entirely.
            if not approved:
                tool_logger.record_approval(record, approved=False)
                return {
                    "tool_name": tool_name,
                    "success": False,
                    "data": None,
                    "error": "Action denied by human reviewer.",
                }
            tool_logger.record_approval(record, approved=True)
        else:
            print(f"\n  \033[91m\033[1m⚠  APPROVAL REQUIRED — DESTRUCTIVE ACTION\033[0m")
            print(f"  Tool:      {tool_name}")
            print(f"  Arguments: {arguments}")
            print(f"  Ticket:    {ticket_id}")

            try:
                approval = input(f"  \033[93mApprove? [y/n]: \033[0m").strip().lower()
            except (EOFError, KeyboardInterrupt):
                approval = "n"

            if approval != "y":
                tool_logger.record_approval(record, approved=False)
                print(f"  \033[91m✗ DENIED — tool not executed\033[0m")
                return {
                    "tool_name": tool_name,
                    "success": False,
                    "data": None,
                    "error": "Action denied by human reviewer.",
                }

            tool_logger.record_approval(record, approved=True)
            print(f"  \033[92m✓ APPROVED\033[0m")
    else:
        tool_logger.record_approval(record, approved=True)

    # --- Execute the tool ---
    start = time.time()
    try:
        result = tool_fn(**arguments)
        duration_ms = (time.time() - start) * 1000
        tool_logger.record_result(record, result, duration_ms)

        return {
            "tool_name": tool_name,
            "success": result.get("success", False),
            "data": result.get("data"),
            "error": result.get("error"),
        }

    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        error_msg = f"{type(e).__name__}: {e}"
        tool_logger.record_error(record, error_msg, duration_ms)
        logger.error(f"Tool '{tool_name}' raised an exception: {error_msg}")

        return {
            "tool_name": tool_name,
            "success": False,
            "data": None,
            "error": error_msg,
        }


def run_agent(
    ticket: dict,
    tool_logger: ToolLogger,
    use_rag: bool = True,
    auto_approve: bool = False,
) -> AgentResult:
    """
    Full agent pipeline for a single ticket:
      1. Classify the ticket
      2. Extract structured data
      3. LLM plans which tools to call
      4. Execute tools (with approval gates)
      5. Draft reply using all context (classification + RAG + tool results)

    Returns an AgentResult with all intermediate and final outputs.
    """
    result = AgentResult()
    result.ticket_id = ticket["id"]
    result.ticket_text = ticket["text"]
    ticket_text = ticket["text"]
    ticket_id = ticket["id"]

    # --- Step 1: Classify ---
    try:
        result.classification = classify_ticket(ticket_text)
    except Exception as e:
        result.errors.append(f"Classification failed: {e}")
        logger.error(f"Classification failed for {ticket_id}: {e}")

    # --- Step 2: Extract data ---
    try:
        result.extracted = extract_data(ticket_text)
    except Exception as e:
        result.errors.append(f"Extraction failed: {e}")
        logger.error(f"Extraction failed for {ticket_id}: {e}")

    # --- Step 3: Agent plans tool calls ---
    if result.classification and result.extracted:
        try:
            result.agent_plan = plan_agent_actions(
                ticket_text, result.classification, result.extracted
            )
        except Exception as e:
            result.errors.append(f"Agent planning failed: {e}")
            logger.error(f"Agent planning failed for {ticket_id}: {e}")

    # --- Step 4: Execute planned tools ---
    if result.agent_plan and result.agent_plan.tool_calls:
        for tool_call in result.agent_plan.tool_calls:
            tool_result = _execute_tool(
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                ticket_id=ticket_id,
                tool_logger=tool_logger,
                auto_approve=auto_approve,
            )
            if tool_result:
                result.tool_results.append(tool_result)

    # --- Step 5: Draft reply with full context ---
    try:
        result.reply = draft_reply(
            ticket_text,
            classification=result.classification,
            use_rag=use_rag,
            tool_results=result.tool_results if result.tool_results else None,
        )
    except Exception as e:
        result.errors.append(f"Reply drafting failed: {e}")
        logger.error(f"Reply drafting failed for {ticket_id}: {e}")

    return result