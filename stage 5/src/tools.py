"""
Mock tools module — Stage 4: Agent + Tools.
Simulates real backend operations that a support agent would perform.
Each tool returns a structured result dict with success/data/error fields.
"""

import random
import logging
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# MOCK DATA STORE
# =============================================================================

MOCK_ORDERS = {
    "#SUB-20240": {
        "order_id": "#SUB-20240",
        "customer": "James Carter",
        "email": "james.carter@gmail.com",
        "product": "Premium Subscription (Monthly)",
        "status": "active",
        "amount": 49.99,
        "date": "2026-06-15",
        "refundable": True,
    },
    "#PKG-88210": {
        "order_id": "#PKG-88210",
        "customer": "Unknown",
        "product": "Wireless Earbuds Pro",
        "status": "in_transit",
        "amount": 79.99,
        "date": "2026-07-05",
        "tracking": "TRACK-882100045",
        "refundable": False,
    },
    "#45231": {
        "order_id": "#45231",
        "customer": "Alex",
        "product": "Smart Watch X200",
        "status": "delivered",
        "amount": 199.99,
        "date": "2026-06-28",
        "refundable": True,
    },
    "#78432": {
        "order_id": "#78432",
        "customer": "Sarah Johnson",
        "email": "sarah.j@email.com",
        "product": "Blue Wireless Headphone",
        "status": "delivered",
        "amount": 59.99,
        "date": "2026-06-05",
        "refundable": True,
    },
    "#ORD-55123": {
        "order_id": "#ORD-55123",
        "customer": "Emily Chen",
        "product": "Laptop Stand Pro",
        "status": "processing",
        "amount": 34.99,
        "date": "2026-07-14",
        "refundable": True,
    },
    "#ORD-99001": {
        "order_id": "#ORD-99001",
        "customer": "David Kim",
        "product": "USB-C Hub 7-in-1",
        "status": "shipped",
        "amount": 45.00,
        "date": "2026-07-10",
        "tracking": "TRACK-990010022",
        "refundable": True,
    },
}

MOCK_WARRANTIES = {
    "#78432": {
        "order_id": "#78432",
        "product": "Blue Wireless Headphone",
        "warranty_status": "active",
        "warranty_expiry": "2027-06-05",
        "coverage": "Manufacturing defects, battery failure",
    },
    "#45231": {
        "order_id": "#45231",
        "product": "Smart Watch X200",
        "warranty_status": "active",
        "warranty_expiry": "2028-06-28",
        "coverage": "Manufacturing defects, screen damage, water damage",
    },
    "#ORD-99001": {
        "order_id": "#ORD-99001",
        "product": "USB-C Hub 7-in-1",
        "warranty_status": "expired",
        "warranty_expiry": "2026-07-10",
        "coverage": "Manufacturing defects only",
    },
}


# =============================================================================
# TOOL FUNCTIONS
# =============================================================================

def lookup_order_status(order_id: str) -> dict[str, Any]:
    """
    Look up the current status of an order by its order ID.
    Read-only — does NOT require human approval.
    """
    if not order_id or not order_id.strip():
        return {
            "success": False,
            "data": None,
            "error": "order_id is required but was empty.",
        }

    # Normalise: add '#' if missing
    clean_id = order_id.strip()
    if not clean_id.startswith("#"):
        clean_id = "#" + clean_id

    order = MOCK_ORDERS.get(clean_id)
    if order is None:
        return {
            "success": False,
            "data": None,
            "error": f"Order '{clean_id}' not found in system.",
        }

    return {
        "success": True,
        "data": {
            "order_id": order["order_id"],
            "customer": order["customer"],
            "product": order["product"],
            "status": order["status"],
            "amount": order["amount"],
            "date": order["date"],
            "tracking": order.get("tracking"),
        },
        "error": None,
    }


def check_warranty(order_id: str) -> dict[str, Any]:
    """
    Check the warranty status for a product/order.
    Read-only — does NOT require human approval.
    """
    if not order_id or not order_id.strip():
        return {
            "success": False,
            "data": None,
            "error": "order_id is required but was empty.",
        }

    clean_id = order_id.strip()
    if not clean_id.startswith("#"):
        clean_id = "#" + clean_id

    warranty = MOCK_WARRANTIES.get(clean_id)
    if warranty is None:
        return {
            "success": False,
            "data": None,
            "error": f"No warranty record found for order '{clean_id}'.",
        }

    return {
        "success": True,
        "data": warranty,
        "error": None,
    }


