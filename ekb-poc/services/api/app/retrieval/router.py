"""Question routing: document (hybrid search + graph), data (text-to-SQL via Trino) or mixed (both)."""

import logging

from .. import llm
from ..security import User

log = logging.getLogger("ekb.router")

ROUTES = ("document", "data", "mixed")

PROMPT = """Classify a question for a bank knowledge base. Return JSON {"route": "...", "reason": "..."}.

"document": answered by READING policy/product documents — rules, conditions, eligibility, a specific
  fee, rate or limit of one product, who approves what, what a policy requires, how a process works.
"data": answered by QUERYING records — counts, totals, averages, rankings, trends over months,
  lists across many documents (e.g. "list every product whose late fee is above SGD 90"), the document
  register (how many documents, which were updated, versions, statuses), workflow history (who
  approved what, pending reviews), portfolio metrics (accounts, balances, arrears rates by month),
  credit-exception counts.
"mixed": needs both, e.g. a policy rule AND a metric ("what is the arrears rate on personal loans and
  what does our hardship policy offer them?").

When unsure between document and mixed, choose document."""


def route(question: str, user: User) -> tuple[str, str]:
    try:
        out = llm.chat_json(
            [{"role": "system", "content": PROMPT}, {"role": "user", "content": question[:1000]}],
            actor=user.username,
            purpose="route",
            max_tokens=80,
        )
        r = str(out.get("route", "document")).lower()
        return (r if r in ROUTES else "document"), str(out.get("reason", ""))[:200]
    except Exception as e:  # routing must never fail the question
        log.warning("router fell back to document: %s", e)
        return "document", "router unavailable"
