"""
Memori Models - Cấu trúc dữ liệu hợp nhất, config, và ontology.

Gộp từ:
- structs.py: Cấu trúc dữ liệu Memory (SemanticTriple, Entity, Memories, etc.)
- config.py: MemoriConfig và các cài đặt liên quan
- ontology.py: Chuẩn hóa và xác thực Predicate

Việc gộp này giúp giảm 3 file xuống 1 để dễ bảo trì.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from uuid import UUID

logger = logging.getLogger(__name__)


# =============================================================================
# PREDICATE ONTOLOGY (từ ontology.py)
# =============================================================================

PREDICATE_WHITELIST: Dict[tuple, List[str]] = {
    ("person", "person"): [
        "knows", "friend_of", "colleague_of", "related_to",
        "works_with", "reports_to", "married_to", "sibling_of"
    ],
    ("person", "location"): [
        "lives_in", "works_in", "from", "visited", "born_in", "moved_to"
    ],
    ("person", "organization"): [
        "works_at", "worked_at", "employed_by", "founded", "member_of", "studies_at"
    ],
    ("person", "concept"): [
        "likes", "dislikes", "prefers", "interested_in", "believes_in"
    ],
    ("person", "preference"): [
        "likes", "dislikes", "prefers", "interested_in", "wants"
    ],
    ("person", "programming_language"): [
        "uses", "knows", "learning", "expert_in", "prefers", "likes", "dislikes"
    ],
    ("person", "technology"): [
        "uses", "knows", "learning", "expert_in", "prefers", "likes"
    ],
    ("person", "skill"): [
        "has", "learning", "expert_in", "practices"
    ],
    ("person", "age"): ["is"],
    ("person", "occupation"): ["is", "works_as"],
    ("person", "nationality"): ["is", "from"],
}

PREDICATE_SYNONYMS: Dict[str, str] = {
    "resides_in": "lives_in", "living_in": "lives_in", "staying_in": "lives_in",
    "located_in": "lives_in", "based_in": "works_in",
    "employed_at": "works_at", "working_at": "works_at", "works_for": "works_at",
    "employed_by": "works_at",
    "loves": "likes", "enjoys": "likes", "fond_of": "likes", "appreciates": "likes",
    "hates": "dislikes", "doesnt_like": "dislikes", "not_like": "dislikes",
    "familiar_with": "knows", "understands": "knows", "learned": "knows", "studied": "knows",
    "is_learning": "learning", "studying": "learning",
    "friend_with": "friend_of", "friends_with": "friend_of", "acquainted_with": "knows",
}


def normalize_predicate(
    predicate: str,
    subject_type: Optional[str] = None,
    object_type: Optional[str] = None,
) -> str:
    """Chuẩn hóa predicate về dạng chính tắc."""
    normalized = predicate.lower().strip().replace(" ", "_").replace("-", "_")
    
    if normalized in PREDICATE_SYNONYMS:
        normalized = PREDICATE_SYNONYMS[normalized]
        logger.debug(f"Đã chuẩn hóa predicate '{predicate}' -> '{normalized}'")
    
    if subject_type and object_type:
        key = (subject_type.lower(), object_type.lower())
        if key in PREDICATE_WHITELIST:
            allowed = PREDICATE_WHITELIST[key]
            if normalized not in allowed:
                for allowed_pred in allowed:
                    if normalized in allowed_pred or allowed_pred in normalized:
                        return allowed_pred
    
    return normalized


def validate_predicate(
    predicate: str,
    subject_type: Optional[str] = None,
    object_type: Optional[str] = None,
) -> bool:
    """Kiểm tra xem predicate có hợp lệ cho các loại entity đã cho không."""
    normalized = normalize_predicate(predicate, subject_type, object_type)
    
    if not subject_type or not object_type:
        return True
    
    key = (subject_type.lower(), object_type.lower())
    if key in PREDICATE_WHITELIST:
        return normalized in PREDICATE_WHITELIST[key]
    
    return True


def get_allowed_predicates(subject_type: str, object_type: str) -> List[str]:
    """Lấy danh sách các predicates được phép cho các loại entity đã cho."""
    key = (subject_type.lower(), object_type.lower())
    return PREDICATE_WHITELIST.get(key, [])


def suggest_predicate(
    predicate: str,
    subject_type: Optional[str] = None,
    object_type: Optional[str] = None,
) -> Optional[str]:
    """Gợi ý predicate hợp lệ tương tự như predicate đã cho."""
    if not subject_type or not object_type:
        return normalize_predicate(predicate)
    
    allowed = get_allowed_predicates(subject_type, object_type)
    if not allowed:
        return normalize_predicate(predicate)
    
    normalized = predicate.lower().strip()
    
    for allowed_pred in allowed:
        if normalized in allowed_pred or allowed_pred in normalized:
            return allowed_pred
    
    if normalized in PREDICATE_SYNONYMS:
        suggested = PREDICATE_SYNONYMS[normalized]
        if suggested in allowed:
            return suggested
    
    if subject_type == "person" and object_type in ("concept", "preference"):
        return "likes"
    
    return allowed[0] if allowed else normalize_predicate(predicate)


# =============================================================================
# MEMORY STRUCTURES (từ structs.py)
# =============================================================================

@dataclass
class SemanticTriple:
    """Quan hệ Subject-Predicate-Object với hỗ trợ thời gian."""
    subject_name: Optional[str] = None
    subject_type: Optional[str] = None
    predicate: Optional[str] = None
    object_name: Optional[str] = None
    object_type: Optional[str] = None
    valid_at: Optional[Any] = None
    invalid_at: Optional[Any] = None
    confidence: float = 1.0


class Conversation:
    """Cấu trúc bộ nhớ hội thoại."""
    def __init__(self):
        self.summary: Optional[str] = None
    
    def configure_from_advanced_augmentation(self, json_: dict) -> "Conversation":
        conversation = json_.get("conversation", None)
        if conversation is None:
            return self
        self.summary = conversation.get("summary", None)
        return self


class Entity:
    """Cấu trúc bộ nhớ Entity với facts và semantic triples."""
    def __init__(self):
        self.facts: List[str] = []
        self.fact_embeddings: List[List[float]] = []
        self.fact_importance_scores: List[float] = []
        self.semantic_triples: List[SemanticTriple] = []
    
    def configure_from_advanced_augmentation(self, json_: dict) -> "Entity":
        entity = json_.get("entity", None)
        if entity is None:
            return self
        
        self.facts.extend(entity.get("facts", []))
        self.fact_embeddings.extend(entity.get("fact_embeddings", []))
        
        for entry in entity.get("semantic_triples", []) + entity.get("triples", []):
            triple = self._parse_semantic_triple(entry)
            if triple is not None:
                self.semantic_triples.append(triple)
                fact_text = f"{triple.subject_name} {triple.predicate} {triple.object_name}"
                self.facts.append(fact_text)
        
        return self
    
    def _parse_semantic_triple(self, entry: dict) -> Optional[SemanticTriple]:
        subject = entry.get("subject")
        predicate = entry.get("predicate")
        object_ = entry.get("object")
        
        if not subject or not predicate or not object_:
            return None
        
        subject_name = subject.get("name")
        subject_type = subject.get("type")
        object_name = object_.get("name")
        object_type = object_.get("type")
        
        if not all([subject_name, subject_type, object_name, object_type]):
            return None
        
        triple = SemanticTriple()
        triple.subject_name = subject_name
        triple.subject_type = subject_type.lower()
        triple.predicate = predicate
        triple.object_name = object_name
        triple.object_type = object_type.lower()
        
        return triple


class Process:
    """Cấu trúc bộ nhớ Process."""
    def __init__(self):
        self.attributes: List[str] = []
    
    def configure_from_advanced_augmentation(self, json_: dict) -> "Process":
        process = json_.get("process", None)
        if process is None:
            return self
        self.attributes.extend(process.get("attributes", []))
        return self


class Memories:
    """Cấu trúc bộ nhớ hoàn chỉnh kết hợp tất cả các loại bộ nhớ."""
    def __init__(self):
        self.conversation: Conversation = Conversation()
        self.entity: Entity = Entity()
        self.process: Process = Process()
    
    def configure_from_advanced_augmentation(self, json_: dict) -> "Memories":
        self.conversation = Conversation().configure_from_advanced_augmentation(json_)
        self.entity = Entity().configure_from_advanced_augmentation(json_)
        self.process = Process().configure_from_advanced_augmentation(json_)
        return self


@dataclass
class RecalledFact:
    """Một fact được gợi nhớ từ bộ nhớ với điểm tương đồng."""
    id: int
    content: str
    similarity: float
    lexical_score: float = 0.0
    rank_score: float = 0.0
    importance_score: float = 1.0


@dataclass
class AugmentationInput:
    """Dữ liệu đầu vào cho augmentation pipeline."""
    conversation_id: Optional[str] = None
    entity_id: Optional[str] = None
    process_id: Optional[str] = None
    conversation_messages: List[Dict[str, Any]] = field(default_factory=list)
    system_prompt: Optional[str] = None


# =============================================================================
# CONFIGURATION (từ config.py)
# =============================================================================

@dataclass
class MemoriCache:
    """Cache cho IDs để tránh lookup lặp lại."""
    conversation_id: Optional[int] = None
    entity_id: Optional[int] = None
    process_id: Optional[int] = None
    session_id: Optional[int] = None


@dataclass
class MemoriEmbeddings:
    """Cấu hình Embedding."""
    model: str = "all-MiniLM-L6-v2"
    fallback_dimension: int = 768
    use_existing_service: bool = True


@dataclass
class MemoriConfig:
    """Cấu hình cho quản lý bộ nhớ kiểu Memori."""
    entity_id: Optional[str] = None
    process_id: Optional[str] = None
    session_id: Optional[str] = None
    workspace_id: Optional[UUID] = None
    
    cache: MemoriCache = field(default_factory=MemoriCache)
    embeddings: MemoriEmbeddings = field(default_factory=MemoriEmbeddings)
    
    recall_facts_limit: int = 5
    recall_embeddings_limit: int = 1000
    recall_relevance_threshold: float = 0.1
    session_timeout_minutes: int = 30
    
    augmentation_enabled: bool = True
    max_workers: int = 50
    db_writer_batch_size: int = 100
    db_writer_batch_timeout: float = 0.1
    db_writer_queue_size: int = 1000
    
    thread_pool_executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(max_workers=15)
    )
    
    debug_truncate: bool = True
    storage: Any = None
    
    def reset_cache(self) -> "MemoriConfig":
        self.cache = MemoriCache()
        return self
    
    def is_test_mode(self) -> bool:
        return os.environ.get("MEMORI_TEST_MODE", None) is not None
    
    @classmethod
    def from_conversation(
        cls,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> "MemoriConfig":
        return cls(
            entity_id=str(user_id) if user_id else None,
            session_id=str(conversation_id),
            workspace_id=workspace_id,
        )
