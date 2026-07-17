"""
Main runner — Stage 4: Agent + Tools.
Processes tickets through an agentic pipeline: classify → extract → plan tools
→ execute (with human approval gates) → draft reply.

Usage:
    python main.py                  # agent mode (default, with RAG + tools)
    python main.py --adversarial    # adversarial tickets with agent
    python main.py --auto-approve   # skip human approval for destructive tools
    python main.py --no-agent       # fall back to Stage 3 (no tools)
    python main.py --no-rag         # disable RAG
    python main.py --rebuild-kb     # force re-ingestion of the knowledge base
"""

import json
import sys
import time
import logging

from src.ai_service import classify_ticket, draft_reply, extract_data
from src.knowledge_base import initialise_knowledge_base
from src.agent import run_agent
from src.tool_logger import ToolLogger
from data.sample_tickets import SAMPLE_TICKETS
from data.adversarial_tickets import ADVERSARIAL_TICKETS


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[35m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_separator():
    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{text}{Colors.RESET}")


def print_json(data):
    # Exclude 'sources' from the main JSON dump — we print them separately
    display_data = {k: v for k, v in data.items() if k != "sources"}
    formatted = json.dumps(display_data, indent=2, ensure_ascii=False)
    print(f"{Colors.CYAN}{formatted}{Colors.RESET}")


def print_sources(sources):
    """Print source citations from a RAG-grounded reply."""
    if not sources:
        print(f"  {Colors.DIM}SOURCES: (none — no knowledge base context used){Colors.RESET}")
        return

    print(f"\n  {Colors.BOLD}{Colors.MAGENTA}SOURCES:{Colors.RESET}")
    for i, source in enumerate(sources, 1):
        doc = source.get("doc_name", "unknown")
        page = source.get("page_number", "?")
        chunk_id = source.get("chunk_id", "?")
        preview = source.get("chunk_preview", "")

        if len(preview) > 120:
            preview = preview[:120] + "…"

        print(f"    {Colors.MAGENTA}[{i}]{Colors.RESET} {doc} "
              f"{Colors.DIM}(page {page}, {chunk_id}){Colors.RESET}")
        print(f"        {Colors.DIM}\"{preview}\"{Colors.RESET}")


def print_flag_status(result):
    """Print whether the result was flagged for human review."""
    confidence = result.confidence
    flagged = result.flagged_for_review

    if flagged:
        print(f"  {Colors.RED}[FLAGGED FOR HUMAN REVIEW] confidence={confidence:.2f}{Colors.RESET}")
    else:
        print(f"  {Colors.GREEN}[AUTO-APPROVED] confidence={confidence:.2f}{Colors.RESET}")


def print_agent_plan(plan):
    """Print the agent's tool call plan."""
    if not plan.tool_calls:
        print(f"  {Colors.DIM}No tools needed for this ticket.{Colors.RESET}")
        return

    print(f"  {Colors.BOLD}Planned tool calls:{Colors.RESET}")
    for i, tc in enumerate(plan.tool_calls, 1):
        destructive = ""
        from src.tools import TOOL_REGISTRY
        tool_info = TOOL_REGISTRY.get(tc.tool_name, {})
        if tool_info.get("destructive"):
            destructive = f" {Colors.RED}[DESTRUCTIVE]{Colors.RESET}"

        print(f"    {Colors.WHITE}[{i}]{Colors.RESET} {tc.tool_name}{destructive}")
        print(f"        Args:   {json.dumps(tc.arguments)}")
        print(f"        Reason: {Colors.DIM}{tc.reason}{Colors.RESET}")


def print_tool_results(tool_results):
    """Print tool execution results."""
    if not tool_results:
        return

    print(f"\n  {Colors.BOLD}{Colors.BLUE}TOOL RESULTS:{Colors.RESET}")
    for i, result in enumerate(tool_results, 1):
        name = result.get("tool_name", "?")
        success = result.get("success", False)

        if success:
            print(f"    {Colors.GREEN}[{i}] {name} — SUCCESS{Colors.RESET}")
            data = result.get("data", {})
            if data:
                for key, value in data.items():
                    print(f"        {key}: {Colors.CYAN}{value}{Colors.RESET}")
        else:
            error = result.get("error", "Unknown error")
            print(f"    {Colors.RED}[{i}] {name} — FAILED{Colors.RESET}")
            print(f"        {Colors.RED}Error: {error}{Colors.RESET}")


def print_audit_log(tool_logger, ticket_id):
    """Print the audit log for a specific ticket."""
    logs = tool_logger.get_logs_for_ticket(ticket_id)
    if not logs:
        return

    print(f"\n  {Colors.BOLD}{Colors.WHITE}AUDIT LOG:{Colors.RESET}")
    for record in logs:
        status_parts = []
        if record.approved is True:
            status_parts.append(f"{Colors.GREEN}approved{Colors.RESET}")
        elif record.approved is False:
            status_parts.append(f"{Colors.RED}denied{Colors.RESET}")

        if record.result and record.result.get("success"):
            status_parts.append(f"{Colors.GREEN}success{Colors.RESET}")
        elif record.error:
            status_parts.append(f"{Colors.RED}error{Colors.RESET}")
        elif record.result and not record.result.get("success"):
            status_parts.append(f"{Colors.YELLOW}tool-failed{Colors.RESET}")

        status = ", ".join(status_parts) if status_parts else "unknown"
        approval_tag = f" {Colors.RED}[REQUIRES APPROVAL]{Colors.RESET}" if record.requires_approval else ""

        print(f"    {Colors.DIM}{record.timestamp}{Colors.RESET} "
              f"{record.tool_name}{approval_tag} → {status} "
              f"{Colors.DIM}({record.duration_ms:.1f}ms){Colors.RESET}")

        if record.error:
            print(f"      {Colors.RED}Error: {record.error}{Colors.RESET}")


# =============================================================================
# AGENT MODE (Stage 4)
# =============================================================================

def process_ticket_agent(ticket, tool_logger, use_rag=True, auto_approve=False):
    """Run the full agent pipeline on a single ticket."""
    ticket_id = ticket["id"]
    ticket_text = ticket["text"]

    print_separator()
    print_header(f"TICKET: {ticket_id}")
    print(f"{Colors.DIM}Text:{Colors.RESET} {ticket_text[:120]}{'...' if len(ticket_text) > 120 else ''}")
    print()

    # Run the agent
    agent_result = run_agent(
        ticket=ticket,
        tool_logger=tool_logger,
        use_rag=use_rag,
        auto_approve=auto_approve,
    )

    # 1. Print Classification
    print(f"  {Colors.BOLD}{Colors.BLUE}CLASSIFY{Colors.RESET}")
    if agent_result.classification:
        print_json(agent_result.classification.model_dump())
        print_flag_status(agent_result.classification)
    else:
        print(f"  {Colors.RED}Classification failed{Colors.RESET}")
    print()

    # 2. Print Extraction
    print(f"  {Colors.BOLD}{Colors.YELLOW}EXTRACT DATA{Colors.RESET}")
    if agent_result.extracted:
        print_json(agent_result.extracted.model_dump())
        print_flag_status(agent_result.extracted)
    else:
        print(f"  {Colors.RED}Extraction failed{Colors.RESET}")
    print()

    # 3. Print Agent Plan
    print(f"  {Colors.BOLD}{Colors.MAGENTA}AGENT PLAN{Colors.RESET}")
    if agent_result.agent_plan:
        print(f"  Reasoning: {Colors.DIM}{agent_result.agent_plan.reasoning}{Colors.RESET}")
        print(f"  Confidence: {agent_result.agent_plan.confidence:.2f}")
        print_agent_plan(agent_result.agent_plan)
    else:
        print(f"  {Colors.DIM}No agent plan generated{Colors.RESET}")
    print()

    # 4. Print Tool Results
    if agent_result.tool_results:
        print_tool_results(agent_result.tool_results)
        print()

    # 5. Print Draft Reply
    rag_label = " + RAG" if use_rag else ""
    tools_label = " + TOOLS" if agent_result.tool_results else ""
    print(f"  {Colors.BOLD}{Colors.GREEN}DRAFT REPLY{rag_label}{tools_label}{Colors.RESET}")
    if agent_result.reply:
        reply_data = agent_result.reply.model_dump()
        print_json(reply_data)
        print_flag_status(agent_result.reply)
        print_sources(reply_data.get("sources", []))
    else:
        print(f"  {Colors.RED}Reply drafting failed{Colors.RESET}")

    # 6. Print Audit Log
    print_audit_log(tool_logger, ticket_id)

    # 7. Print Errors
    if agent_result.errors:
        print(f"\n  {Colors.RED}{Colors.BOLD}ERRORS:{Colors.RESET}")
        for err in agent_result.errors:
            print(f"    {Colors.RED}• {err}{Colors.RESET}")

    print()

    return {
        "id": ticket_id,
        "classify_flagged": agent_result.classification.flagged_for_review if agent_result.classification else True,
        "reply_flagged": agent_result.reply.flagged_for_review if agent_result.reply else True,
        "extract_flagged": agent_result.extracted.flagged_for_review if agent_result.extracted else True,
        "sources_count": len(agent_result.reply.sources) if agent_result.reply else 0,
        "tools_called": len(agent_result.tool_results),
        "errors": len(agent_result.errors),
    }


# =============================================================================
# LEGACY MODE (Stage 3 fallback)
# =============================================================================

def process_ticket_legacy(ticket, use_rag=True):
    """Run Stage 3 pipeline (no agent/tools) on a single ticket."""
    ticket_id = ticket["id"]
    ticket_text = ticket["text"]
    classification = None
    reply = None
    extracted = None

    print_separator()
    print_header(f"TICKET: {ticket_id}")
    print(f"{Colors.DIM}Text:{Colors.RESET} {ticket_text[:120]}{'...' if len(ticket_text) > 120 else ''}")
    print()

    # 1. Classify
    print(f"  {Colors.BOLD}{Colors.BLUE}CLASSIFY{Colors.RESET}")
    try:
        classification = classify_ticket(ticket_text)
        print_json(classification.model_dump())
        print_flag_status(classification)
    except Exception as e:
        print(f"  {Colors.RED}ERROR: {e}{Colors.RESET}")

    print()

    # 2. Draft Reply (with RAG, no tools)
    rag_label = " + RAG" if use_rag else ""
    print(f"  {Colors.BOLD}{Colors.GREEN}DRAFT REPLY{rag_label}{Colors.RESET}")
    try:
        reply = draft_reply(ticket_text, classification, use_rag=use_rag)
        reply_data = reply.model_dump()
        print_json(reply_data)
        print_flag_status(reply)
        print_sources(reply_data.get("sources", []))
    except Exception as e:
        print(f"  {Colors.RED}ERROR: {e}{Colors.RESET}")

    print()

    # 3. Extract Data
    print(f"  {Colors.BOLD}{Colors.YELLOW}EXTRACT DATA{Colors.RESET}")
    try:
        extracted = extract_data(ticket_text)
        print_json(extracted.model_dump())
        print_flag_status(extracted)
    except Exception as e:
        print(f"  {Colors.RED}ERROR: {e}{Colors.RESET}")

    print()

    return {
        "id": ticket_id,
        "classify_flagged": classification.flagged_for_review if classification else True,
        "reply_flagged": reply.flagged_for_review if reply else True,
        "extract_flagged": extracted.flagged_for_review if extracted else True,
        "sources_count": len(reply.sources) if reply else 0,
        "tools_called": 0,
        "errors": 0,
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    adversarial_mode = "--adversarial" in sys.argv
    no_rag = "--no-rag" in sys.argv
    rebuild_kb = "--rebuild-kb" in sys.argv
    no_agent = "--no-agent" in sys.argv
    auto_approve = "--auto-approve" in sys.argv

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if adversarial_mode:
        tickets = ADVERSARIAL_TICKETS
        mode_label = "(Adversarial)"
    else:
        tickets = SAMPLE_TICKETS
        mode_label = ""

    if no_agent:
        banner = f"SUPPORT OPS COPILOT  Stage 3: RAG {mode_label}"
    else:
        banner = f"SUPPORT OPS COPILOT  Stage 4: Agent + Tools {mode_label}"

    flags = []
    if no_rag:
        flags.append("RAG DISABLED")
    if no_agent:
        flags.append("AGENT DISABLED")
    if auto_approve:
        flags.append("AUTO-APPROVE")
    if flags:
        banner += f" [{', '.join(flags)}]"

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("=" * 64)
    print(f"  {banner}")
    print("=" * 64)
    print(f"{Colors.RESET}")

    # --- Initialise Knowledge Base ---
    if not no_rag:
        print(f"{Colors.BOLD}{Colors.MAGENTA}Initialising Knowledge Base …{Colors.RESET}")
        try:
            chunk_count = initialise_knowledge_base(force=rebuild_kb)
            print(f"{Colors.GREEN}  ✓ Knowledge base ready ({chunk_count} chunks){Colors.RESET}\n")
        except Exception as e:
            print(f"{Colors.RED}  ✗ Knowledge base init failed: {e}{Colors.RESET}")
            print(f"{Colors.YELLOW}  Proceeding without RAG.{Colors.RESET}\n")
            no_rag = True
    else:
        print(f"{Colors.DIM}  RAG disabled — skipping knowledge base init{Colors.RESET}\n")

    # --- Initialise Tool Logger (Stage 4) ---
    tool_logger = ToolLogger()

    total = len(tickets)
    print(f"Processing {total} tickets...\n")

    start = time.time()
    results = []

    for i, ticket in enumerate(tickets, 1):
        print(f"{Colors.DIM}[{i}/{total}]{Colors.RESET}")

        if no_agent:
            result = process_ticket_legacy(ticket, use_rag=not no_rag)
        else:
            result = process_ticket_agent(
                ticket,
                tool_logger=tool_logger,
                use_rag=not no_rag,
                auto_approve=auto_approve,
            )

        results.append(result)

    elapsed = time.time() - start
    print_separator()

    # Summary
    flagged_count = sum(
        1 for r in results
        if r["classify_flagged"] or r["reply_flagged"] or r["extract_flagged"]
    )
    auto_count = total - flagged_count
    total_sources = sum(r["sources_count"] for r in results)
    total_tools = sum(r["tools_called"] for r in results)
    total_errors = sum(r["errors"] for r in results)

    print(f"\n{Colors.BOLD}SUMMARY{Colors.RESET}")
    print(f"  Processed:            {total} tickets in {elapsed:.1f}s")
    print(f"  Auto-approved:        {auto_count}")
    print(f"  Flagged for review:   {flagged_count}")
    print(f"  Total source citations: {total_sources}")

    if not no_agent:
        tool_summary = tool_logger.get_summary()
        print(f"  Tool calls:           {tool_summary['total_tool_calls']}")
        print(f"    Approved:           {tool_summary['approved']}")
        print(f"    Denied:             {tool_summary['denied']}")
        print(f"    Successful:         {tool_summary['successful']}")
        print(f"    Errors:             {tool_summary['errors']}")

    if total_errors > 0:
        print(f"  {Colors.RED}Pipeline errors:      {total_errors}{Colors.RESET}")

    if flagged_count > 0:
        print(f"\n  {Colors.YELLOW}Flagged tickets:{Colors.RESET}")
        for r in results:
            if r["classify_flagged"] or r["reply_flagged"] or r["extract_flagged"]:
                flags = []
                if r["classify_flagged"]:
                    flags.append("classify")
                if r["reply_flagged"]:
                    flags.append("reply")
                if r["extract_flagged"]:
                    flags.append("extract")
                print(f"    {r['id']}: {', '.join(flags)}")

    print()


if __name__ == "__main__":
    main()
