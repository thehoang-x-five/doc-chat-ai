"""
Các hoạt động thời gian (Temporal Operations) cho Memori Knowledge Graph.

Lấy cảm hứng từ mô hình bi-temporal của Graphiti để xử lý:
- Trích xuất facts theo thời gian (valid_at, invalid_at)
- Phát hiện mâu thuẫn
- Vô hiệu hóa cạnh (Edge invalidation)

Các khái niệm chính:
- valid_at: Khi sự thật bắt đầu đúng trong thực tế
- invalid_at: Khi sự thật ngừng đúng trong thực tế
- expired_at: Khi triple bị vô hiệu hóa bởi một mâu thuẫn
"""

import logging
import json
import re
from datetime import datetime
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field

from app.services.memori.models import SemanticTriple

logger = logging.getLogger(__name__)


class EdgeDates(BaseModel):
    """Các mốc thời gian trích xuất từ hội thoại."""
    valid_at: Optional[str] = Field(None, description="ISO date khi sự thật bắt đầu đúng")
    invalid_at: Optional[str] = Field(None, description="ISO date khi sự thật ngừng đúng")


class ContradictedFacts(BaseModel):
    """Danh sách các chỉ số fact bị mâu thuẫn."""
    contradicted_facts: List[int] = Field(
        default_factory=list,
        description="Danh sách chỉ số của các fact bị mâu thuẫn bởi fact mới"
    )


