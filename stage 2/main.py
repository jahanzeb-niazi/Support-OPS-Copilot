"""
Main runner — Stage 2: Reliability.
Processes tickets through the AI Service with validated output.

Usage:
    python main.py                  # runs SAMPLE_TICKETS (default)
    python main.py --adversarial    # runs ADVERSARIAL_TICKETS
"""

import json
import sys
import time

from src.ai_service import classify_ticket, draft_reply, extract_data
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
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_separator():
    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{text}{Colors.RESET}")


def print_json(data):
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    print(f"{Colors.CYAN}{formatted}{Colors.RESET}")


def print_flag_status(result):
    """Print whether the result was flagged for human review."""
    confidence = result.confidence
    flagged = result.flagged_for_review

    if flagged:
        print(f"  {Colors.RED}[FLAGGED FOR HUMAN REVIEW] confidence={confidence:.2f}{Colors.RESET}")
    else:
        print(f"  {Colors.GREEN}[AUTO-APPROVED] confidence={confidence:.2f}{Colors.RESET}")


def process_ticket(ticket):
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

    # 2. Draft Reply
    print(f"  {Colors.BOLD}{Colors.GREEN}DRAFT REPLY{Colors.RESET}")
    try:
        reply = draft_reply(ticket_text, classification)
        print_json(reply.model_dump())
        print_flag_status(reply)
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
    }


def main():
    adversarial_mode = "--adversarial" in sys.argv

    if adversarial_mode:
        tickets = ADVERSARIAL_TICKETS
        banner = "SUPPORT OPS COPILOT  Stage 2: Reliability (Adversarial)"
    else:
        tickets = SAMPLE_TICKETS
        banner = "SUPPORT OPS COPILOT  Stage 2: Reliability"

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("=" * 60)
    print(f"  {banner}")
    print("=" * 60)
    print(f"{Colors.RESET}")

    total = len(tickets)
    print(f"Processing {total} tickets...\n")

    start = time.time()
    results = []

    for i, ticket in enumerate(tickets, 1):
        print(f"{Colors.DIM}[{i}/{total}]{Colors.RESET}")
        result = process_ticket(ticket)
        results.append(result)

    elapsed = time.time() - start
    print_separator()

    # Summary
    flagged_count = sum(
        1 for r in results
        if r["classify_flagged"] or r["reply_flagged"] or r["extract_flagged"]
    )
    auto_count = total - flagged_count

    print(f"\n{Colors.BOLD}SUMMARY{Colors.RESET}")
    print(f"  Processed: {total} tickets in {elapsed:.1f}s")
    print(f"  Auto-approved: {auto_count}")
    print(f"  Flagged for review: {flagged_count}")

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
