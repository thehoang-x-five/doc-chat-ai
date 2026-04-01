# ERD Diagram - Hệ thống RAG cho Sinh viên

## 📊 Entity Relationship Diagram (Mermaid)

```mermaid
erDiagram
    %% ========================================
    %% USER & AUTHENTICATION
    %% ========================================
    USERS ||--o{ REFRESH_TOKENS : "has"
    USERS ||--o{ WORKSPACE_USERS : "belongs to"
    USERS ||--o{ WORKSPACES : "owns"
    USERS ||--o{ DOCUMENTS : "creates"
    USERS ||--o{ CONVERSATIONS : "creates"
    
    USERS {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        string role_global "ADMIN, TEACHER, STUDENT"
        timestamp created_at
        timestamp updated_at
        timestamp last_login_at
    }
    
    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        string token_hash
        timestamp expires_at
        timestamp created_at
        timestamp revoked_at
        string ip_address
    }
    
    %% ========================================
    %% WORKSPACE (MÔN HỌC)
    %% ========================================
    WORKSPACES ||--o{ WORKSPACE_USERS : "has members"
    WORKSPACES ||--o{ DOCUMENT_CATEGORIES : "has categories"
    WORKSPACES ||--o{ DOCUMENTS : "contains"
    WORKSPACES ||--o{ CONVERSATIONS : "has chats"
    WORKSPACES ||--o{ JOBS : "has jobs"
    WORKSPACES ||--o{ AI_USAGE : "tracks usage"
    
    WORKSPACES {
        uuid id PK
        string name "Tên môn học"
        uuid owner_id FK "Giáo viên phụ trách"
        string plan "free, pro, enterprise"
        string answer_policy "strict, balanced, open"
        float evidence_threshold
        timestamp created_at
    }
    
    WORKSPACE_USERS {
        uuid workspace_id PK,FK
        uuid user_id PK,FK
        string role "OWNER, EDITOR, VIEWER"
        timestamp joined_at
    }
    
    %% ========================================
    %% DOCUMENT MANAGEMENT
    %% ========================================
    DOCUMENT_CATEGORIES ||--o{ DOCUMENTS : "categorizes"
    
    DOCUMENT_CATEGORIES {
        uuid id PK
        uuid workspace_id FK
        string name "Chương 1, Chương 2..."
        string slug
        text description
        text content_summary "AI-generated"
        array keywords
        string icon
        string color
        int display_order
        boolean is_auto_generated
        timestamp created_at
        timestamp updated_at
    }
    
    DOCUMENTS ||--o{ DOCUMENT_VERSIONS : "has versions"
    
    DOCUMENTS {
        uuid id PK
        uuid workspace_id FK
        uuid category_id FK
        string title
        string doc_type "pdf, docx, txt"
        string source "upload, url"
        array tags
        string status "NEW, INDEXING, READY, FAILED"
        int processing_progress "0-100%"
        string processing_step
        text content_summary "AI-generated"
        array main_headings
        uuid created_by FK
        timestamp created_at
        timestamp updated_at
    }
    
    DOCUMENT_VERSIONS ||--o{ CHUNKS : "split into"
    DOCUMENT_VERSIONS ||--o{ JOBS : "processed by"
    
    DOCUMENT_VERSIONS {
        uuid id PK
        uuid document_id FK
        int version
        string original_file_key "S3/MinIO key"
        string mime_type
        bigint size_bytes
        string checksum_sha256
        string parser "docling, pypdf"
        string parse_method "auto, ocr"
        string language_detected
        int page_count
        string extracted_text_key "S3 key"
        string extracted_md_key "S3 key"
        string structured_json_key "S3 key"
        timestamp created_at
    }
    
    CHUNKS ||--o{ CITATIONS : "cited in"
    CHUNKS ||--o{ CHUNK_EMBEDDINGS : "has embeddings"
    
    CHUNKS {
        uuid id PK
        uuid document_version_id FK
        int chunk_index
        text content
        int token_count
        int page_start
        int page_end
        jsonb bbox_json "Bounding box"
        string section_title
        string hash
        string chunk_type "text, code, table, heading"
        array entities "Named entities"
        array topics
        string summary "1-sentence"
        float importance_score "0-1"
        vector embedding "pgvector(768)"
        timestamp created_at
    }
    
    %% ========================================
    %% EMBEDDING MODELS
    %% ========================================
    EMBEDDING_MODELS ||--o{ CHUNK_EMBEDDINGS : "generates"
    
    EMBEDDING_MODELS {
        uuid id PK
        string name UK "all-MiniLM-L6-v2"
        string provider "sentence-transformers, ollama, openai"
        int dimension "768, 1536"
        boolean is_active
        boolean is_default
        jsonb config_json
        timestamp created_at
    }
    
    CHUNK_EMBEDDINGS {
        uuid id PK
        uuid chunk_id FK
        uuid embedding_model_id FK
        vector embedding "pgvector(768)"
        timestamp created_at
    }
    
    %% ========================================
    %% CHAT & CONVERSATIONS
    %% ========================================
    CONVERSATIONS ||--o{ MESSAGES : "contains"
    
    CONVERSATIONS {
        uuid id PK
        uuid workspace_id FK
        string title
        array scope_tags "Filter documents"
        uuid created_by FK
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }
    
    MESSAGES ||--o{ CITATIONS : "has citations"
    MESSAGES ||--o{ AI_USAGE : "tracks usage"
    
    MESSAGES {
        uuid id PK
        uuid conversation_id FK
        string role "user, assistant, system"
        text content
        string provider "openai, gemini, ollama"
        string model "gpt-4, gemini-1.5-pro"
        int prompt_tokens
        int completion_tokens
        int latency_ms
        string policy_mode "strict, balanced, open"
        float best_retrieval_score
        boolean fallback_used
        timestamp created_at
    }
    
    CITATIONS {
        uuid id PK
        uuid message_id FK
        uuid chunk_id FK
        float score "Similarity score"
        text quote "Trích dẫn"
        int page "Số trang"
        timestamp created_at
    }
    
    %% ========================================
    %% BACKGROUND JOBS
    %% ========================================
    JOBS ||--o{ AI_USAGE : "tracks usage"
    
    JOBS {
        uuid id PK
        uuid workspace_id FK
        uuid document_version_id FK
        string type "OCR, INDEX, CONVERT"
        string status "QUEUED, RUNNING, DONE, ERROR"
        int progress "0-100%"
        string step
        text error_message
        jsonb config_json
        timestamp started_at
        timestamp finished_at
        timestamp created_at
    }
    
    %% ========================================
    %% AI USAGE TRACKING
    %% ========================================
    AI_USAGE {
        uuid id PK
        uuid workspace_id FK
        uuid job_id FK
        uuid message_id FK
        string provider "openai, gemini, ollama"
        string model
        int tokens_in
        int tokens_out
        decimal cost_usd
        timestamp created_at
    }
    
    %% ========================================
    %% MEMORI SYSTEM (OPTIONAL - CẤP ĐỘ 4)
    %% ========================================
    WORKSPACES ||--o{ MEMORI_ENTITIES : "has entities"
    MEMORI_ENTITIES ||--o{ MEMORI_ENTITY_FACTS : "has facts"
    MEMORI_ENTITIES ||--o{ MEMORI_KNOWLEDGE_GRAPH : "has triples"
    
    MEMORI_ENTITIES {
        int id PK
        string external_id UK
        uuid workspace_id FK
        timestamp created_at
        timestamp updated_at
    }
    
    MEMORI_ENTITY_FACTS {
        int id PK
        int entity_id FK
        text content
        bytea content_embedding "FAISS binary"
        uuid conversation_id FK
        float importance_score
        timestamp last_accessed_at
        timestamp created_at
    }
    
    MEMORI_KNOWLEDGE_GRAPH {
        int id PK
        int entity_id FK
        string subject_name
        string subject_type
        string predicate
        string object_name
        string object_type
        uuid conversation_id FK
        float confidence
        timestamp created_at
        timestamp valid_at "Temporal model"
        timestamp invalid_at
        timestamp expired_at
    }
```

