from typing import TypedDict, List, Dict, Any, Optional
from ..models.article import TopNewsReport


class NewsAgentState(TypedDict, total=False):
    """LangGraph agent state for the real-time news retrieval workflow."""
    task: str
    target_date: str
    reference_timestamp: str
    max_age_hours: float
    raw_worldwide: List[Dict[str, Any]]
    raw_india: List[Dict[str, Any]]
    validated_worldwide: List[Dict[str, Any]]
    validated_india: List[Dict[str, Any]]
    final_report: Optional[TopNewsReport]
    llm_provider_used: str
    fallback_occurred: bool
    error: Optional[str]
    logs: List[str]
