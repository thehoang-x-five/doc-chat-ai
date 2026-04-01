"""
Tìm kiếm ngữ nghĩa (Semantic Search) cho Memori Facts.
Sao chép từ project Memori: memori/_search.py

Tính năng:
- Tìm kiếm vector tương đồng với FAISS
- Reranking theo từ vựng (tìm kiếm lai: 85% ngữ nghĩa + 15% từ vựng)
- Điểm trùng lặp token có trọng số IDF
"""

import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.services.memori.extraction import parse_embedding_from_db

logger = logging.getLogger(__name__)


def find_similar_embeddings(
    embeddings: List[Tuple[int, Any]],
    query_embedding: List[float],
    limit: int = 5,
) -> List[Tuple[int, float]]:
    """
    Tìm các embeddings tương đồng nhất sử dụng FAISS cosine similarity.
    Sao chép từ Memori: Sử dụng FAISS để tìm kiếm tương đồng hiệu quả.
    
    Args:
        embeddings: Danh sách các tuple (id, embedding_raw)
        query_embedding: Query embedding dưới dạng list float
        limit: Số lượng kết quả trả về
        
    Returns:
        Danh sách các tuple (id, similarity_score), sắp xếp giảm dần theo độ tương đồng
    """
    try:
        import faiss
    except ImportError:
        logger.warning("FAISS chưa được cài đặt, sử dụng numpy fallback")
        return _find_similar_numpy(embeddings, query_embedding, limit)
    
    if not embeddings:
        logger.debug("find_similar_embeddings được gọi với danh sách embeddings rỗng")
        return []
    
    query_dim = len(query_embedding)
    if query_dim == 0:
        return []
    
    embeddings_list = []
    id_list = []
    
    for fact_id, raw in embeddings:
        try:
            parsed = parse_embedding_from_db(raw)
            if not parsed:
                continue
            parsed_arr = np.array(parsed, dtype=np.float32)
            if parsed_arr.ndim != 1 or parsed_arr.shape[0] != query_dim:
                continue
            embeddings_list.append(parsed_arr)
            id_list.append(fact_id)
        except Exception:
            continue
    
    if not embeddings_list:
        logger.debug("Không có embeddings hợp lệ sau khi parse")
        return []
    
    logger.debug("Đang xây dựng FAISS index với %d embeddings", len(embeddings_list))
    try:
        embeddings_array = np.stack(embeddings_list, axis=0)
    except ValueError:
        return []
    
    # Chuẩn hóa để tính cosine similarity
    faiss.normalize_L2(embeddings_array)
    query_array = np.asarray([query_embedding], dtype=np.float32)
    
    if embeddings_array.shape[1] != query_array.shape[1]:
        logger.debug(
            "Kích thước embedding không khớp: db=%d, query=%d",
            embeddings_array.shape[1],
            query_array.shape[1],
        )
        return []
    
    faiss.normalize_L2(query_array)
    
    # Xây dựng FAISS index (Inner Product = Cosine Similarity sau khi chuẩn hóa)
    index = faiss.IndexFlatIP(embeddings_array.shape[1])
    index.add(embeddings_array)
    
    k = min(limit, len(embeddings_array))
    similarities, indices = index.search(query_array, k)
    
    results = []
    for result_idx, embedding_idx in enumerate(indices[0]):
        if 0 <= embedding_idx < len(id_list):
            results.append((id_list[embedding_idx], float(similarities[0][result_idx])))
    
    if results:
        scores = [round(score, 3) for _, score in results]
        logger.debug(
            "FAISS similarity search hoàn tất - top %d kết quả: %s",
            len(results),
            scores,
        )
    
    return results


def _find_similar_numpy(
    embeddings: List[Tuple[int, Any]],
    query_embedding: List[float],
    limit: int = 5,
) -> List[Tuple[int, float]]:
    """
    Fallback tìm kiếm tương đồng bằng numpy (khi không có FAISS).
    """
    if not embeddings:
        return []
    
    query_arr = np.array(query_embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query_arr)
    if query_norm == 0:
        return []
    query_arr = query_arr / query_norm
    
    results = []
    for fact_id, raw in embeddings:
        try:
            parsed = parse_embedding_from_db(raw)
            if not parsed:
                continue
            emb_arr = np.array(parsed, dtype=np.float32)
            emb_norm = np.linalg.norm(emb_arr)
            if emb_norm == 0:
                continue
            emb_arr = emb_arr / emb_norm
            
            # Cosine similarity
            similarity = float(np.dot(query_arr, emb_arr))
            results.append((fact_id, similarity))
        except Exception:
            continue
    
    # Sắp xếp theo độ tương đồng giảm dần
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


# =============================================================================
# TÍNH ĐIỂM TỪ VỰNG (LEXICAL SCORING - search hybrid)
# =============================================================================

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "had", "has", "have", "how", "i", "in", "is", "it",
    "of", "on", "or", "that", "the", "their", "then", "there", "to",
    "was", "were", "what", "when", "where", "which", "who", "why", "with",
    "you", "your",
    # Vietnamese stopwords
    "là", "và", "của", "có", "được", "cho", "với", "này", "đó", "trong",
    "một", "các", "những", "để", "khi", "từ", "về", "như", "không", "đã",
    "sẽ", "cũng", "còn", "hay", "hoặc", "nếu", "thì", "mà", "vì", "bởi",
}


