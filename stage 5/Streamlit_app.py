"""
Streamlit UI — Support Ops Copilot (Stage 4: Agent + Tools).

Lets a reviewer:
  - Submit a raw ticket and watch it get classified + extracted
  - See the agent's tool-call plan
  - Approve / reject destructive tool actions (issue_refund, cancel_order) before they run
  - See the drafted reply, with RAG source citations
  - See low-confidence results flagged for human review
  - See a live tool-call audit log

Run with:
    streamlit run streamlit_app.py
"""

import os
import json

import streamlit as st
import pandas as pd

from src.ai_service import classify_ticket, extract_data, plan_agent_actions, draft_reply
from src.knowledge_base import initialise_knowledge_base
from src.tools import TOOL_REGISTRY
from src.tool_logger import ToolLogger
from src.agent import _execute_tool

try:
    from data.sample_tickets import SAMPLE_TICKETS
except ImportError:
    SAMPLE_TICKETS = []


# =============================================================================
# PAGE SETUP
# =============================================================================

st.set_page_config(page_title="Support Ops Copilot", page_icon="🎧", layout="wide")


def render_flag_badge(flagged: bool, confidence: float, label: str = "") -> None:
    prefix = f"{label} — " if label else ""
    if flagged:
        st.warning(f"🚩 {prefix}Flagged for human review · confidence {confidence:.2f}")
    else:
        st.success(f"✅ {prefix}Auto-approved · confidence {confidence:.2f}")


@st.cache_resource
def get_tool_logger() -> ToolLogger:
    """One shared ToolLogger instance for the whole app session (survives reruns)."""
    return ToolLogger()


@st.cache_resource
def get_kb_status(use_rag: bool):
    if not use_rag:
        return 0
    try:
        return initialise_knowledge_base()
    except Exception as e:
        return f"error: {e}"


# =============================================================================
# SESSION STATE
# =============================================================================

if "ticket_counter" not in st.session_state:
    st.session_state.ticket_counter = 0
if "current" not in st.session_state:
    st.session_state.current = None  # holds the in-progress / completed ticket dict

tool_logger = get_tool_logger()


# =============================================================================
# SIDEBAR — settings + audit log
# =============================================================================

