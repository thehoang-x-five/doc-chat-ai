# Memori Integration - RAG-Anything

## Overview

Đã tích hợp đầy đủ hệ thống quản lý bộ nhớ từ dự án Memori vào RAG-Anything, bao gồm:

1. **Entity Facts với Embeddings** - Lưu trữ facts về entities với vector embeddings cho semantic search
2. **Knowledge Graph (Semantic Triples)** - Lưu trữ quan hệ Subject-Predicate-Object
3. **FAISS Vector Search** - Tìm kiếm semantic similarity hiệu quả
4. **Lexical Reranking** - Hybrid search (85% semantic + 15% lexical)
5. **Session Management** - Quản lý session với timeout
6. **Async Augmentation Pipeline** - Trích xuất facts từ conversations

## Files Created/Modified

### New Files (Memori Module)
```
server/app/services/memori/
├── __init__.py          # Module exports
├── config.py            # MemoriConfig class
├── structs.py           # Data structures (SemanticTriple, Entity, Memories, etc.)
├── embeddings.py        # Embedding utilities (reuses EmbeddingService)
├── search.py            # FAISS + lexical search
├── recall.py            # MemoriRecall class
├── manager.py           # MemoriManager (main orchestrator)
└── augmentation.py      # Async augmentation pipeline
```

### Database Models (Added to models.py)
- `MemoriEntity` - Entity storage
- `MemoriEntityFact` - Facts with embeddings (LargeBinary for FAISS)
- `MemoriKnowledgeGraph` - Semantic triples
- `MemoriProcess` - Process tracking
- `MemoriProcessAttribute` - Process attributes
- `MemoriSession` - Session with timeout
- `MemoriConversation` - Memori conversation
- `MemoriConversationMessage` - Messages

### Migration
- `server/alembic/versions/add_memori_tables.py`

### API Endpoints
- `server/app/api/v1/memori.py` - REST API for memory management

### Modified Files
- `server/app/services/chat_service.py` - Integrated Memori recall + extraction
- `server/app/api/v1/__init__.py` - Added memori router
- `server/requirements.txt` - Added faiss-cpu

## How It Works

### 1. Fact Recall (Before RAG Query)
Khi user gửi message, hệ thống sẽ:
1. Tìm kiếm facts liên quan trong database bằng semantic similarity
2. Sử dụng FAISS để tìm top-k facts gần nhất
3. Rerank bằng lexical overlap (85% semantic + 15% lexical)
4. Inject facts vào context cho LLM

### 2. Fact Extraction (After Response)
Sau mỗi 5 messages, hệ thống sẽ:
1. Gửi conversation history cho LLM
2. LLM trích xuất facts và entities
3. Lưu facts với embeddings vào database
4. Lưu semantic triples vào knowledge graph

### 3. Search Algorithm
```
1. Generate query embedding
2. FAISS cosine similarity search (top-k candidates)
3. Lexical reranking với IDF-weighted token overlap
4. Final score = 0.85 * semantic + 0.15 * lexical
5. Filter by relevance threshold
```

## API Endpoints

### POST /api/v1/memori/recall
Tìm kiếm facts liên quan cho một query.

### POST /api/v1/memori/facts/{entity_id}
Thêm facts cho một entity.

### POST /api/v1/memori/triples/{entity_id}
Thêm semantic triples vào knowledge graph.

### GET /api/v1/memori/knowledge-graph/{entity_id}
Lấy knowledge graph của một entity.

### GET /api/v1/memori/stats/{entity_id}
Lấy thống kê memory của một entity.

### DELETE /api/v1/memori/cleanup/{entity_id}
Dọn dẹp facts cũ/không quan trọng.

## Setup

### 1. Install Dependencies
```bash
pip install faiss-cpu
```

### 2. Run Migration
```bash
cd server
alembic upgrade head
```

### 3. Test
```bash
# Start server
uvicorn app.main:app --reload

# Test recall endpoint
curl -X POST "http://localhost:8000/api/v1/memori/recall?workspace_id=xxx" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "limit": 5}'
```

## Configuration

Trong `MemoriConfig`:
- `recall_facts_limit`: Số facts tối đa trả về (default: 5)
- `recall_embeddings_limit`: Số embeddings tối đa để search (default: 1000)
- `recall_relevance_threshold`: Ngưỡng similarity tối thiểu (default: 0.1)
- `session_timeout_minutes`: Timeout session (default: 30)

## Integration with Existing Memory

Hệ thống kết hợp cả 2 approaches:
1. **Traditional MemoryManager**: Short-term (10 messages) + Long-term (summary)
2. **Memori-style**: Entity Facts + Semantic Search + Knowledge Graph

Cả 2 contexts được inject vào prompt:
```
[Conversation Context]
{memory_context from MemoryManager}

<memori_context>
{recalled facts from Memori}
</memori_context>

[Current Question]
{user question}
```
