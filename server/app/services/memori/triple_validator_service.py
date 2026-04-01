"""
Triple Validator & Cleaner - Validation chuẩn production sử dụng LLM như một CRITIC-ONLY.

Các nguyên tắc chính:
1. LLM làm CRITIC-ONLY: chỉ đưa ra quyết định ACCEPT/REJECT/SWAP/MERGE
2. LLM KHÔNG được rewrite entity names
3. Tách literal attributes vs entity relationships
4. Giữ nguyên dữ liệu triple gốc, chỉ áp dụng các hành động

Lấy cảm hứng từ phương pháp của Graphiti về xác thực knowledge graph.
"""
import logging
import json
import re
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.memori.models import SemanticTriple

logger = logging.getLogger(__name__)


class TripleAction(str, Enum):
    """Các hành động mà LLM critic có thể quyết định."""
    ACCEPT = "ACCEPT"  # Giữ nguyên
    REJECT = "REJECT"  # Xóa (vô nghĩa, dư thừa)
    SWAP_SUBJ_OBJ = "SWAP_SUBJ_OBJ"  # Đảo ngược mối quan hệ
    MERGE_REDUNDANT = "MERGE_REDUNDANT"  # Gộp với một triple khác
    CONVERT_TO_ATTRIBUTE = "CONVERT_TO_ATTRIBUTE"  # Nên là thuộc tính entity


class TripleDecision(BaseModel):
    """Quyết định của LLM cho một triple đơn lẻ."""
    triple_index: int = Field(description="Index của triple (0-based)")
    action: TripleAction = Field(description="Hành động cần thực hiện")
    confidence: float = Field(ge=0.0, le=1.0, description="Độ tin cậy")
    reason: str = Field(description="Giải thích ngắn gọn")
    merge_with_index: Optional[int] = Field(None, description="Index để gộp cùng")