def issue_refund(order_id: str, reason: str = "") -> dict[str, Any]:
    """
    Process a refund for the given order.
    DESTRUCTIVE — requires human approval before execution.
    """
    if not order_id or not order_id.strip():
        return {
            "success": False,
            "data": None,
            "error": "order_id is required but was empty.",
        }

    clean_id = order_id.strip()
    if not clean_id.startswith("#"):
        clean_id = "#" + clean_id

    order = MOCK_ORDERS.get(clean_id)
    if order is None:
        return {
            "success": False,
            "data": None,
            "error": f"Order '{clean_id}' not found — cannot issue refund.",
        }

    if not order.get("refundable", False):
        return {
            "success": False,
            "data": None,
            "error": f"Order '{clean_id}' is not eligible for refund (status: {order['status']}).",
        }

    # Simulate refund processing
    refund_id = f"REF-{random.randint(100000, 999999)}"

    return {
        "success": True,
        "data": {
            "refund_id": refund_id,
            "order_id": clean_id,
            "amount": order["amount"],
            "reason": reason or "Customer requested refund",
            "status": "processing",
            "estimated_days": "3-5 business days",
        },
        "error": None,
    }


def cancel_order(order_id: str, reason: str = "") -> dict[str, Any]:
    """
    Cancel an active order.
    DESTRUCTIVE — requires human approval before execution.
    """
    if not order_id or not order_id.strip():
        return {
            "success": False,
            "data": None,
            "error": "order_id is required but was empty.",
        }

    clean_id = order_id.strip()
    if not clean_id.startswith("#"):
        clean_id = "#" + clean_id

    order = MOCK_ORDERS.get(clean_id)
    if order is None:
        return {
            "success": False,
            "data": None,
            "error": f"Order '{clean_id}' not found — cannot cancel.",
        }

    # Only processing/active orders can be cancelled
    if order["status"] not in ("processing", "active"):
        return {
            "success": False,
            "data": None,
            "error": (
                f"Order '{clean_id}' cannot be cancelled "
                f"(current status: {order['status']}). "
                f"Only 'processing' or 'active' orders can be cancelled."
            ),
        }

    return {
        "success": True,
        "data": {
            "order_id": clean_id,
            "previous_status": order["status"],
            "new_status": "cancelled",
            "reason": reason or "Customer requested cancellation",
        },
        "error": None,
    }


def escalate_to_human(ticket_id: str, reason: str = "",
                      urgency: str = "medium") -> dict[str, Any]:
    """
    Escalate a ticket to a human agent for manual handling.
    NOT destructive — auto-approved.
    """
    if not ticket_id or not ticket_id.strip():
        return {
            "success": False,
            "data": None,
            "error": "ticket_id is required but was empty.",
        }

    escalation_id = f"ESC-{random.randint(10000, 99999)}"

    return {
        "success": True,
        "data": {
            "escalation_id": escalation_id,
            "ticket_id": ticket_id.strip(),
            "assigned_to": "Human Agent Queue",
            "urgency": urgency,
            "reason": reason or "Agent determined human review is needed",
            "estimated_response": "Within 1 hour" if urgency in ("critical", "high") else "Within 4 hours",
        },
        "error": None,
    }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

TOOL_REGISTRY = {
    "lookup_order_status": {
        "fn": lookup_order_status,
        "destructive": False,
        "description": "Look up the current status of an order by order ID. Returns order details including status, product, amount, and tracking info.",
        "parameters": "order_id (str, required): The order ID to look up (e.g. '#SUB-20240').",
    },
    "check_warranty": {
        "fn": check_warranty,
        "destructive": False,
        "description": "Check the warranty status for a product/order. Returns warranty expiry and coverage details.",
        "parameters": "order_id (str, required): The order ID to check warranty for.",
    },
    "issue_refund": {
        "fn": issue_refund,
        "destructive": True,
        "description": "Process a refund for a given order. Returns refund ID and estimated processing time. DESTRUCTIVE: requires human approval.",
        "parameters": "order_id (str, required): The order ID to refund. reason (str, optional): Reason for the refund.",
    },
    "cancel_order": {
        "fn": cancel_order,
        "destructive": True,
        "description": "Cancel an active or processing order. DESTRUCTIVE: requires human approval.",
        "parameters": "order_id (str, required): The order ID to cancel. reason (str, optional): Reason for cancellation.",
    },
    "escalate_to_human": {
        "fn": escalate_to_human,
        "destructive": False,
        "description": "Escalate the ticket to a human agent for manual handling. Use when the AI cannot confidently resolve the issue.",
        "parameters": "ticket_id (str, required): The ticket ID. reason (str, optional): Why escalation is needed. urgency (str, optional): 'critical', 'high', 'medium', or 'low'.",
    },
}


def get_tools_description() -> str:
    """Format all available tools into a text description for the LLM prompt."""
    lines = []
    for name, info in TOOL_REGISTRY.items():
        destructive_tag = " [DESTRUCTIVE — requires human approval]" if info["destructive"] else ""
        lines.append(f"- {name}{destructive_tag}")
        lines.append(f"  Description: {info['description']}")
        lines.append(f"  Parameters: {info['parameters']}")
        lines.append("")
    return "\n".join(lines)