---

## 🔑 Key Relationships

### 1. **User → Workspace (Môn học)**
- **1:N** - Một giáo viên có thể dạy nhiều môn học (owner)
- **M:N** - Một sinh viên có thể học nhiều môn học (workspace_users)

### 2. **Workspace → Document**
- **1:N** - Một môn học có nhiều tài liệu
- **Document → Document_Version** (1:N) - Hỗ trợ versioning

### 3. **Document_Version → Chunk**
- **1:N** - Một tài liệu được chia thành nhiều chunks
- **Chunk → Chunk_Embedding** (1:N) - Hỗ trợ nhiều embedding models

### 4. **Workspace → Conversation**
- **1:N** - Một môn học có nhiều conversations
- **Conversation → Message** (1:N) - Một conversation có nhiều messages

### 5. **Message → Citation**
- **1:N** - Một message có nhiều citations
- **Citation → Chunk** (N:1) - Trỏ đến chunk nguồn

---

## 📐 Cardinality Summary

| Relationship | Type | Description |
|-------------|------|-------------|
| User → Workspace | 1:N | Giáo viên sở hữu môn học |
| User ↔ Workspace | M:N | Sinh viên học môn học |
| Workspace → Document | 1:N | Môn học chứa tài liệu |
| Document → Document_Version | 1:N | Versioning |
| Document_Version → Chunk | 1:N | Chunking |
| Chunk → Chunk_Embedding | 1:N | Multi-model embeddings |
| Workspace → Conversation | 1:N | Chat sessions |
| Conversation → Message | 1:N | Chat history |
| Message → Citation | 1:N | Source citations |
| Citation → Chunk | N:1 | Reference to source |

