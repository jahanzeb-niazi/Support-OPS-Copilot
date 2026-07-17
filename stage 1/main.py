"""
Main runner — processes tickets through the three AI Service functions.

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
    print(f"{Colors.DIM}{'═' * 80}{Colors.RESET}")


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{text}{Colors.RESET}")


def print_json(data):
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    print(f"{Colors.CYAN}{formatted}{Colors.RESET}")


def process_ticket(ticket):
    """Run all three functions on a single ticket."""
    ticket_id = ticket["id"]
    ticket_text = ticket["text"]

    print_separator()
    print_header(f"📩 {ticket_id}")
    print(f"{Colors.DIM}Ticket:{Colors.RESET} {ticket_text[:120]}{'...' if len(ticket_text) > 120 else ''}")
    print()

    # 1. Classify
    print(f"  {Colors.BOLD}{Colors.BLUE}▸ CLASSIFY{Colors.RESET}")
    try:
        classification = classify_ticket(ticket_text)
        print_json(classification)
    except Exception as e:
        classification = {"error": str(e)}
        print(f"  {Colors.RED}ERROR: {e}{Colors.RESET}")

    print()

    # 2. Draft Reply
    print(f"  {Colors.BOLD}{Colors.GREEN}▸ DRAFT REPLY{Colors.RESET}")
    try:
        reply = draft_reply(ticket_text, classification)
        print_json(reply)
    except Exception as e:
        print(f"  {Colors.RED}ERROR: {e}{Colors.RESET}")

    print()

    # 3. Extract Data
    print(f"  {Colors.BOLD}{Colors.YELLOW}▸ EXTRACT DATA{Colors.RESET}")
    try:
        extracted = extract_data(ticket_text)
        print_json(extracted)
    except Exception as e:
        print(f"  {Colors.RED}ERROR: {e}{Colors.RESET}")

    print()


def main():
    adversarial_mode = "--adversarial" in sys.argv

    if adversarial_mode:
        tickets = ADVERSARIAL_TICKETS
        banner_line1 = "║       SUPPORT OPS COPILOT — BREAKING IT                  ║"
        banner_line2 = "║          Adversarial Testing with Gemini                 ║"
        done_color = Colors.RED
        done_label = "Adversarial run complete!"
    else:
        tickets = SAMPLE_TICKETS
        banner_line1 = "║       SUPPORT OPS COPILOT — Stage 1: AI Service          ║"
        banner_line2 = "║          Processing Sample Tickets with Gemini           ║"
        done_color = Colors.GREEN
        done_icon = "✓"
        done_label = "Done!"

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔══════════════════════════════════════════════════════════╗")
    print(banner_line1)
    print(banner_line2)
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")

    total = len(tickets)
    print(f"Processing {total} tickets...\n")

    start = time.time()

    for i, ticket in enumerate(tickets, 1):
        print(f"{Colors.DIM}[{i}/{total}]{Colors.RESET}")
        process_ticket(ticket)

    elapsed = time.time() - start
    print_separator()
    print(f"\n{Colors.BOLD}{done_color} {done_label}{Colors.RESET} Processed {total} tickets in {elapsed:.1f}s")
    print()


if __name__ == "__main__":
    main()
