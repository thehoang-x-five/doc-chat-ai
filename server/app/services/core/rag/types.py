
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from uuid import UUID

@dataclass
class PolicyEvaluationResult:
    policy_mode: str = "standard"
    best_score: float = 0.0
    fallback_used: bool = False
    threshold: float = 0.0
    should_answer: bool = True

@dataclass
class Citation:
    chunk_id: str
    content: str = ""
    source: str = ""
    score: float = 0.0
    document_id: Optional[UUID] = None
    document_title: str = ""
    page: Optional[int] = None
    quote: str = ""

@dataclass
class RAGResponse:
    answer: str
    pattern: str = "auto"
    provider: str = "unknown"
    model: str = "unknown"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    policy_evaluation: PolicyEvaluationResult = field(default_factory=PolicyEvaluationResult)
    citations: List[Citation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
