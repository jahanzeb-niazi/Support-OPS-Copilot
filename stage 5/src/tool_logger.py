"""
Tool Call Logger — Stage 4: Agent + Tools.
Audit logger for every tool invocation: inputs, outputs, approval decisions, errors.
Pure Python — no external dependencies beyond Pydantic.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ToolCallRecord:
    """A single audit log entry for a tool execution."""

    def __init__(
        self,
        ticket_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        requires_approval: bool,
    ):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.ticket_id = ticket_id
        self.tool_name = tool_name
        self.arguments = arguments
        self.requires_approval = requires_approval
        self.approved: Optional[bool] = None
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "ticket_id": self.ticket_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class ToolLogger:
    """
    Collects and manages audit logs for all tool invocations.
    One instance per application run.
    """

    def __init__(self):
        self._logs: list[ToolCallRecord] = []

    def create_record(
        self,
        ticket_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        requires_approval: bool,
    ) -> ToolCallRecord:
        """Create a new log record (call this BEFORE executing the tool)."""
        record = ToolCallRecord(
            ticket_id=ticket_id,
            tool_name=tool_name,
            arguments=arguments,
            requires_approval=requires_approval,
        )
        self._logs.append(record)
        return record

    def record_approval(self, record: ToolCallRecord, approved: bool) -> None:
        """Log the approval decision."""
        record.approved = approved
        status = "APPROVED" if approved else "DENIED"
        logger.info(
            f"[APPROVAL] {record.tool_name} → {status} "
            f"(ticket: {record.ticket_id})"
        )

    def record_result(
        self,
        record: ToolCallRecord,
        result: dict,
        duration_ms: float,
    ) -> None:
        """Log a successful tool execution result."""
        record.result = result
        record.duration_ms = duration_ms
        record.approved = True  # if we got a result, it was approved

        success = result.get("success", False)
        level = "INFO" if success else "WARNING"
        logger.log(
            logging.getLevelName(level),
            f"[TOOL RESULT] {record.tool_name} "
            f"({'success' if success else 'failed'}) "
            f"in {duration_ms:.1f}ms (ticket: {record.ticket_id})"
        )

    def record_error(
        self,
        record: ToolCallRecord,
        error: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Log a tool execution error."""
        record.error = error
        record.duration_ms = duration_ms
        logger.error(
            f"[TOOL ERROR] {record.tool_name}: {error} "
            f"(ticket: {record.ticket_id})"
        )

    def get_logs_for_ticket(self, ticket_id: str) -> list[ToolCallRecord]:
        """Get all log records for a specific ticket."""
        return [r for r in self._logs if r.ticket_id == ticket_id]

    def get_all_logs(self) -> list[ToolCallRecord]:
        """Get all log records."""
        return list(self._logs)

    def get_summary(self) -> dict:
        """Get summary statistics across all tool calls."""
        total = len(self._logs)
        approved = sum(1 for r in self._logs if r.approved is True)
        denied = sum(1 for r in self._logs if r.approved is False)
        errors = sum(1 for r in self._logs if r.error is not None)
        successful = sum(
            1 for r in self._logs
            if r.result and r.result.get("success", False)
        )

        return {
            "total_tool_calls": total,
            "approved": approved,
            "denied": denied,
            "successful": successful,
            "errors": errors,
        }