async def extract_edge_dates(
    rag_service,
    edge: SemanticTriple,
    facts: List[str],
    reference_timestamp: datetime,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Trích xuất các mốc thời gian (valid_at, invalid_at) từ ngữ cảnh hội thoại.
    
    Args:
        rag_service: Service RAG để gọi LLM
        edge: Semantic triple cần trích xuất ngày tháng
        facts: Danh sách chuỗi facts làm ngữ cảnh
        reference_timestamp: Timestamp hiện tại làm tham chiếu
        
    Returns:
        Tuple chứa (valid_at, invalid_at) dạng datetime
        
    Example:
        User: "Trước đây tôi sống ở Hà Nội, nhưng từ tháng 6 năm nay tôi chuyển về Huế"
        
        Edge: "Tài Thế lives_in Hà Nội"
        Returns: (None, 2024-06-01)  # Ngừng đúng vào tháng 6
        
        Edge: "Tài Thế lives_in Huế"
        Returns: (2024-06-01, None)  # Bắt đầu đúng vào tháng 6
    """
    facts_text = "\n".join([f"- {fact}" for fact in facts])
    
    prompt = f"""Extract temporal information from the conversation.

FACT: "{edge.subject_name} {edge.predicate} {edge.object_name}"

CONVERSATION:
{facts_text}

REFERENCE TIMESTAMP: {reference_timestamp.isoformat()}

Task:
Determine when this fact became true (valid_at) and when it stopped being true (invalid_at).

Look for temporal indicators:
- "trước đây", "trước kia" → fact was true in the past
- "hiện tại", "bây giờ", "now" → fact is currently true
- "từ [date]" → fact became true at date
- "đến [date]", "until [date]" → fact stopped being true at date
- "không ... nữa", "no longer" → fact stopped being true recently

Return JSON:
{{
    "valid_at": "ISO date when fact became true, or null if unknown",
    "invalid_at": "ISO date when fact stopped being true, or null if still true"
}}

Examples:
- "Trước đây sống ở Hà Nội" → {{"valid_at": null, "invalid_at": "{reference_timestamp.isoformat()}"}}
- "Từ tháng 6 sống ở Huế" → {{"valid_at": "2024-06-01T00:00:00Z", "invalid_at": null}}
- "Không thích Python nữa" → {{"valid_at": null, "invalid_at": "{reference_timestamp.isoformat()}"}}

JSON:"""

    try:
        result = await rag_service._generate_answer_with_fallback(
            question=prompt,
            context="",
            max_tokens=512,
        )
        
        if result and result[0]:
            response_text = result[0]
            
            # Lưu để debug
            with open("temporal_extraction_response.txt", "w", encoding="utf-8") as f:
                f.write(response_text)
            
            # Parse JSON
            cleaned_text = re.sub(r'```(?:json)?\s*', '', response_text)
            cleaned_text = re.sub(r'```\s*', '', cleaned_text).strip()
            
            json_match = re.search(r'\{[\s\S]*?\}', cleaned_text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    
                    valid_at_str = data.get('valid_at')
                    invalid_at_str = data.get('invalid_at')
                    
                    valid_at = None
                    invalid_at = None
                    
                    if valid_at_str and valid_at_str != "null":
                        try:
                            valid_at = datetime.fromisoformat(valid_at_str.replace('Z', '+00:00'))
                        except ValueError as e:
                            logger.warning(f"Lỗi parse valid_at: {e}")
                    
                    if invalid_at_str and invalid_at_str != "null":
                        try:
                            invalid_at = datetime.fromisoformat(invalid_at_str.replace('Z', '+00:00'))
                        except ValueError as e:
                            logger.warning(f"Lỗi parse invalid_at: {e}")
                    
                    logger.info(f"Đã trích xuất dates cho '{edge.subject_name} {edge.predicate} {edge.object_name}': valid_at={valid_at}, invalid_at={invalid_at}")
                    return valid_at, invalid_at
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Lỗi parse temporal extraction response: {e}")
    except Exception as e:
        logger.warning(f"Temporal extraction thất bại: {e}")
    
    return None, None


async def get_edge_contradictions(
    rag_service,
    new_edge: SemanticTriple,
    existing_edges: List[SemanticTriple],
) -> List[SemanticTriple]:
    """
    Phát hiện các cạnh hiện có mâu thuẫn với cạnh mới.
    
    Args:
        rag_service: RAG service để gọi LLM
        new_edge: Semantic triple mới
        existing_edges: Danh sách semantic triple hiện có
        
    Returns:
        Danh sách các cạnh hiện có bị mâu thuẫn bởi cạnh mới
        
    Example:
        New: "Tài Thế lives_in Huế"
        Existing: ["Tài Thế lives_in Hà Nội", "Tài Thế likes Python"]
        Returns: ["Tài Thế lives_in Hà Nội"]  # Mâu thuẫn
    """
    if not existing_edges:
        return []
    
    # Xây dựng ngữ cảnh
    new_edge_text = f"{new_edge.subject_name} {new_edge.predicate} {new_edge.object_name}"
    
    existing_edges_text = []
    for i, edge in enumerate(existing_edges):
        existing_edges_text.append(
            f"{i}. {edge.subject_name} {edge.predicate} {edge.object_name}"
        )
    
    prompt = f"""Determine which existing facts contradict the new fact.

<NEW FACT>
{new_edge_text}
</NEW FACT>

<EXISTING FACTS>
{chr(10).join(existing_edges_text)}
</EXISTING FACTS>

Task:
Identify which EXISTING FACTS are contradicted by the NEW FACT.

A fact is contradicted if:
1. It makes an opposite claim (e.g., "lives_in X" vs "lives_in Y")
2. It states something that cannot be true if the new fact is true
3. It represents an outdated state

Do NOT mark as contradicted if:
- Facts are complementary (e.g., "likes Python" and "likes JavaScript")
- Facts are about different aspects (e.g., "lives_in Huế" and "works_in Hà Nội")
- Facts are both true (e.g., "knows Alice" and "knows Bob")

Return JSON:
{{
    "contradicted_facts": [0, 2, ...]  // List of indices, or empty list if none
}}

Examples:
- NEW: "lives_in Huế", EXISTING: ["lives_in Hà Nội"] → {{"contradicted_facts": [0]}}
- NEW: "dislikes Python", EXISTING: ["likes Python"] → {{"contradicted_facts": [0]}}
- NEW: "likes JavaScript", EXISTING: ["likes Python"] → {{"contradicted_facts": []}}

JSON:"""

    try:
        result = await rag_service._generate_answer_with_fallback(
            question=prompt,
            context="",
            max_tokens=512,
        )
        
        if result and result[0]:
            response_text = result[0]
            
            # Lưu để debug
            with open("contradiction_detection_response.txt", "w", encoding="utf-8") as f:
                f.write(response_text)
            
            # Parse JSON
            cleaned_text = re.sub(r'```(?:json)?\s*', '', response_text)
            cleaned_text = re.sub(r'```\s*', '', cleaned_text).strip()
            
            json_match = re.search(r'\{[\s\S]*?\}', cleaned_text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    
                    contradicted_indices = data.get('contradicted_facts', [])
                    contradicted_edges = [
                        existing_edges[i] 
                        for i in contradicted_indices 
                        if i < len(existing_edges)
                    ]
                    
                    if contradicted_edges:
                        logger.info(f"Tìm thấy {len(contradicted_edges)} cạnh mâu thuẫn cho '{new_edge_text}'")
                        for edge in contradicted_edges:
                            logger.info(f"  - {edge.subject_name} {edge.predicate} {edge.object_name}")
                    
                    return contradicted_edges
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Lỗi parse response phát hiện mâu thuẫn: {e}")
    except Exception as e:
        logger.warning(f"Phát hiện mâu thuẫn thất bại: {e}")
    
    return []


async def invalidate_contradicted_edges(
    session,
    contradicted_edges: List[SemanticTriple],
    invalidation_time: datetime,
) -> None:
    """
    Đánh dấu các cạnh bị mâu thuẫn là đã hết hạn trong database.
    
    Args:
        session: Database session
        contradicted_edges: Danh sách các cạnh cần vô hiệu hóa
        invalidation_time: Thời điểm vô hiệu hóa
    """
    from app.db.models import MemoriKnowledgeGraph
    from sqlalchemy import select, and_
    
    for edge in contradicted_edges:
        # Tìm cạnh trong database
        result = await session.execute(
            select(MemoriKnowledgeGraph).where(
                and_(
                    MemoriKnowledgeGraph.subject_name == edge.subject_name,
                    MemoriKnowledgeGraph.predicate == edge.predicate,
                    MemoriKnowledgeGraph.object_name == edge.object_name,
                    MemoriKnowledgeGraph.expired_at.is_(None),  # Chưa hết hạn
                )
            )
        )
        db_edge = result.scalar_one_or_none()
        
        if db_edge:
            db_edge.expired_at = invalidation_time
            logger.info(f"Đã vô hiệu hóa cạnh: {edge.subject_name} {edge.predicate} {edge.object_name}")