with st.sidebar:
    st.header("⚙️ Settings")
    use_rag = st.toggle("Use knowledge base (RAG)", value=True)

    if not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY is not set. Add it to your .env file before submitting tickets.")

    kb_status = get_kb_status(use_rag)
    if use_rag:
        if isinstance(kb_status, str):
            st.warning(f"Knowledge base unavailable ({kb_status}) — replies will proceed without RAG context.")
        else:
            st.caption(f"📚 Knowledge base ready — {kb_status} chunks indexed.")
    else:
        st.caption("RAG disabled for this session.")

    st.caption(
        "Destructive tools (`issue_refund`, `cancel_order`) always pause for your "
        "approve / reject decision in the main panel — there is no auto-approve toggle here."
    )

    if st.button("🔄 Start a new ticket", use_container_width=True):
        st.session_state.current = None
        st.rerun()

    st.divider()
    st.header("🧾 Tool Call Audit Log")
    logs = tool_logger.get_all_logs()
    if logs:
        rows = [
            {
                "time": r.timestamp,
                "ticket": r.ticket_id,
                "tool": r.tool_name,
                "needs approval": r.requires_approval,
                "approved": r.approved,
                "success": (r.result or {}).get("success") if r.result else None,
                "error": r.error,
                "ms": round(r.duration_ms, 1),
            }
            for r in logs
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        summary = tool_logger.get_summary()
        st.caption(
            f"Total: {summary['total_tool_calls']} · Approved: {summary['approved']} · "
            f"Denied: {summary['denied']} · Success: {summary['successful']} · "
            f"Errors: {summary['errors']}"
        )
    else:
        st.caption("No tool calls yet this session.")


# =============================================================================
# MAIN — ticket submission
# =============================================================================

st.title("🎧 Support Ops Copilot")
st.caption("Submit a ticket → classify → plan tools → approve destructive actions → drafted reply.")

if SAMPLE_TICKETS:
    sample_labels = ["— none —"] + [f"{t['id']}: {t['text'][:60]}…" for t in SAMPLE_TICKETS]
    picked = st.selectbox("Load a sample ticket (optional)", sample_labels)
    if picked != "— none —":
        idx = sample_labels.index(picked) - 1
        st.session_state["ticket_input"] = SAMPLE_TICKETS[idx]["text"]

with st.form("ticket_form", clear_on_submit=False):
    ticket_text = st.text_area(
        "Raw ticket text",
        height=150,
        key="ticket_input",
        placeholder="Paste or type the customer's message here…",
    )
    submitted = st.form_submit_button("Submit Ticket", type="primary")

if submitted:
    if not ticket_text or not ticket_text.strip():
        st.error("Please enter some ticket text.")
    else:
        st.session_state.ticket_counter += 1
        ticket_id = f"TCK-{st.session_state.ticket_counter:04d}"

        classification, extracted, plan = None, None, None
        try:
            with st.spinner("Classifying ticket…"):
                classification = classify_ticket(ticket_text)
        except Exception as e:
            st.error(f"Classification failed: {e}")

        try:
            with st.spinner("Extracting structured data…"):
                extracted = extract_data(ticket_text)
        except Exception as e:
            st.error(f"Extraction failed: {e}")

        if classification and extracted:
            try:
                with st.spinner("Planning agent actions…"):
                    plan = plan_agent_actions(ticket_text, classification, extracted)
            except Exception as e:
                st.error(f"Agent planning failed: {e}")

        decisions = {}
        if plan:
            for i, tc in enumerate(plan.tool_calls):
                info = TOOL_REGISTRY.get(tc.tool_name, {})
                # Non-destructive tools are auto-approved (True); destructive tools
                # start undecided (None) until the reviewer clicks Approve/Reject.
                decisions[i] = True if not info.get("destructive", False) else None

        st.session_state.current = {
            "ticket_id": ticket_id,
            "ticket_text": ticket_text,
            "classification": classification,
            "extracted": extracted,
            "plan": plan,
            "decisions": decisions,
            "tool_results": None,
            "reply": None,
        }
        st.rerun()


# =============================================================================
# MAIN — active/completed ticket pipeline
# =============================================================================

cur = st.session_state.current

if cur:
    st.divider()
    st.subheader(f"Ticket {cur['ticket_id']}")
    st.text(cur["ticket_text"])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏷️ Classification")
        c = cur["classification"]
        if c:
            render_flag_badge(c.flagged_for_review, c.confidence)
            st.json(c.model_dump())
        else:
            st.error("Classification failed for this ticket.")

    with col2:
        st.markdown("### 🔎 Extracted Data")
        e = cur["extracted"]
        if e:
            render_flag_badge(e.flagged_for_review, e.confidence)
            st.json(e.model_dump())
        else:
            st.error("Extraction failed for this ticket.")

    st.markdown("### 🤖 Agent Plan")
    plan = cur["plan"]
    if plan is None:
        st.info("No agent plan available (classification or extraction failed).")
    elif not plan.tool_calls:
        st.info("The agent decided no tools are needed for this ticket.")
        st.caption(plan.reasoning)
    else:
        st.caption(f"Reasoning: {plan.reasoning}  ·  Plan confidence: {plan.confidence:.2f}")

        for i, tc in enumerate(plan.tool_calls):
            info = TOOL_REGISTRY.get(tc.tool_name, {})
            destructive = info.get("destructive", False)

            with st.container(border=True):
                header = f"**{i + 1}. `{tc.tool_name}`**"
                if destructive:
                    header += "&nbsp;&nbsp;🔴 **DESTRUCTIVE — needs approval**"
                st.markdown(header)
                st.caption(tc.reason)
                st.code(json.dumps(tc.arguments, indent=2), language="json")

                decision = cur["decisions"].get(i)
                if destructive:
                    if decision is None:
                        b1, b2 = st.columns(2)
                        if b1.button("✅ Approve", key=f"approve_{cur['ticket_id']}_{i}", use_container_width=True):
                            cur["decisions"][i] = True
                            st.rerun()
                        if b2.button("❌ Reject", key=f"reject_{cur['ticket_id']}_{i}", use_container_width=True):
                            cur["decisions"][i] = False
                            st.rerun()
                    elif decision is True:
                        st.success("Approved — will execute")
                    else:
                        st.error("Rejected — will not execute")
                else:
                    st.caption("Read-only tool — auto-approved")

    # --- Execute plan once all destructive calls have a decision ---
    if cur["tool_results"] is None:
        no_tools = plan is None or not plan.tool_calls
        all_decided = no_tools or all(v is not None for v in cur["decisions"].values())

        if not all_decided:
            st.info("⏳ Approve or reject every destructive action above to continue.")

        if st.button("▶️ Execute plan & draft reply", disabled=not all_decided, type="primary"):
            tool_results = []
            if plan:
                for i, tc in enumerate(plan.tool_calls):
                    decision = cur["decisions"].get(i)
                    result = _execute_tool(
                        tool_name=tc.tool_name,
                        arguments=tc.arguments,
                        ticket_id=cur["ticket_id"],
                        tool_logger=tool_logger,
                        auto_approve=False,
                        approved=decision,
                    )
                    if result:
                        tool_results.append(result)
            cur["tool_results"] = tool_results

            try:
                with st.spinner("Drafting reply…"):
                    reply = draft_reply(
                        cur["ticket_text"],
                        classification=cur["classification"],
                        use_rag=use_rag,
                        tool_results=tool_results if tool_results else None,
                    )
                cur["reply"] = reply
            except Exception as e:
                st.error(f"Reply drafting failed: {e}")

            st.rerun()

    # --- Tool results ---
    if cur["tool_results"] is not None:
        st.markdown("### 🛠️ Tool Results")
        if cur["tool_results"]:
            for r in cur["tool_results"]:
                if r["success"]:
                    with st.expander(f"✅ `{r['tool_name']}` — success", expanded=True):
                        st.json(r["data"])
                else:
                    with st.expander(f"❌ `{r['tool_name']}` — failed", expanded=True):
                        st.error(r["error"])
        else:
            st.caption("No tools were executed for this ticket.")

    # --- Drafted reply ---
    if cur["reply"]:
        st.markdown("### ✉️ Drafted Reply")
        reply = cur["reply"]
        render_flag_badge(reply.flagged_for_review, reply.confidence)

        st.text_input("Subject", value=reply.subject, disabled=True, key=f"subj_{cur['ticket_id']}")
        st.text_area("Body", value=reply.body, height=220, disabled=True, key=f"body_{cur['ticket_id']}")
        st.caption(f"Tone: {reply.tone}")

        st.markdown("#### 📚 Sources")
        if reply.sources:
            for s in reply.sources:
                st.markdown(f"- **{s.doc_name}** (page {s.page_number}, `{s.chunk_id}`) — _{s.chunk_preview}_")
        else:
            st.caption("No knowledge base sources were cited for this reply.")

        b1, b2 = st.columns(2)
        if b1.button("👍 Approve reply for sending", use_container_width=True):
            st.success("Reply approved for this session.")
        if b2.button("👎 Reject — needs human rewrite", use_container_width=True):
            st.warning("Reply flagged — a human should rewrite this before sending.")
else:
    st.info("Submit a ticket above to run it through the agent pipeline.")