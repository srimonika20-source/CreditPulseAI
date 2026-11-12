"""
AI Credit Analyst: natural-language Q&A grounded in computed metrics.

Answers are built only from metrics, findings and recommendations produced
by the analytics engines, and each answer cites its evidence. The default
implementation is offline (intent-matching + templates). Any optional LLM
integration will read credentials from the environment, never from code.

Status: placeholder, implemented in Phase 7.

Planned interface:
    - answer(question: str, context: AnalystContext) -> AnalystResponse
    - explain_finding(finding: Finding) -> AnalystResponse
    - summarise_portfolio(context: AnalystContext) -> AnalystResponse
"""

from __future__ import annotations

__all__: list[str] = []  # populated when implemented in Phase 7