class TripleValidator:
    """
    Xác thực và làm sạch semantic triples sử dụng LLM như một CRITIC-ONLY.
    
    LLM chỉ đưa ra quyết định - chúng ta áp dụng chúng để giữ nguyên dữ liệu gốc.
    """
    
    # Các loại Literal nên là attributes, không phải nodes
    LITERAL_TYPES = {
        "concept", "preference", "number", "date", "time", 
        "age", "color", "size", "quantity", "description"
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    def is_literal_attribute(self, triple: SemanticTriple) -> bool:
        """Kiểm tra nếu triple object là một literal (nên là attribute, không phải node)."""
        if triple.object_type and triple.object_type.lower() in self.LITERAL_TYPES:
            return True
        
        # Kiểm tra các mẫu predicate
        attribute_predicates = {"is", "has", "prefers", "likes"}
        if triple.predicate.lower() in attribute_predicates:
            entity_types = {"person", "organization", "location", "city", "country"}
            if not triple.object_type or triple.object_type.lower() not in entity_types:
                return True
        
        return False
    
    async def validate_with_llm_critic(
        self,
        triples: List[SemanticTriple],
        entity_name: str,
        facts: List[str],
    ) -> List[TripleDecision]:
        """
        Sử dụng LLM như critic để đưa ra quyết định (KHÔNG rewrite).
        """
        if not triples:
            return []
        
        # Xây dựng danh sách triples
        triples_text = []
        for i, t in enumerate(triples):
            triples_text.append(
                f"{i}. {t.subject_name} ({t.subject_type or '?'}) "
                f"--[{t.predicate}]--> "
                f"{t.object_name} ({t.object_type or '?'})"
            )
        
        facts_text = "\n".join([f"- {fact}" for fact in facts])
        
        critic_prompt = f"""You are a knowledge graph critic. Review triples and make decisions.

Entity: {entity_name}

Facts:
{facts_text}

Triples:
{chr(10).join(triples_text)}

For each triple, decide ONE action:
- ACCEPT: Valid relationship
- REJECT: Nonsensical (e.g., "X is tên Y")
- SWAP_SUBJ_OBJ: Reversed (e.g., "bạn tôi is Khanh" → swap)
- MERGE_REDUNDANT: Redundant with another (e.g., "lives_in Vietnam" + "lives_in Huế")
- CONVERT_TO_ATTRIBUTE: Object is literal attribute

CRITICAL: DO NOT rewrite entity names. Keep original text.

Return JSON array:
[
  {{"triple_index": 0, "action": "ACCEPT", "confidence": 0.95, "reason": "Valid"}},
  {{"triple_index": 1, "action": "REJECT", "confidence": 0.99, "reason": "Nonsensical"}},
  {{"triple_index": 2, "action": "SWAP_SUBJ_OBJ", "confidence": 0.90, "reason": "Reversed"}},
  {{"triple_index": 3, "action": "MERGE_REDUNDANT", "confidence": 0.85, "reason": "Redundant", "merge_with_index": 4}}
]

JSON:"""

        try:
            from app.services.core.rag import RAGService
            
            rag = await RAGService.get_instance(self.session)
            result = await rag._generate_answer_with_fallback(
                question=critic_prompt,
                context="",
                max_tokens=2048,
            )
            
            if result and result[0]:
                response_text = result[0]
                
                # Lưu để debug
                with open("triple_critic_response.txt", "w", encoding="utf-8") as f:
                    f.write(response_text)
                
                # Parse JSON - tìm array cuối cùng
                cleaned_text = re.sub(r'```(?:json)?\s*', '', response_text)
                cleaned_text = re.sub(r'```\s*', '', cleaned_text).strip()
                
                json_matches = list(re.finditer(r'\[[\s\S]*?\]', cleaned_text))
                if json_matches:
                    json_match = json_matches[-1]
                    try:
                        data = json.loads(json_match.group())
                        
                        decisions = []
                        for item in data:
                            if isinstance(item, dict):
                                try:
                                    decision = TripleDecision(
                                        triple_index=item.get("triple_index", 0),
                                        action=TripleAction(item.get("action", "ACCEPT")),
                                        confidence=item.get("confidence", 0.5),
                                        reason=item.get("reason", ""),
                                        merge_with_index=item.get("merge_with_index"),
                                    )
                                    decisions.append(decision)
                                except Exception as e:
                                    logger.warning(f"Lỗi parse decision: {e}")
                        
                        logger.info(f"LLM critic: {len(decisions)} quyết định")
                        return decisions
                    except json.JSONDecodeError as e:
                        logger.warning(f"Lỗi parse critic response: {e}")
        except Exception as e:
            logger.warning(f"LLM critic thất bại: {e}")
        
        # Fallback: chấp nhận tất cả
        return [
            TripleDecision(
                triple_index=i,
                action=TripleAction.ACCEPT,
                confidence=0.5,
                reason="Fallback"
            )
            for i in range(len(triples))
        ]
    
    def apply_decisions(
        self,
        triples: List[SemanticTriple],
        decisions: List[TripleDecision],
    ) -> List[SemanticTriple]:
        """
        Áp dụng các quyết định của LLM vào triples gốc (giữ nguyên tên entity).
        """
        result_triples = []
        rejected_indices = set()
        merged_indices = set()
        
        for decision in decisions:
            idx = decision.triple_index
            if idx >= len(triples):
                continue
            
            triple = triples[idx]
            
            if decision.action == TripleAction.ACCEPT:
                result_triples.append(triple)
            
            elif decision.action == TripleAction.REJECT:
                rejected_indices.add(idx)
                logger.info(f"REJECT: {triple.subject_name} --[{triple.predicate}]--> {triple.object_name}")
            
            elif decision.action == TripleAction.SWAP_SUBJ_OBJ:
                swapped = SemanticTriple(
                    subject_name=triple.object_name,
                    subject_type=triple.object_type,
                    predicate=triple.predicate,
                    object_name=triple.subject_name,
                    object_type=triple.subject_type,
                )
                result_triples.append(swapped)
                logger.info(f"SWAP: {triple.subject_name} <-> {triple.object_name}")
            
            elif decision.action == TripleAction.MERGE_REDUNDANT:
                if decision.merge_with_index is not None:
                    merged_indices.add(idx)
                    logger.info(f"MERGE: {triple.subject_name} --[{triple.predicate}]--> {triple.object_name}")
                else:
                    result_triples.append(triple)
            
            elif decision.action == TripleAction.CONVERT_TO_ATTRIBUTE:
                # Bỏ qua triple này - nó nên được lưu là attribute, không phải relationship
                logger.info(f"CONVERT_TO_ATTRIBUTE: {triple.subject_name}.{triple.predicate} = {triple.object_name} (xóa khỏi graph)")
        
        logger.info(f"Đã áp dụng: {len(result_triples)} giữ, {len(rejected_indices)} loại, {len(merged_indices)} gộp")
        return result_triples
    
    def filter_invalid_triples(
        self,
        triples: List[SemanticTriple],
        entity_name: str,
    ) -> List[SemanticTriple]:
        """Lọc dựa trên quy tắc cho các triples không hợp lệ rõ ràng."""
        valid_triples = []
        
        for triple in triples:
            # Bỏ qua nếu rỗng
            if not triple.subject_name or not triple.predicate or not triple.object_name:
                continue
            
            # Bỏ qua "is tên X"
            if triple.predicate.lower() == "is" and "tên" in triple.object_name.lower():
                logger.info(f"Đã lọc: {triple.subject_name} is {triple.object_name} (name pattern)")
                continue
            
            # Bỏ qua tự tham chiếu (self-referential)
            if triple.subject_name.lower() == triple.object_name.lower():
                logger.info(f"Đã lọc: {triple.subject_name} {triple.predicate} {triple.object_name} (self-ref)")
                continue
            
            valid_triples.append(triple)
        
        if len(valid_triples) < len(triples):
            logger.info(f"Đã lọc theo quy tắc: {len(triples) - len(valid_triples)} triples")
        
        return valid_triples
    
    def deduplicate_triples(
        self,
        triples: List[SemanticTriple],
    ) -> List[SemanticTriple]:
        """Loại bỏ các triples trùng lặp."""
        seen = set()
        unique_triples = []
        
        for triple in triples:
            key = (
                triple.subject_name.lower(),
                triple.predicate.lower(),
                triple.object_name.lower(),
            )
            if key not in seen:
                seen.add(key)
                unique_triples.append(triple)
        
        if len(unique_triples) < len(triples):
            logger.info(f"Đã deduplicate: {len(triples) - len(unique_triples)} triples")
        
        return unique_triples
    
    async def process_triples(
        self,
        triples: List[SemanticTriple],
        entity_name: str,
        facts: List[str],
        use_llm: bool = True,
    ) -> List[SemanticTriple]:
        """
        Full pipeline: lọc → chuẩn hóa predicates → deduplicate → LLM critic → áp dụng quyết định.
        """
        logger.info(f"Đang xử lý {len(triples)} triples...")
        
        # Step 1: Rule-based filtering
        triples = self.filter_invalid_triples(triples, entity_name)
        
        # Step 2: Predicate normalization using ontology
        try:
            from app.services.memori.models import normalize_predicate
            
            for triple in triples:
                original_pred = triple.predicate
                normalized = normalize_predicate(
                    triple.predicate,
                    triple.subject_type,
                    triple.object_type,
                )
                if normalized != original_pred:
                    triple.predicate = normalized
                    logger.debug(f"Đã chuẩn hóa predicate: '{original_pred}' -> '{normalized}'")
        except ImportError:
            logger.warning("Ontology module không khả dụng, bỏ qua chuẩn hóa predicate")
        except Exception as e:
            logger.warning(f"Chuẩn hóa predicate thất bại: {e}")
        
        # Step 3: Deduplication
        triples = self.deduplicate_triples(triples)
        
        # Step 4: LLM critic (optional)
        if use_llm and triples:
            decisions = await self.validate_with_llm_critic(triples, entity_name, facts)
            triples = self.apply_decisions(triples, decisions)
        
        logger.info(f"Final: {len(triples)} clean triples")
        return triples

