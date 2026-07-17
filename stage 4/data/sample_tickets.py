"""
Sample support tickets for testing the AI Service functions.
Stage 4 adds tickets that naturally trigger different tool actions.
"""

SAMPLE_TICKETS = [
    {
        "id": "TICKET-001",
        "text": "Hi, my name is James Carter. I was charged $49.99 for a subscription I cancelled last month. My account email is james.carter@gmail.com. Order reference is #SUB-20240. Please refund me.",
    },
    {
        "id": "TICKET-002",
        "text": "My package was supposed to arrive on July 10th but the tracking hasn't updated since July 7th. It's stuck at 'In Transit' for 3 days now. Order #PKG-88210.",
    },
    {
        "id": "TICKET-003",
        "text": "I need to cancel my order #ORD-55123 immediately. I found a better deal elsewhere and it hasn't shipped yet. Please cancel and confirm.",
    },
    {
        "id": "TICKET-004",
        "text": "My Blue Wireless Headphone from order #78432 has a cracked ear cup. I've only had it for a few months. Is this covered under warranty? I'd like a replacement.",
    },
    {
        "id": "TICKET-005",
        "text": "I've been trying to resolve a billing dispute for 3 weeks now. Nobody responds to my emails, my account keeps getting charged, and I'm considering legal action. This is unacceptable. I want to speak to a manager NOW.",
    },
]