def _tokenize(text: str) -> List[str]:
    """Tokenize văn bản, loại bỏ stopwords."""
    tokens = [t for t in _TOKEN_RE.findall((text or "").lower()) if t]
    return [t for t in tokens if t not in _STOPWORDS]


def _lexical_scores_for_ids(
    *,
    query_text: str,
    ids: List[int],
    content_map: Dict[int, str],
) -> Dict[int, float]:
    """
    Tính điểm trùng lặp token có trọng số IDF trong khoảng [0, 1] cho mỗi doc.
    Sao chép từ Memori: Dùng cho lexical reranking.
    """
    q_tokens = _tokenize(query_text)
    if not q_tokens:
        return dict.fromkeys(ids, 0.0)
    
    docs: Dict[int, set] = {}
    for i in ids:
        content = content_map.get(i, "")
        docs[i] = set(_tokenize(content))
    
    # IDF trên các docs ứng viên
    n = float(len(ids)) or 1.0
    df: Dict[str, int] = {}
    for t in set(q_tokens):
        df[t] = sum(1 for i in ids if t in docs.get(i, set()))
    idf = {t: (math.log((n + 1.0) / (float(df[t]) + 1.0)) + 1.0) for t in df}
    
    denom = sum(idf.get(t, 0.0) for t in q_tokens) or 1.0
    out: Dict[int, float] = {}
    for i in ids:
        doc_tokens = docs.get(i, set())
        num = sum(idf.get(t, 0.0) for t in q_tokens if t in doc_tokens)
        out[i] = float(num / denom)
    return out


def _rerank_by_lexical_overlap(
    *,
    query_text: str,
    candidate_ids: List[int],
    content_map: Dict[int, str],
    similarities_map: Dict[int, float],
) -> List[int]:
    """
    Rerank các ứng viên sử dụng điểm lai (85% semantic + 15% lexical).
    Sao chép từ Memori: Cải thiện khả năng truy hồi bằng chứng chính xác.
    """
    scores = _lexical_scores_for_ids(
        query_text=query_text, ids=candidate_ids, content_map=content_map
    )
    
    def key(fid: int) -> Tuple[float, float]:
        cos = float(similarities_map.get(fid, 0.0))
        lex = float(scores.get(fid, 0.0))
        return ((0.85 * cos) + (0.15 * lex), cos)
    
    return sorted(candidate_ids, key=key, reverse=True)


def search_entity_facts(
    facts_data: List[Dict[str, Any]],
    query_embedding: List[float],
    limit: int,
    query_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Tìm kiếm facts của entity bằng độ tương đồng embedding với tùy chọn lexical reranking.
    Sao chép từ Memori: Hàm tìm kiếm chính để recall fact.
    
    Args:
        facts_data: Danh sách dicts chứa 'id', 'content', 'content_embedding'
        query_embedding: Query embedding dưới dạng list floats
        limit: Số lượng kết quả trả về
        query_text: Text truy vấn tùy chọn để lexical reranking
        
    Returns:
        Danh sách dicts với các key: id, content, similarity, lexical_score, rank_score
    """
    if not facts_data:
        logger.debug("Không có dữ liệu facts nào được cung cấp")
        return []
    
    # Chuẩn bị embeddings cho FAISS search
    embeddings = [(f["id"], f.get("content_embedding")) for f in facts_data if f.get("content_embedding")]
    
    if not embeddings:
        logger.debug("Không tìm thấy embeddings trong dữ liệu facts")
        return []
    
    logger.debug("Đang tìm kiếm trên %d facts", len(embeddings))
    
    # Khi có query_text, lấy tập ứng viên lớn hơn để rerank
    candidate_limit = int(limit)
    if query_text:
        candidate_limit = max(limit, min(len(embeddings), max(limit * 10, 50)))
    
    similar = find_similar_embeddings(embeddings, query_embedding, candidate_limit)
    
    if not similar:
        logger.debug("Không tìm thấy embeddings tương đồng")
        return []
    
    candidate_ids = [fact_id for fact_id, _ in similar]
    similarities_map = dict(similar)
    
    # Xây dựng content map
    content_map = {f["id"]: f["content"] for f in facts_data}
    
    # Rerank nếu có query_text
    if query_text:
        reranked = _rerank_by_lexical_overlap(
            query_text=query_text,
            candidate_ids=candidate_ids,
            content_map=content_map,
            similarities_map=similarities_map,
        )
        ordered_ids = reranked[:limit]
    else:
        ordered_ids = candidate_ids[:limit]
    
    # Xây dựng kết quả
    results: List[Dict[str, Any]] = []
    for fact_id in ordered_ids:
        content = content_map.get(fact_id)
        if content is None:
            continue
        
        cos = float(similarities_map.get(fact_id, 0.0))
        row = {
            "id": fact_id,
            "content": content,
            "similarity": cos,
        }
        results.append(row)
    
    # Thêm lexical scores nếu có query_text
    if query_text and results:
        scores = _lexical_scores_for_ids(
            query_text=query_text,
            ids=[r["id"] for r in results],
            content_map=content_map,
        )
        for r in results:
            lex = float(scores.get(r["id"], 0.0))
            cos = float(r["similarity"])
            r["lexical_score"] = lex
            r["rank_score"] = (0.85 * cos) + (0.15 * lex)
    
    logger.debug("Trả về %d facts kèm điểm tương đồng", len(results))
    return results