---

## 🎯 Indexes (Quan trọng cho Performance)

```sql
-- User indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role_global);

-- Workspace indexes
CREATE INDEX idx_workspace_users_workspace ON workspace_users(workspace_id);
CREATE INDEX idx_workspace_users_user ON workspace_users(user_id);

-- Document indexes
CREATE INDEX idx_documents_workspace_status ON documents(workspace_id, status);
CREATE INDEX idx_documents_category ON documents(category_id);
CREATE INDEX idx_documents_tags ON documents USING GIN(tags);

-- Chunk indexes
CREATE INDEX idx_chunks_doc_version ON chunks(document_version_id);
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat(embedding vector_cosine_ops);

-- Conversation indexes
CREATE INDEX idx_conversations_workspace ON conversations(workspace_id);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_citations_message ON citations(message_id);
CREATE INDEX idx_citations_chunk ON citations(chunk_id);

-- Job indexes
CREATE INDEX idx_jobs_workspace_status ON jobs(workspace_id, status);
CREATE INDEX idx_jobs_status ON jobs(status);

-- AI Usage indexes
CREATE INDEX idx_ai_usage_workspace ON ai_usage(workspace_id);
CREATE INDEX idx_ai_usage_created ON ai_usage(created_at);
```

---

## 🔍 Vector Search (pgvector)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create vector index for fast similarity search
CREATE INDEX idx_chunks_embedding 
ON chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Query example: Find similar chunks
SELECT 
    c.id,
    c.content,
    c.page_start,
    dv.document_id,
    d.title,
    1 - (c.embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM chunks c
JOIN document_versions dv ON c.document_version_id = dv.id
JOIN documents d ON dv.document_id = d.id
WHERE d.workspace_id = 'workspace-uuid'
ORDER BY c.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

---

## 📊 Database Size Estimation

Giả sử môn học có:
- 10 tài liệu PDF (mỗi file ~5MB, ~100 trang)
- Mỗi trang → 3 chunks
- Mỗi chunk → 768-dim embedding (3KB)

**Ước tính**:
- Documents: 10 rows × 1KB = 10KB
- Document_Versions: 10 rows × 2KB = 20KB
- Chunks: 10 × 100 × 3 = 3,000 rows × 5KB = 15MB
- Chunk_Embeddings: 3,000 rows × 3KB = 9MB
- **Total**: ~25MB/môn học

Với 100 môn học → ~2.5GB

---

## 🚀 Optimization Tips

1. **Partitioning**: Partition `chunks` table by `workspace_id` nếu có nhiều môn học
2. **Archiving**: Archive old conversations sau 1 năm
3. **Caching**: Cache embeddings trong Redis
4. **Connection Pooling**: Sử dụng pgBouncer
5. **Read Replicas**: Tách read/write cho scalability

---

**Lưu ý**: ERD này đã loại bỏ các bảng không liên quan (CloudCode, OCR, Image generation) để tập trung vào core RAG features phù hợp với đề tài sinh viên.
