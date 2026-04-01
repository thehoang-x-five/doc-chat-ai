# Sơ Đồ Kiến Trúc Hệ Thống RAG - Chi Tiết Đầy Đủ

> **Tài liệu này**: Mô tả chi tiết kiến trúc hệ thống AI hỗ trợ sinh viên học tập với RAG
> 
> **Bao gồm**: OCR Flow, Memori Integration, Intent Detection, LLM Fallback, RAG Patterns

---

## 📋 Mục Lục

1. [Tổng Quan Kiến Trúc](#1-tổng-quan-kiến-trúc)
2. [Flow 1: Upload & OCR Processing](#2-flow-1-upload--ocr-processing)
3. [Flow 2: RAG Chat Query với Intent Detection](#3-flow-2-rag-chat-query-với-intent-detection)
4. [Flow 3: Memori Integration (Knowledge Graph)](#4-flow-3-memori-integration-knowledge-graph)
5. [Flow 4: LLM Provider Fallback Chain](#5-flow-4-llm-provider-fallback-chain)
6. [Flow 5: RAG Patterns (Advanced)](#6-flow-5-rag-patterns-advanced)
7. [Công Nghệ & Tối Ưu](#7-công-nghệ--tối-ưu)

---

## 1. Tổng Quan Kiến Trúc

### 1.1 Kiến Trúc Tổng Thể

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Browser<br/>React + TypeScript]
    end
    
    subgraph "API Gateway"
        NGINX[Nginx<br/>Reverse Proxy]
        API[FastAPI<br/>REST API]
    end
    
    subgraph "Service Layer - Core"
        CHAT[ChatService<br/>Conversation Management]
        DOC[DocumentService<br/>Document CRUD]
        RAG[RAGService<br/>RAG Orchestration]
    end
    
    subgraph "Service Layer - AI"
        INTENT[IntentDetector<br/>Pattern + LLM]
        EMB[EmbeddingService<br/>sentence-transformers]
        RET[RetrieverService<br/>Vector Search]
        MEMORI[MemoriManager<br/>Knowledge Graph]
    end
    
    subgraph "Background Workers"
        CELERY[Celery Workers]
        OCR_WORKER[OCR Task<br/>Docling/RAGAnything]
        MEMORI_WORKER[Memori Task<br/>Fact Extraction]
    end
    
    subgraph "Data Layer"
        PG[(PostgreSQL<br/>+ pgvector)]
        REDIS[(Redis<br/>Cache + Queue)]
        MINIO[(MinIO/S3<br/>Object Storage)]
    end
    
    subgraph "External AI Services"
        CLOUDCODE[Cloud Code<br/>FREE Claude/Gemini]
        DEEPSEEK[DeepSeek<br/>Cheap + Fast]
        GEMINI[Gemini<br/>Free Tier]
        GROQ[Groq<br/>Fast Inference]
        OLLAMA[Ollama<br/>Local Fallback]
    end

    WEB --> NGINX
    NGINX --> API
    API --> CHAT
    API --> DOC
    CHAT --> RAG
    CHAT --> MEMORI
    RAG --> INTENT
    RAG --> RET
    RAG --> EMB
    RAG --> CLOUDCODE
    RAG --> DEEPSEEK
    RAG --> GEMINI
    RAG --> GROQ
    RAG --> OLLAMA
    DOC --> CELERY
    CELERY --> OCR_WORKER
    CELERY --> MEMORI_WORKER
    OCR_WORKER --> PG
    OCR_WORKER --> MINIO
    MEMORI_WORKER --> PG
    CHAT --> PG
    DOC --> PG
    RET --> PG
    EMB --> REDIS
    MEMORI --> PG
```

### 1.2 Đặc Điểm Chính

**Kiến Trúc Phân Tầng**:
- **Client**: React SPA với TypeScript
- **API Gateway**: Nginx + FastAPI (async)
- **Service Layer**: Business logic (Chat, Document, RAG, Memori)
- **Data Layer**: PostgreSQL + pgvector + Redis + MinIO
- **Background Jobs**: Celery workers cho xử lý nặng

**Tính Năng Nổi Bật**:
- ✅ **Multi-Provider LLM**: Auto fallback khi hết quota
- ✅ **Intent Detection**: Pattern matching + LLM fallback
- ✅ **Knowledge Graph**: Memori với semantic triples
- ✅ **Advanced RAG**: 7 patterns (Corrective, Self, Adaptive, CORAG, CORAL, REVEAL, Speculative)
- ✅ **Vector Search**: pgvector với HNSW index
- ✅ **Async Processing**: Celery cho OCR và fact extraction

---

## 2. Flow 1: Upload & OCR Processing

### 2.1 Sơ Đồ Chi Tiết

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DocService
    participant Storage as MinIO/S3
    participant DB as PostgreSQL
    participant Celery
    participant OCR as OCR Worker
    participant Parser as Docling/RAGAnything
    participant EmbedService

    
    Note over Client,EmbedService: PHASE 1: UPLOAD & VALIDATION
    Client->>API: POST /documents/upload<br/>(file, workspace_id, tags)
    API->>DocService: upload(file, workspace_id, user_id, tags)
    
    Note over DocService: Validate file<br/>(type: PDF/DOCX/TXT, size < 50MB)
    DocService->>DB: INSERT Document<br/>(status=NEW)
    DocService->>Storage: Upload file<br/>(key: documents/{workspace}/{doc_id}/{filename})
    DocService->>DB: INSERT DocumentVersion (v1)
    DocService->>DB: INSERT Job<br/>(type=OCR, status=QUEUED)
    DocService->>DB: UPDATE Document<br/>(status=INDEXING)
    DocService-->>API: Return Document
    API-->>Client: 201 Created + Document info
    
    Note over Celery,EmbedService: PHASE 2: BACKGROUND PROCESSING
    Celery->>DB: Poll QUEUED jobs
    Celery->>OCR: Start OCR task
    OCR->>DB: UPDATE Job (status=RUNNING, progress=10%)
    OCR->>Storage: Download file
    
    Note over OCR,Parser: PHASE 3: PARSING (2 strategies)
    alt RAGAnything Parsing (Graph RAG)
        OCR->>Parser: parse_document(file_path)
        Parser-->>OCR: content_list (text, tables, images, equations)
        Note over Parser: Multimodal processing<br/>+ Knowledge graph extraction
    else Docling Parsing (Naive RAG)
        OCR->>Parser: process_document(file_path)
        Parser-->>OCR: fullText, markdownText, structured JSON
        Note over Parser: Text extraction only
    end
    
    OCR->>DB: UPDATE Job (progress=60%)
    
    Note over OCR,EmbedService: PHASE 4: CHUNKING & EMBEDDING
    loop For each chunk (500 tokens, 50 overlap)
        OCR->>EmbedService: embed_text(chunk_content)
        EmbedService-->>OCR: embedding vector (768-dim)
        OCR->>DB: INSERT Chunk<br/>(content, embedding, page_start, page_end)
    end
    
    OCR->>Storage: Upload outputs<br/>(text.txt, content.md, structured.json)
    OCR->>DB: UPDATE DocumentVersion<br/>(extracted_text_key, page_count)
    OCR->>DB: UPDATE Document<br/>(status=READY, progress=100%)
    OCR->>DB: UPDATE Job<br/>(status=DONE)
```

### 2.2 Chi Tiết Các Bước

**Bước 1: Upload & Validation**
- Client upload file qua multipart/form-data
- Validate: type (PDF, DOCX, TXT), size (< 50MB)
- Create Document record với status=NEW
- Upload file lên MinIO/S3 với key: `documents/{workspace_id}/{document_id}/{filename}`
- Calculate SHA256 checksum để detect duplicates

**Bước 2: Queue Background Job**
- Create Job record (type=OCR, status=QUEUED)
- Celery worker poll và pick up job
- Update Document status=INDEXING (frontend shows "Processing...")

**Bước 3: Parsing - 2 Strategies**

**Strategy A: RAGAnything (Graph RAG)**
```python
# Feature flag: ENABLE_RAGANYTHING_PARSING=True
from app.services.rag_service import RAGService

content_list, doc_id = await rag_service.parse_document(
    file_path=tmp_path,
    workspace_id=workspace_id,
    parse_method="auto",  # auto/fast/hi_res
)

# Output: List of content blocks
# - Text blocks with page numbers
# - Tables (structured data)
# - Images (base64 encoded)
# - Equations (LaTeX)
# - Knowledge graph triples
```

**Strategy B: Docling (Naive RAG)**
```python
# Fallback when RAGAnything not available
from app.core.engines.ocr import DocumentEngine

result = await engine.process_document(
    job_id=job_id,
    file_path=tmp_path,
    settings_dict={
        "parser": "docling",
        "parse_method": "auto",
        "language": "auto",
    }
)

# Output: Simple text extraction
# - fullText: Plain text
# - markdownText: Markdown formatted
# - structured: JSON metadata
```

**Bước 4: Chunking**
- Split content thành chunks ~500 tokens
- Overlap 50 tokens giữa các chunks (preserve context)
- Preserve metadata: page_start, page_end, section_title

**Bước 5: Embedding**
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Dimension: 768
- Cache embeddings trong Redis (key: MD5(text))

**Bước 6: Indexing**
- Insert chunks vào PostgreSQL với pgvector
- Create HNSW index cho fast similarity search
- Update Document status=READY

---

## 3. Flow 2: RAG Chat Query với Intent Detection

### 3.1 Sơ Đồ Chi Tiết

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant ChatService
    participant MemoriManager
    participant IntentDetector
    participant RAGService
    participant RetrieverService
    participant EmbedService
    participant DB
    participant LLM as LLM Providers

    
    Note over Client,LLM: PHASE 1: RECEIVE QUESTION
    Client->>API: POST /chat/conversations/{id}/messages<br/>(content, tags, model)
    API->>ChatService: send_message(conversation_id, content)
    ChatService->>DB: INSERT Message (role=USER)
    
    Note over ChatService,MemoriManager: PHASE 2: MEMORY RECALL
    ChatService->>DB: Get last 10 messages
    ChatService->>MemoriManager: recall_for_query(query, conversation_id)
    MemoriManager->>DB: Search facts by embedding similarity
    MemoriManager->>DB: Get knowledge graph triples
    MemoriManager-->>ChatService: recalled_facts (top 5)
    Note over ChatService: Build memory_context string
    
    Note over ChatService,IntentDetector: PHASE 3: INTENT DETECTION
    ChatService->>RAGService: query(question, memory_context)
    RAGService->>IntentDetector: detect(question)
    
    alt Pattern Matching (Fast)
        IntentDetector-->>RAGService: intent=GREETING (confidence=0.95)
        Note over IntentDetector: Regex patterns:<br/>- Greeting: "xin chào", "hello"<br/>- Image gen: "tạo ảnh", "vẽ"<br/>- Code gen: "viết code"
    else LLM Classification (Ambiguous)
        IntentDetector->>LLM: Classify query with context
        LLM-->>IntentDetector: intent=DOCUMENT_QUERY
    end
    
    alt Intent = GREETING/CHITCHAT
        RAGService-->>ChatService: Direct response (no RAG)
    else Intent = DOCUMENT_QUERY
        Note over RAGService,DB: PHASE 4: VECTOR SEARCH
        RAGService->>EmbedService: embed_text(question)
        EmbedService-->>RAGService: query_embedding (768-dim)
        RAGService->>RetrieverService: search(query_embedding, workspace_id, tags, top_k=5)
        RetrieverService->>DB: SELECT chunks<br/>ORDER BY embedding <=> query_embedding<br/>WHERE workspace_id AND tags
        DB-->>RetrieverService: Top 5 chunks with scores
        
        Note over RAGService: PHASE 5: RERANKING (Optional)
        RAGService->>RAGService: Rerank with cross-encoder<br/>(improve precision by 15-20%)
        
        Note over RAGService,LLM: PHASE 6: GENERATE ANSWER
        RAGService->>RAGService: Build context from chunks
        RAGService->>LLM: generate(question, context, memory)
        Note over LLM: Multi-provider fallback:<br/>1. Cloud Code (FREE)<br/>2. DeepSeek<br/>3. Gemini<br/>4. Groq<br/>5. Ollama
        LLM-->>RAGService: answer + metadata
        RAGService-->>ChatService: RAGResponse (answer, citations, tokens)
    end
    
    Note over ChatService,DB: PHASE 7: SAVE RESPONSE
    ChatService->>DB: INSERT Message (role=ASSISTANT)
    ChatService->>DB: INSERT Citations (chunk_id, score, quote, page)
    ChatService->>DB: INSERT AIUsage (tokens, cost)
    ChatService-->>API: (user_message, assistant_message)
    API-->>Client: 201 Created + Messages + Citations
```

### 3.2 Chi Tiết Intent Detection

**Pattern Matching (Fast, Deterministic)**:
```python
# Greeting patterns
GREETING_PATTERNS = [
    r"^(hi|hello|hey|xin\s*chào|chào)[\s!.,?]*$",
    r"^good\s*(morning|afternoon|evening)[\s!.,?]*$",
]

# Image generation patterns
IMAGE_GENERATION_PATTERNS = [
    r"(tạo|vẽ|sinh|generate)\s*(một\s*)?(ảnh|hình|tranh)",
    r"(generate|create|make|draw)\s*(an?\s*)?(image|picture)",
]

# Code generation patterns
CODE_GENERATION_PATTERNS = [
    r"(viết|tạo|code)\s*(code|hàm|function|class)",
    r"(write|create|implement)\s*(a\s*)?(function|class|script)",
]
```

**LLM Classification (Ambiguous Cases)**:
```python
# Prompt template
INTENT_CLASSIFICATION_PROMPT = """Classify the query into ONE category:

- `greeting`: Greetings (hi, hello, xin chào)
- `chitchat`: General chat NOT about documents
- `document`: Questions about topics in document categories
- `image_generation`: Create/draw images
- `code_generation`: Write code

Document Categories: {document_context}

Output JSON only: {{"intent": "<type>", "response": "<if greeting/chitchat else null>"}}

Query: "{query}"
"""

# Multi-provider fallback
# 1. Cloud Code (FREE Claude/Gemini) - Best quality
# 2. DeepSeek - Strong, fast, cheap
# 3. Gemini - Good quality, free tier
# 4. Groq - Fast, free tier
# 5. Ollama - Local fallback
```

### 3.3 Chi Tiết Vector Search

**Query với pgvector**:
```sql
SELECT 
    c.id as chunk_id,
    d.id as document_id,
    d.title as document_title,
    c.content,
    c.page_start,
    c.page_end,
    c.section_title,
    1 - (c.embedding <=> :query_embedding) as score
FROM chunks c
JOIN document_versions dv ON c.document_version_id = dv.id
JOIN documents d ON dv.document_id = d.id
WHERE d.workspace_id = :workspace_id
  AND d.status = 'READY'
  AND c.embedding IS NOT NULL
  AND d.tags && ARRAY[:tags]::varchar[]  -- Tag filtering
  AND 1 - (c.embedding <=> :query_embedding) >= :min_score
ORDER BY c.embedding <=> :query_embedding
LIMIT :top_k
```

**Indexes**:
```sql
-- HNSW index for fast vector search
CREATE INDEX idx_chunks_embedding ON chunks 
USING hnsw (embedding vector_cosine_ops);

-- GIN index for tag filtering
CREATE INDEX idx_documents_tags ON documents USING GIN (tags);
```

---

## 4. Flow 3: Memori Integration (Knowledge Graph)

### 4.1 Sơ Đồ Chi Tiết

```mermaid
sequenceDiagram
    participant ChatService
    participant Celery
    participant MemoriWorker
    participant MemoriManager
    participant LLM
    participant DB
    
    Note over ChatService,DB: PHASE 1: TRIGGER (After Chat Response)
    ChatService->>DB: Get message count
    alt Message count % 2 == 0
        ChatService->>Celery: Queue memori_extraction_task<br/>(conversation_id, workspace_id, user_id)
        Note over Celery: Non-blocking, async
    end
    
    Note over Celery,DB: PHASE 2: BACKGROUND EXTRACTION
    Celery->>MemoriWorker: Start extraction task
    MemoriWorker->>DB: Get last 6 messages (3 exchanges)
    
    Note over MemoriWorker,LLM: PHASE 3: FACT EXTRACTION
    MemoriWorker->>LLM: Extract facts from conversation
    Note over LLM: Prompt:<br/>- Extract user preferences<br/>- Extract user attributes<br/>- Extract facts about entities
    LLM-->>MemoriWorker: facts, preferences, attributes
    
    Note over MemoriWorker,DB: PHASE 4: TRIPLE EXTRACTION
    MemoriWorker->>LLM: Extract semantic triples
    Note over LLM: Prompt:<br/>- Subject-Predicate-Object<br/>- Temporal support (valid_at, invalid_at)<br/>- Contradiction detection
    LLM-->>MemoriWorker: semantic_triples
    
    Note over MemoriWorker,DB: PHASE 5: STORE TO DB
    MemoriWorker->>MemoriManager: add_facts(entity_id, facts)
    MemoriManager->>DB: INSERT memori_entity_facts<br/>(content, embedding, importance_score)
    
    MemoriWorker->>MemoriManager: add_semantic_triples(entity_id, triples)
    MemoriManager->>DB: Check for contradictions
    alt Contradiction detected
        MemoriManager->>DB: UPDATE old_triple<br/>(expired_at = NOW())
        Note over DB: "Latest wins" policy
    end
    MemoriManager->>DB: INSERT memori_knowledge_graph<br/>(subject, predicate, object, valid_at, invalid_at)
    
    MemoriWorker->>MemoriManager: add_preferences(entity_id, preferences)
    MemoriManager->>DB: INSERT memori_preferences
    
    MemoriWorker->>MemoriManager: add_attributes(entity_id, attributes)
    MemoriManager->>DB: INSERT memori_attributes
```

### 4.2 Chi Tiết Fact Extraction

**Extraction Prompt**:
```python
FACT_EXTRACTION_PROMPT = """Analyze this conversation and extract important facts.

CONVERSATION:
USER: Tôi đang học Python và muốn làm AI engineer
ASSISTANT: Tuyệt vời! Python là ngôn ngữ tốt cho AI...
USER: Tôi sống ở Hà Nội và đang học năm 3

Extract:
1. Facts about the user (preferences, background, interests)
2. Key decisions or statements made
3. Important context for future conversations

Return as JSON:
{
    "facts": [
        "User is learning Python",
        "User wants to become an AI engineer",
        "User lives in Hanoi",
        "User is in year 3 of university"
    ],
    "preferences": {
        "programming_language": "Python",
        "career_goal": "AI engineer"
    },
    "attributes": {
        "location": "Hanoi",
        "education_level": "Year 3 university"
    }
}
"""
```

**Triple Extraction with Temporal Support**:
```python
TRIPLE_EXTRACTION_PROMPT = """Extract semantic triples with temporal awareness.

FACTS:
- User is learning Python
- User lives in Hanoi
- User used to live in Ho Chi Minh City

INSTRUCTIONS:
1. PRONOUN RESOLUTION: Replace "tôi", "mình", "I" → "user"
2. TEMPORAL EXTRACTION:
   - "trước đây", "used to" → set invalid_at to "now"
   - "từ [date]", "since" → set valid_at to that date
3. NEGATION: "không ... nữa" → mark with invalid_at

Return JSON array:
[
    {"s":"user","st":"person","p":"is_learning","o":"Python","ot":"programming_language","valid_at":null,"invalid_at":null,"confidence":0.9},
    {"s":"user","st":"person","p":"lives_in","o":"Hanoi","ot":"location","valid_at":"now","invalid_at":null,"confidence":0.9},
    {"s":"user","st":"person","p":"lives_in","o":"Ho Chi Minh City","ot":"location","valid_at":null,"invalid_at":"now","confidence":0.8}
]
"""
```

### 4.3 Contradiction Detection

**Graphiti-Inspired Bi-Temporal Model**:
```python
# Check for contradictions
contradicted = await get_edge_contradictions(
    rag_service, new_triple, existing_triples
)

if contradicted:
    # "Latest wins" policy
    await invalidate_contradicted_edges(
        session, contradicted, datetime.utcnow()
    )
    # Old triple: expired_at = NOW()
    # New triple: valid_at = NOW(), expired_at = NULL
```

**Example**:
```
Old triple: (user, lives_in, Hanoi, valid_at=2023-01-01, expired_at=NULL)
New triple: (user, lives_in, Ho Chi Minh City, valid_at=2024-01-01, expired_at=NULL)

After contradiction detection:
Old triple: (user, lives_in, Hanoi, valid_at=2023-01-01, expired_at=2024-01-01)
New triple: (user, lives_in, Ho Chi Minh City, valid_at=2024-01-01, expired_at=NULL)
```

---

## 5. Flow 4: LLM Provider Fallback Chain

### 5.1 Sơ Đồ Chi Tiết

```mermaid
sequenceDiagram
    participant RAGService
    participant CloudCode
    participant DeepSeek
    participant Gemini
    participant Groq
    participant Ollama
    
    Note over RAGService: PHASE 1: Try Cloud Code (FREE)
    RAGService->>CloudCode: generate(prompt, model="gemini-3-flash")
    alt Success
        CloudCode-->>RAGService: answer + metadata
    else Quota Exceeded / Error
        CloudCode-->>RAGService: Error (quota exceeded)
        
        Note over RAGService: PHASE 2: Fallback to DeepSeek
        RAGService->>DeepSeek: generate(prompt, model="deepseek-chat")
        alt Success
            DeepSeek-->>RAGService: answer + metadata
        else Quota Exceeded / Error
            DeepSeek-->>RAGService: Error
            
            Note over RAGService: PHASE 3: Fallback to Gemini
            RAGService->>Gemini: generate(prompt, model="gemini-1.5-flash")
            alt Success
                Gemini-->>RAGService: answer + metadata
            else Quota Exceeded / Error
                Gemini-->>RAGService: Error
                
                Note over RAGService: PHASE 4: Fallback to Groq
                RAGService->>Groq: generate(prompt, model="llama-3.3-70b")
                alt Success
                    Groq-->>RAGService: answer + metadata
                else Quota Exceeded / Error
                    Groq-->>RAGService: Error
                    
                    Note over RAGService: PHASE 5: Final Fallback to Ollama
                    RAGService->>Ollama: generate(prompt, model="qwen2.5:7b")
                    Ollama-->>RAGService: answer + metadata
                end
            end
        end
    end
```

### 5.2 Chi Tiết Implementation

**Priority Order (Strongest → Weakest)**:
```python
async def _generate_answer_with_fallback(
    self, question: str, context: str, model: Optional[str] = None
) -> tuple:
    """
    Generate answer with multi-provider fallback chain.
    
    Priority:
    1. Cloud Code (FREE Claude/Gemini) - Best quality, no cost
    2. DeepSeek - Strong, fast, cheap ($0.14/1M tokens)
    3. Gemini - Good quality, free tier (15 RPM)
    4. Groq - Fast inference, free tier (30 RPM)
    5. Ollama - Local fallback, always available
    """
    
    # Priority 1: Cloud Code
    try:
        result = await self._call_cloudcode(question, context, model)
        if result:
            return result
    except QuotaExceededError:
        logger.warning("Cloud Code quota exceeded, trying DeepSeek")
    except Exception as e:
        logger.warning(f"Cloud Code error: {e}")
    
    # Priority 2: DeepSeek
    try:
        result = await self._call_deepseek(question, context, model)
        if result:
            return result
    except QuotaExceededError:
        logger.warning("DeepSeek quota exceeded, trying Gemini")
    except Exception as e:
        logger.warning(f"DeepSeek error: {e}")
    
    # Priority 3: Gemini
    try:
        result = await self._call_gemini(question, context, model)
        if result:
            return result
    except QuotaExceededError:
        logger.warning("Gemini quota exceeded, trying Groq")
    except Exception as e:
        logger.warning(f"Gemini error: {e}")
    
    # Priority 4: Groq
    try:
        result = await self._call_groq(question, context, model)
        if result:
            return result
    except QuotaExceededError:
        logger.warning("Groq quota exceeded, trying Ollama")
    except Exception as e:
        logger.warning(f"Groq error: {e}")
    
    # Priority 5: Ollama (always available)
    return await self._call_ollama(question, context, model)
```

**API Key Management**:
```python
class APIKeyManager:
    """
    Manages API keys with rotation and quota tracking.
    
    Features:
    - Multiple keys per provider
    - Automatic rotation on quota exceeded
    - Success/failure tracking
    - Cooldown period for failed keys
    """
    
    def get_key(self, provider: str) -> Optional[str]:
        """Get next available key for provider."""
        keys = self._keys.get(provider, [])
        for key in keys:
            if not self._is_on_cooldown(key):
                return key
        return None
    
    def mark_quota_exceeded(self, provider: str, key: str):
        """Mark key as quota exceeded (cooldown 1 hour)."""
        self._cooldowns[key] = datetime.utcnow() + timedelta(hours=1)
    
    def mark_success(self, provider: str, key: str):
        """Mark key as successful (remove from cooldown)."""
        if key in self._cooldowns:
            del self._cooldowns[key]
```

---

## 6. Flow 5: RAG Patterns (Advanced)

### 6.1 Tổng Quan 7 Patterns

```mermaid
graph TB
    QUERY[User Query] --> PATTERN_SELECTOR{Pattern Selector}
    
    PATTERN_SELECTOR -->|Simple Query| NAIVE[Naive RAG<br/>Basic Retrieval]
    PATTERN_SELECTOR -->|Need Validation| CORRECTIVE[Corrective RAG<br/>Validate & Correct]
    PATTERN_SELECTOR -->|Need Reflection| SELF[Self RAG<br/>Self-Reflection]
    PATTERN_SELECTOR -->|Complex Query| ADAPTIVE[Adaptive RAG<br/>Dynamic Strategy]
    PATTERN_SELECTOR -->|Optimize Cost| CORAG[CORAG<br/>MCTS Optimization]
    PATTERN_SELECTOR -->|Multi-turn| CORAL[CORAL<br/>Conversational RAG]
    PATTERN_SELECTOR -->|Multimodal| REVEAL[REVEAL<br/>Visual-Language RAG]
    PATTERN_SELECTOR -->|Speed Priority| SPECULATIVE[Speculative RAG<br/>Parallel Drafts]
    
    NAIVE --> ANSWER[Final Answer]
    CORRECTIVE --> ANSWER
    SELF --> ANSWER
    ADAPTIVE --> ANSWER
    CORAG --> ANSWER
    CORAL --> ANSWER
    REVEAL --> ANSWER
    SPECULATIVE --> ANSWER
```

### 6.2 Pattern 1: Corrective RAG

**Mục đích**: Validate retrieved documents và correct nếu không relevant

```mermaid
sequenceDiagram
    participant Query
    participant Retriever
    participant Validator
    participant WebSearch
    participant Generator
    
    Query->>Retriever: Retrieve top-k documents
    Retriever-->>Validator: Retrieved docs
    Validator->>Validator: Check relevance (score >= threshold)
    
    alt All docs relevant
        Validator-->>Generator: Use retrieved docs
    else Some docs irrelevant
        Validator->>WebSearch: Search for better docs
        WebSearch-->>Validator: Additional docs
        Validator-->>Generator: Use corrected docs
    end
    
    Generator-->>Query: Final answer
```

**Code**:
```python
result = await rag_service.query_with_corrective_rag(
    question=question,
    documents=retrieved_docs,
    relevance_threshold=0.6,
    max_correction_attempts=2,
)
```

### 6.3 Pattern 2: Self RAG

**Mục đích**: Self-reflection để check hallucinations

```mermaid
sequenceDiagram
    participant Query
    participant Retriever
    participant Generator
    participant Critic
    
    loop Max 3 iterations
        Query->>Retriever: Retrieve documents
        Retriever-->>Generator: Retrieved docs
        Generator->>Generator: Generate answer
        Generator-->>Critic: Check answer
        
        Critic->>Critic: Relevance check<br/>(Is answer relevant?)
        Critic->>Critic: Grounding check<br/>(Is answer grounded in docs?)
        Critic->>Critic: Utility check<br/>(Is answer useful?)
        
        alt All checks pass
            Critic-->>Query: Final answer
        else Checks fail
            Critic->>Retriever: Refine query & retry
        end
    end
```

**Code**:
```python
result = await rag_service.query_with_self_rag(
    question=question,
    documents=retrieved_docs,
    max_iterations=3,
    min_relevance_score=0.6,
    min_grounding_score=0.5,
)
```

### 6.4 Pattern 3: Adaptive RAG

**Mục đích**: Dynamic strategy selection based on query complexity

```mermaid
graph TB
    QUERY[User Query] --> CLASSIFIER{Query Classifier}
    
    CLASSIFIER -->|Simple| LIGHTWEIGHT[Lightweight Strategy<br/>Top-3 docs, Fast model]
    CLASSIFIER -->|Medium| STANDARD[Standard Strategy<br/>Top-5 docs, Standard model]
    CLASSIFIER -->|Complex| FULL[Full Strategy<br/>Top-10 docs, Best model]
    
    LIGHTWEIGHT --> ANSWER[Final Answer]
    STANDARD --> ANSWER
    FULL --> ANSWER
```

**Code**:
```python
result = await rag_service.query_with_adaptive_rag(
    question=question,
    documents=retrieved_docs,
    high_confidence_threshold=0.8,
    low_confidence_threshold=0.6,
    lightweight_top_k=3,
    full_top_k=10,
)
```

### 6.5 Pattern 4: CORAG (Chain-of-Retrieval)

**Mục đích**: Optimize chunk selection với Monte Carlo Tree Search

```mermaid
graph TB
    ROOT[Root Node] --> CHUNK1[Chunk 1<br/>Score: 0.8]
    ROOT --> CHUNK2[Chunk 2<br/>Score: 0.7]
    ROOT --> CHUNK3[Chunk 3<br/>Score: 0.6]
    
    CHUNK1 --> CHUNK1_1[Chunk 1 + Chunk 4<br/>Utility: 0.85]
    CHUNK1 --> CHUNK1_2[Chunk 1 + Chunk 5<br/>Utility: 0.82]
    
    CHUNK2 --> CHUNK2_1[Chunk 2 + Chunk 6<br/>Utility: 0.75]
    
    CHUNK1_1 --> BEST[Best Path<br/>Max Utility]
```

**Code**:
```python
result = await rag_service.query_with_corag(
    question=question,
    documents=retrieved_docs,
    cost_weight=0.3,
    mcts_iterations=100,
)
```

### 6.6 Pattern 5: CORAL (Conversational RAG)

**Mục đích**: Multi-turn conversation với context tracking

```mermaid
sequenceDiagram
    participant User
    participant CORAL
    participant ContextManager
    participant Retriever
    participant Generator
    
    User->>CORAL: Turn 1: "What is Python?"
    CORAL->>ContextManager: Store turn 1
    CORAL->>Retriever: Retrieve docs
    CORAL->>Generator: Generate answer
    Generator-->>User: "Python is a programming language..."
    
    User->>CORAL: Turn 2: "What are its advantages?"
    CORAL->>ContextManager: Get context (Turn 1)
    Note over ContextManager: Resolve "its" → "Python"
    CORAL->>Retriever: Retrieve docs (enhanced query)
    CORAL->>Generator: Generate answer (with context)
    Generator-->>User: "Python's advantages include..."
    
    User->>CORAL: Turn 3: "Show me an example"
    CORAL->>ContextManager: Get context (Turn 1-2)
    Note over ContextManager: Prune old context<br/>(keep last 3 turns)
    CORAL->>Retriever: Retrieve docs
    CORAL->>Generator: Generate answer
    Generator-->>User: "Here's a Python example..."
```

**Code**:
```python
result = await rag_service.query_with_coral(
    user_message=message,
    conversation_id=conversation_id,
    max_history_turns=10,
    context_window_size=4096,
    use_context_enhancement=True,
)
```

### 6.7 Pattern 6: REVEAL (Visual-Language RAG)

**Mục đích**: Multimodal RAG với text + images

```mermaid
graph TB
    QUERY[User Query<br/>Text + Image] --> TEXT_PROC[Text Processing]
    QUERY --> IMAGE_PROC[Image Processing]
    
    TEXT_PROC --> TEXT_EMB[Text Embedding]
    IMAGE_PROC --> IMAGE_EMB[Image Embedding]
    
    TEXT_EMB --> FUSION[Fusion Layer<br/>Early/Late/Hybrid]
    IMAGE_EMB --> FUSION
    
    FUSION --> RETRIEVAL[Multimodal Retrieval]
    RETRIEVAL --> GENERATOR[Multimodal Generator]
    GENERATOR --> ANSWER[Final Answer]
```

**Code**:
```python
result = await rag_service.query_multimodal_reveal(
    text_query=text_query,
    visual_query=image_data,
    top_k=5,
    fusion_strategy="hybrid",
    visual_weight=0.4,
    text_weight=0.6,
)
```

### 6.8 Pattern 7: Speculative RAG

**Mục đích**: Parallel draft generation cho speed

```mermaid
sequenceDiagram
    participant Query
    participant SmallModel as Small Model<br/>(Fast)
    participant LargeModel as Large Model<br/>(Accurate)
    
    Query->>SmallModel: Generate 3 drafts in parallel
    par Draft 1
        SmallModel-->>SmallModel: Draft 1
    and Draft 2
        SmallModel-->>SmallModel: Draft 2
    and Draft 3
        SmallModel-->>SmallModel: Draft 3
    end
    
    SmallModel-->>LargeModel: Verify drafts
    LargeModel->>LargeModel: Score each draft
    LargeModel-->>Query: Best draft (40% faster, 30% cheaper)
```

**Code**:
```python
result = await rag_service.query_with_speculative_rag(
    question=question,
    documents=retrieved_docs,
    num_drafts=3,
    small_model="gpt-3.5-turbo",
    large_model="gpt-4",
    enable_merging=False,
)
```

---

## 7. Công Nghệ & Tối Ưu

### 7.1 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 18 + TypeScript | UI framework |
| **API** | FastAPI + Uvicorn | Async REST API |
| **Database** | PostgreSQL 15 + pgvector | Relational + Vector DB |
| **Cache** | Redis 7 | Embedding cache, queue |
| **Storage** | MinIO/S3 | Object storage |
| **Queue** | Celery + Redis | Background jobs |
| **Embeddings** | sentence-transformers | Text → Vector (768-dim) |
| **LLM** | Multi-provider | Cloud Code, DeepSeek, Gemini, Groq, Ollama |
| **OCR** | Docling/RAGAnything | Document parsing |
| **Knowledge Graph** | Memori | Entity facts + triples |

### 7.2 Performance Optimizations

**Database**:
```sql
-- HNSW index for vector search (10x faster)
CREATE INDEX idx_chunks_embedding ON chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- GIN index for tag filtering
CREATE INDEX idx_documents_tags ON documents USING GIN (tags);

-- B-tree indexes for common queries
CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at DESC);
CREATE INDEX idx_documents_workspace ON documents (workspace_id, status);
```

**Caching Strategy**:
```python
# Redis cache layers
CACHE_LAYERS = {
    "embeddings": {
        "key": "emb:{model_id}:{md5(text)}",
        "ttl": None,  # Unlimited (embeddings don't change)
    },
    "intent": {
        "key": "intent:{md5(query)}",
        "ttl": 3600,  # 1 hour
    },
    "search_results": {
        "key": "search:{md5(query+filters)}",
        "ttl": 1800,  # 30 minutes
    },
}
```

**Async Processing**:
```python
# Concurrent LLM calls
results = await asyncio.gather(
    llm_call_1(),
    llm_call_2(),
    llm_call_3(),
    return_exceptions=True,
)

# Batch embedding generation
embeddings = embedding_service.embed_batch(texts, batch_size=32)

# Parallel fact extraction
tasks = [extract_facts(batch) for batch in batches]
results = await asyncio.gather(*tasks)
```

### 7.3 Monitoring & Metrics

**Performance Metrics**:
- API response time (p50, p95, p99)
- RAG pipeline latency breakdown
- Vector search performance
- LLM call latency per provider
- Cache hit rate

**Business Metrics**:
- Documents uploaded
- Conversations created
- Messages sent
- Token usage & cost per provider
- Intent detection accuracy

**Logging**:
```python
logger.info(f"⏱️  RAG query: {latency_ms}ms")
logger.info(f"📊 Retrieved {len(chunks)} chunks, best_score={best_score}")
logger.info(f"🤖 LLM: {provider} ({model}), tokens={prompt_tokens}+{completion_tokens}")
logger.info(f"💾 Cache hit rate: {cache_hit_rate:.1%}")
```

---

**Tác giả**: AI Engineering Team  
**Ngày cập nhật**: January 26, 2026  
**Phiên bản**: 2.0 (Chi tiết đầy đủ)
