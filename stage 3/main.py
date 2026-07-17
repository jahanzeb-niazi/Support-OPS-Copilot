"""
Main runner — Stage 3: RAG.
Processes tickets through the AI Service with validated output
and knowledge-base-grounded replies with source citations.

Usage:
    python main.py                  # runs SAMPLE_TICKETS (default, with RAG)
    python main.py --adversarial    # runs ADVERSARIAL_TICKETS (with RAG)
    python main.py --no-rag         # runs without RAG (Stage 2 behaviour)
    python main.py --rebuild-kb     # force re-ingestion of the knowledge base
"""

import json
import sys
import time
import logging

from src.ai_service import classify_ticket, draft_reply, extract_data
from src.knowledge_base import initialise_knowledge_base
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

        # Truncate preview for display
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


def process_ticket(ticket, use_rag=True):
    """Run all three functions on a single ticket."""
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

    # 2. Draft Reply (with RAG)
    rag_label = " + RAG" if use_rag else ""
    print(f"  {Colors.BOLD}{Colors.GREEN}DRAFT REPLY{rag_label}{Colors.RESET}")
    try:
        reply = draft_reply(ticket_text, classification, use_rag=use_rag)
        reply_data = reply.model_dump()
        print_json(reply_data)
        print_flag_status(reply)
        # Print source citations
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

    # Return results for summary
    return {
        "id": ticket_id,
        "classify_flagged": classification.flagged_for_review if classification else True,
        "reply_flagged": reply.flagged_for_review if reply else True,
        "extract_flagged": extracted.flagged_for_review if extracted else True,
        "sources_count": len(reply.sources) if reply else 0,
    }


def main():
    adversarial_mode = "--adversarial" in sys.argv
    no_rag = "--no-rag" in sys.argv
    rebuild_kb = "--rebuild-kb" in sys.argv

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if adversarial_mode:
        tickets = ADVERSARIAL_TICKETS
        banner = "SUPPORT OPS COPILOT  Stage 3: RAG (Adversarial)"
    else:
        tickets = SAMPLE_TICKETS
        banner = "SUPPORT OPS COPILOT  Stage 3: RAG"

    if no_rag:
        banner += " [RAG DISABLED]"

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("=" * 60)
    print(f"  {banner}")
    print("=" * 60)
    print(f"{Colors.RESET}")

    # --- Stage 3: Initialise Knowledge Base ---
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

    total = len(tickets)
    print(f"Processing {total} tickets...\n")

    start = time.time()
    results = []

    for i, ticket in enumerate(tickets, 1):
        print(f"{Colors.DIM}[{i}/{total}]{Colors.RESET}")
        result = process_ticket(ticket, use_rag=not no_rag)
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

    print(f"\n{Colors.BOLD}SUMMARY{Colors.RESET}")
    print(f"  Processed: {total} tickets in {elapsed:.1f}s")
    print(f"  Auto-approved: {auto_count}")
    print(f"  Flagged for review: {flagged_count}")
    print(f"  Total source citations: {total_sources}")

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
