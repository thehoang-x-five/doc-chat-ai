# Sơ Đồ Thiết Kế Kiến Trúc Hệ Thống RAG

> **Tài liệu này**: Các sơ đồ thiết kế kiến trúc dạng layered với ô và đường kết nối
> 
> **Mục đích**: Dễ hình dung và hiểu rõ luồng dữ liệu trong hệ thống

---

## 1. Kiến Trúc Tổng Thể - Layered Architecture

```mermaid
graph TB
    subgraph "PRESENTATION LAYER"
        style PRESENTATION_LAYER fill:#e1f5ff
        WEB["🌐 Web Browser<br/>━━━━━━━━━━━━━━<br/>React 18 + TypeScript<br/>TailwindCSS<br/>React Query"]
    end
    
    subgraph "API GATEWAY LAYER"
        style API_GATEWAY_LAYER fill:#fff3e0
        NGINX["⚡ Nginx<br/>━━━━━━━━━━━━━━<br/>Reverse Proxy<br/>Load Balancer<br/>SSL Termination"]
        API["🚀 FastAPI Server<br/>━━━━━━━━━━━━━━<br/>REST API<br/>Async/Await<br/>Pydantic Validation"]
    end
    
    subgraph "SERVICE LAYER - CORE"
        style SERVICE_LAYER_CORE fill:#f3e5f5
        CHAT["💬 ChatService<br/>━━━━━━━━━━━━━━<br/>• Conversation CRUD<br/>• Message handling<br/>• Citation storage<br/>• Usage tracking"]
        DOC["📄 DocumentService<br/>━━━━━━━━━━━━━━<br/>• Upload/Download<br/>• Versioning<br/>• Tag management<br/>• Permission checks"]
        RAG["🧠 RAGService<br/>━━━━━━━━━━━━━━<br/>• RAG orchestration<br/>• Pattern selection<br/>• Context building<br/>• LLM integration"]
    end
    
    subgraph "SERVICE LAYER - AI"
        style SERVICE_LAYER_AI fill:#e8f5e9
        INTENT["🎯 IntentDetector<br/>━━━━━━━━━━━━━━<br/>• Pattern matching<br/>• LLM classification<br/>• Cache management"]
        EMB["🔢 EmbeddingService<br/>━━━━━━━━━━━━━━<br/>• Text → Vector<br/>• Model versioning<br/>• Batch processing"]
        RET["🔍 RetrieverService<br/>━━━━━━━━━━━━━━<br/>• Vector search<br/>• Filtering<br/>• Reranking"]
        MEMORI["🧩 MemoriManager<br/>━━━━━━━━━━━━━━<br/>• Knowledge graph<br/>• Fact extraction<br/>• Temporal support"]
    end
    
    subgraph "BACKGROUND WORKERS"
        style BACKGROUND_WORKERS fill:#fff9c4
        CELERY["⚙️ Celery Workers<br/>━━━━━━━━━━━━━━"]
        OCR["📝 OCR Task<br/>━━━━━━━━━━━━━━<br/>• Docling parser<br/>• RAGAnything<br/>• Chunking<br/>• Embedding"]
        MEMORI_TASK["🧠 Memori Task<br/>━━━━━━━━━━━━━━<br/>• Fact extraction<br/>• Triple extraction<br/>• Contradiction check"]
    end

    
    subgraph "DATA LAYER"
        style DATA_LAYER fill:#ffebee
        PG["🗄️ PostgreSQL 15<br/>━━━━━━━━━━━━━━<br/>• Users, Workspaces<br/>• Documents, Chunks<br/>• Conversations, Messages<br/>• Memori (Facts, Triples)"]
        PGVECTOR["📊 pgvector Extension<br/>━━━━━━━━━━━━━━<br/>• Vector storage<br/>• HNSW index<br/>• Cosine similarity"]
        REDIS["⚡ Redis 7<br/>━━━━━━━━━━━━━━<br/>• Embedding cache<br/>• Intent cache<br/>• Celery queue<br/>• Session store"]
        MINIO["📦 MinIO/S3<br/>━━━━━━━━━━━━━━<br/>• Original files<br/>• Parsed outputs<br/>• Extracted text<br/>• Structured JSON"]
    end
    
    subgraph "EXTERNAL SERVICES"
        style EXTERNAL_SERVICES fill:#e0f2f1
        CLOUDCODE["☁️ Cloud Code<br/>━━━━━━━━━━━━━━<br/>FREE Claude/Gemini<br/>Priority: 1"]
        DEEPSEEK["🤖 DeepSeek<br/>━━━━━━━━━━━━━━<br/>$0.14/1M tokens<br/>Priority: 2"]
        GEMINI["🔮 Gemini<br/>━━━━━━━━━━━━━━<br/>Free tier: 15 RPM<br/>Priority: 3"]
        GROQ["⚡ Groq<br/>━━━━━━━━━━━━━━<br/>Fast inference<br/>Priority: 4"]
        OLLAMA["🏠 Ollama<br/>━━━━━━━━━━━━━━<br/>Local fallback<br/>Priority: 5"]
    end
    
    %% Connections
    WEB -->|HTTP/HTTPS| NGINX
    NGINX -->|Proxy| API
    
    API -->|REST| CHAT
    API -->|REST| DOC
    
    CHAT -->|Orchestrate| RAG
    CHAT -->|Recall| MEMORI
    CHAT -->|Save| PG
    
    DOC -->|Queue| CELERY
    DOC -->|CRUD| PG
    DOC -->|Upload| MINIO
    
    RAG -->|Detect| INTENT
    RAG -->|Search| RET
    RAG -->|Embed| EMB
    RAG -->|Generate| CLOUDCODE
    RAG -->|Fallback| DEEPSEEK
    RAG -->|Fallback| GEMINI
    RAG -->|Fallback| GROQ
    RAG -->|Fallback| OLLAMA
    
    INTENT -->|Cache| REDIS
    EMB -->|Cache| REDIS
    RET -->|Query| PG
    RET -->|Query| PGVECTOR
    MEMORI -->|Store| PG
    
    CELERY -->|Execute| OCR
    CELERY -->|Execute| MEMORI_TASK
    
    OCR -->|Parse & Index| PG
    OCR -->|Store| MINIO
    OCR -->|Embed| EMB
    
    MEMORI_TASK -->|Extract| PG
    MEMORI_TASK -->|LLM| CLOUDCODE
    
    PG -.->|Extension| PGVECTOR
```

---

## 2. Flow Upload & OCR Processing - Detailed Design

```mermaid
graph LR
    subgraph "CLIENT"
        USER["👤 User"]
    end
    
    subgraph "API LAYER"
        UPLOAD_API["📤 POST /documents/upload<br/>━━━━━━━━━━━━━━<br/>• Multipart form-data<br/>• File validation<br/>• Permission check"]
    end
    
    subgraph "SERVICE LAYER"
        DOC_SERVICE["📄 DocumentService<br/>━━━━━━━━━━━━━━<br/>1️⃣ Validate file<br/>2️⃣ Create Document<br/>3️⃣ Upload to storage<br/>4️⃣ Create version<br/>5️⃣ Queue job"]
    end
    
    subgraph "STORAGE"
        MINIO_STORE["📦 MinIO<br/>━━━━━━━━━━━━━━<br/>documents/<br/>{workspace}/<br/>{doc_id}/<br/>{filename}"]
    end
    
    subgraph "DATABASE"
        DB_WRITE["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>INSERT Document<br/>INSERT DocumentVersion<br/>INSERT Job<br/>status=QUEUED"]
    end
    
    subgraph "QUEUE"
        CELERY_QUEUE["⚙️ Celery Queue<br/>━━━━━━━━━━━━━━<br/>Job ID<br/>Document Version ID<br/>Config"]
    end
    
    subgraph "WORKER"
        OCR_WORKER["📝 OCR Worker<br/>━━━━━━━━━━━━━━<br/>1️⃣ Download file<br/>2️⃣ Parse document<br/>3️⃣ Chunk text<br/>4️⃣ Generate embeddings<br/>5️⃣ Index to DB"]
    end
    
    subgraph "PARSER"
        PARSER_CHOICE{"Parser<br/>Strategy"}
        RAGANYTHING["🧠 RAGAnything<br/>━━━━━━━━━━━━━━<br/>• Multimodal<br/>• Knowledge graph<br/>• Tables, images"]
        DOCLING["📄 Docling<br/>━━━━━━━━━━━━━━<br/>• Text only<br/>• Fast<br/>• Simple"]
    end
    
    subgraph "EMBEDDING"
        EMB_SERVICE["🔢 EmbeddingService<br/>━━━━━━━━━━━━━━<br/>sentence-transformers<br/>768-dim vectors<br/>Batch processing"]
    end
    
    subgraph "FINAL STORAGE"
        DB_INDEX["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>INSERT Chunks<br/>with embeddings<br/>UPDATE Document<br/>status=READY"]
        MINIO_OUTPUT["📦 MinIO<br/>━━━━━━━━━━━━━━<br/>outputs/<br/>{workspace}/<br/>{doc_id}/v{n}/<br/>text.txt<br/>content.md<br/>structured.json"]
    end
    
    USER -->|Upload| UPLOAD_API
    UPLOAD_API -->|Process| DOC_SERVICE
    DOC_SERVICE -->|Store| MINIO_STORE
    DOC_SERVICE -->|Write| DB_WRITE
    DOC_SERVICE -->|Queue| CELERY_QUEUE
    
    CELERY_QUEUE -->|Pick| OCR_WORKER
    OCR_WORKER -->|Download| MINIO_STORE
    OCR_WORKER -->|Parse| PARSER_CHOICE
    
    PARSER_CHOICE -->|Graph RAG| RAGANYTHING
    PARSER_CHOICE -->|Naive RAG| DOCLING
    
    RAGANYTHING -->|Content| OCR_WORKER
    DOCLING -->|Content| OCR_WORKER
    
    OCR_WORKER -->|Embed| EMB_SERVICE
    EMB_SERVICE -->|Vectors| OCR_WORKER
    
    OCR_WORKER -->|Index| DB_INDEX
    OCR_WORKER -->|Store| MINIO_OUTPUT
    
    style USER fill:#e3f2fd
    style UPLOAD_API fill:#fff3e0
    style DOC_SERVICE fill:#f3e5f5
    style MINIO_STORE fill:#ffebee
    style DB_WRITE fill:#ffebee
    style CELERY_QUEUE fill:#fff9c4
    style OCR_WORKER fill:#fff9c4
    style PARSER_CHOICE fill:#e8f5e9
    style RAGANYTHING fill:#e8f5e9
    style DOCLING fill:#e8f5e9
    style EMB_SERVICE fill:#e8f5e9
    style DB_INDEX fill:#ffebee
    style MINIO_OUTPUT fill:#ffebee
```

---

## 3. Flow RAG Chat Query - Detailed Design

```mermaid
graph TB
    subgraph "CLIENT"
        USER_QUERY["👤 User Query<br/>━━━━━━━━━━━━━━<br/>'Python là gì?'"]
    end
    
    subgraph "API LAYER"
        CHAT_API["💬 POST /chat/messages<br/>━━━━━━━━━━━━━━<br/>conversation_id<br/>content<br/>tags (optional)"]
    end
    
    subgraph "CHAT SERVICE"
        CHAT_SVC["💬 ChatService<br/>━━━━━━━━━━━━━━<br/>1️⃣ Save user message<br/>2️⃣ Recall memory<br/>3️⃣ Call RAG service<br/>4️⃣ Save assistant message"]
    end
    
    subgraph "MEMORY RECALL"
        MEMORI_RECALL["🧩 MemoriManager<br/>━━━━━━━━━━━━━━<br/>• Get last 10 messages<br/>• Search facts by embedding<br/>• Get knowledge graph<br/>• Build context"]
        DB_MEMORY["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>memori_entity_facts<br/>memori_knowledge_graph<br/>messages"]
    end
    
    subgraph "RAG SERVICE"
        RAG_SVC["🧠 RAGService<br/>━━━━━━━━━━━━━━<br/>Orchestrate RAG pipeline"]
    end
    
    subgraph "INTENT DETECTION"
        INTENT_DET["🎯 IntentDetector<br/>━━━━━━━━━━━━━━"]
        PATTERN_MATCH{"Pattern<br/>Match?"}
        LLM_CLASSIFY["🤖 LLM Classify<br/>━━━━━━━━━━━━━━<br/>Cloud Code<br/>DeepSeek<br/>Gemini"]
        INTENT_RESULT["Intent Result<br/>━━━━━━━━━━━━━━<br/>• GREETING<br/>• CHITCHAT<br/>• DOCUMENT_QUERY<br/>• IMAGE_GEN<br/>• CODE_GEN"]
    end
    
    subgraph "VECTOR SEARCH"
        EMB_QUERY["🔢 Embed Query<br/>━━━━━━━━━━━━━━<br/>sentence-transformers<br/>768-dim vector"]
        RETRIEVER["🔍 RetrieverService<br/>━━━━━━━━━━━━━━<br/>• Vector search<br/>• Tag filtering<br/>• Top-k selection"]
        PGVECTOR_SEARCH["📊 pgvector<br/>━━━━━━━━━━━━━━<br/>SELECT chunks<br/>ORDER BY<br/>embedding <=> query<br/>LIMIT 5"]
        RERANK["🎯 Reranking<br/>━━━━━━━━━━━━━━<br/>Cross-encoder<br/>+15-20% precision"]
    end

    
    subgraph "LLM GENERATION"
        CONTEXT_BUILD["📝 Build Context<br/>━━━━━━━━━━━━━━<br/>• Retrieved chunks<br/>• Memory context<br/>• Conversation history"]
        LLM_CHAIN["🤖 LLM Fallback Chain<br/>━━━━━━━━━━━━━━"]
        PROVIDER_1["☁️ Cloud Code<br/>Priority 1"]
        PROVIDER_2["🤖 DeepSeek<br/>Priority 2"]
        PROVIDER_3["🔮 Gemini<br/>Priority 3"]
        PROVIDER_4["⚡ Groq<br/>Priority 4"]
        PROVIDER_5["🏠 Ollama<br/>Priority 5"]
        LLM_RESPONSE["✅ Answer<br/>━━━━━━━━━━━━━━<br/>+ Citations<br/>+ Metadata<br/>+ Tokens"]
    end
    
    subgraph "RESPONSE STORAGE"
        SAVE_MSG["💾 Save Response<br/>━━━━━━━━━━━━━━<br/>• Assistant message<br/>• Citations<br/>• AI usage<br/>• Tokens & cost"]
        DB_SAVE["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>messages<br/>citations<br/>ai_usage"]
    end
    
    subgraph "BACKGROUND TASK"
        QUEUE_MEMORI["⚙️ Queue Memori Task<br/>━━━━━━━━━━━━━━<br/>Extract facts<br/>Extract triples<br/>Update knowledge graph"]
    end
    
    USER_QUERY -->|Send| CHAT_API
    CHAT_API -->|Process| CHAT_SVC
    
    CHAT_SVC -->|Recall| MEMORI_RECALL
    MEMORI_RECALL -->|Query| DB_MEMORY
    DB_MEMORY -->|Facts & Triples| MEMORI_RECALL
    MEMORI_RECALL -->|Context| CHAT_SVC
    
    CHAT_SVC -->|Query| RAG_SVC
    
    RAG_SVC -->|Detect| INTENT_DET
    INTENT_DET -->|Check| PATTERN_MATCH
    PATTERN_MATCH -->|Yes| INTENT_RESULT
    PATTERN_MATCH -->|No| LLM_CLASSIFY
    LLM_CLASSIFY -->|Classify| INTENT_RESULT
    
    INTENT_RESULT -->|DOCUMENT_QUERY| EMB_QUERY
    INTENT_RESULT -->|GREETING/CHITCHAT| LLM_CHAIN
    
    EMB_QUERY -->|Vector| RETRIEVER
    RETRIEVER -->|Search| PGVECTOR_SEARCH
    PGVECTOR_SEARCH -->|Top-k chunks| RERANK
    RERANK -->|Ranked chunks| CONTEXT_BUILD
    
    CONTEXT_BUILD -->|Prompt| LLM_CHAIN
    
    LLM_CHAIN -->|Try| PROVIDER_1
    PROVIDER_1 -->|Success| LLM_RESPONSE
    PROVIDER_1 -->|Fail| PROVIDER_2
    PROVIDER_2 -->|Success| LLM_RESPONSE
    PROVIDER_2 -->|Fail| PROVIDER_3
    PROVIDER_3 -->|Success| LLM_RESPONSE
    PROVIDER_3 -->|Fail| PROVIDER_4
    PROVIDER_4 -->|Success| LLM_RESPONSE
    PROVIDER_4 -->|Fail| PROVIDER_5
    PROVIDER_5 -->|Always Success| LLM_RESPONSE
    
    LLM_RESPONSE -->|Return| RAG_SVC
    RAG_SVC -->|Return| CHAT_SVC
    
    CHAT_SVC -->|Save| SAVE_MSG
    SAVE_MSG -->|Write| DB_SAVE
    
    CHAT_SVC -->|Queue| QUEUE_MEMORI
    
    CHAT_SVC -->|Response| CHAT_API
    CHAT_API -->|Return| USER_QUERY
    
    style USER_QUERY fill:#e3f2fd
    style CHAT_API fill:#fff3e0
    style CHAT_SVC fill:#f3e5f5
    style MEMORI_RECALL fill:#e8f5e9
    style DB_MEMORY fill:#ffebee
    style RAG_SVC fill:#f3e5f5
    style INTENT_DET fill:#e8f5e9
    style PATTERN_MATCH fill:#fff9c4
    style LLM_CLASSIFY fill:#e8f5e9
    style INTENT_RESULT fill:#c8e6c9
    style EMB_QUERY fill:#e8f5e9
    style RETRIEVER fill:#e8f5e9
    style PGVECTOR_SEARCH fill:#ffebee
    style RERANK fill:#e8f5e9
    style CONTEXT_BUILD fill:#f3e5f5
    style LLM_CHAIN fill:#e0f2f1
    style PROVIDER_1 fill:#e0f2f1
    style PROVIDER_2 fill:#e0f2f1
    style PROVIDER_3 fill:#e0f2f1
    style PROVIDER_4 fill:#e0f2f1
    style PROVIDER_5 fill:#e0f2f1
    style LLM_RESPONSE fill:#c8e6c9
    style SAVE_MSG fill:#f3e5f5
    style DB_SAVE fill:#ffebee
    style QUEUE_MEMORI fill:#fff9c4
```

---

## 4. Flow Memori Knowledge Graph - Detailed Design

```mermaid
graph TB
    subgraph "TRIGGER"
        CHAT_COMPLETE["✅ Chat Response Sent<br/>━━━━━━━━━━━━━━<br/>Message count % 2 == 0"]
    end
    
    subgraph "QUEUE"
        CELERY_QUEUE_M["⚙️ Celery Queue<br/>━━━━━━━━━━━━━━<br/>memori_extraction_task<br/>conversation_id<br/>workspace_id<br/>user_id"]
    end
    
    subgraph "WORKER"
        MEMORI_WORKER["🧠 Memori Worker<br/>━━━━━━━━━━━━━━<br/>Background processing<br/>Non-blocking"]
    end
    
    subgraph "DATA FETCH"
        GET_MESSAGES["📨 Get Messages<br/>━━━━━━━━━━━━━━<br/>Last 6 messages<br/>(3 exchanges)"]
        DB_MESSAGES["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>SELECT messages<br/>ORDER BY created_at<br/>LIMIT 6"]
    end
    
    subgraph "FACT EXTRACTION"
        BUILD_PROMPT_F["📝 Build Prompt<br/>━━━━━━━━━━━━━━<br/>Extract:<br/>• Facts<br/>• Preferences<br/>• Attributes"]
        LLM_EXTRACT_F["🤖 LLM Extract<br/>━━━━━━━━━━━━━━<br/>Cloud Code<br/>DeepSeek<br/>Gemini"]
        PARSE_FACTS["📊 Parse Results<br/>━━━━━━━━━━━━━━<br/>JSON format<br/>facts: []<br/>preferences: {}<br/>attributes: {}"]
    end
    
    subgraph "TRIPLE EXTRACTION"
        BUILD_PROMPT_T["📝 Build Prompt<br/>━━━━━━━━━━━━━━<br/>Extract triples:<br/>• Subject-Predicate-Object<br/>• Temporal (valid_at, invalid_at)<br/>• Pronoun resolution"]
        LLM_EXTRACT_T["🤖 LLM Extract<br/>━━━━━━━━━━━━━━<br/>Cloud Code<br/>DeepSeek<br/>Gemini"]
        PARSE_TRIPLES["📊 Parse Triples<br/>━━━━━━━━━━━━━━<br/>JSON array<br/>[{s, p, o, valid_at, invalid_at}]"]
    end
    
    subgraph "VALIDATION"
        VALIDATE_TRIPLES["✅ Validate Triples<br/>━━━━━━━━━━━━━━<br/>• Filter invalid<br/>• Deduplicate<br/>• Check quality"]
    end
    
    subgraph "CONTRADICTION CHECK"
        GET_EXISTING["📚 Get Existing Triples<br/>━━━━━━━━━━━━━━<br/>WHERE entity_id<br/>AND expired_at IS NULL"]
        DB_EXISTING["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>memori_knowledge_graph"]
        CHECK_CONFLICT{"Contradiction<br/>Detected?"}
        INVALIDATE["❌ Invalidate Old<br/>━━━━━━━━━━━━━━<br/>UPDATE<br/>expired_at = NOW()"]
    end
    
    subgraph "STORAGE"
        STORE_FACTS["💾 Store Facts<br/>━━━━━━━━━━━━━━<br/>• Generate embeddings<br/>• Calculate importance<br/>• INSERT facts"]
        STORE_TRIPLES["💾 Store Triples<br/>━━━━━━━━━━━━━━<br/>• INSERT triples<br/>• Set temporal fields<br/>• Link to conversation"]
        STORE_PREFS["💾 Store Preferences<br/>━━━━━━━━━━━━━━<br/>• Category mapping<br/>• Importance scoring<br/>• INSERT preferences"]
        STORE_ATTRS["💾 Store Attributes<br/>━━━━━━━━━━━━━━<br/>• Category mapping<br/>• Importance scoring<br/>• INSERT attributes"]
        DB_STORE["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━<br/>memori_entity_facts<br/>memori_knowledge_graph<br/>memori_preferences<br/>memori_attributes"]
    end
    
    CHAT_COMPLETE -->|Queue| CELERY_QUEUE_M
    CELERY_QUEUE_M -->|Pick| MEMORI_WORKER
    
    MEMORI_WORKER -->|Fetch| GET_MESSAGES
    GET_MESSAGES -->|Query| DB_MESSAGES
    DB_MESSAGES -->|Messages| GET_MESSAGES
    GET_MESSAGES -->|Messages| MEMORI_WORKER
    
    MEMORI_WORKER -->|Extract Facts| BUILD_PROMPT_F
    BUILD_PROMPT_F -->|Prompt| LLM_EXTRACT_F
    LLM_EXTRACT_F -->|Response| PARSE_FACTS
    
    MEMORI_WORKER -->|Extract Triples| BUILD_PROMPT_T
    BUILD_PROMPT_T -->|Prompt| LLM_EXTRACT_T
    LLM_EXTRACT_T -->|Response| PARSE_TRIPLES
    
    PARSE_TRIPLES -->|Validate| VALIDATE_TRIPLES
    
    VALIDATE_TRIPLES -->|Check| GET_EXISTING
    GET_EXISTING -->|Query| DB_EXISTING
    DB_EXISTING -->|Existing triples| CHECK_CONFLICT
    
    CHECK_CONFLICT -->|Yes| INVALIDATE
    CHECK_CONFLICT -->|No| STORE_TRIPLES
    INVALIDATE -->|Update| DB_STORE
    INVALIDATE -->|Then| STORE_TRIPLES
    
    PARSE_FACTS -->|Facts| STORE_FACTS
    PARSE_FACTS -->|Preferences| STORE_PREFS
    PARSE_FACTS -->|Attributes| STORE_ATTRS
    
    STORE_FACTS -->|Write| DB_STORE
    STORE_TRIPLES -->|Write| DB_STORE
    STORE_PREFS -->|Write| DB_STORE
    STORE_ATTRS -->|Write| DB_STORE
    
    style CHAT_COMPLETE fill:#c8e6c9
    style CELERY_QUEUE_M fill:#fff9c4
    style MEMORI_WORKER fill:#fff9c4
    style GET_MESSAGES fill:#e8f5e9
    style DB_MESSAGES fill:#ffebee
    style BUILD_PROMPT_F fill:#e8f5e9
    style LLM_EXTRACT_F fill:#e0f2f1
    style PARSE_FACTS fill:#e8f5e9
    style BUILD_PROMPT_T fill:#e8f5e9
    style LLM_EXTRACT_T fill:#e0f2f1
    style PARSE_TRIPLES fill:#e8f5e9
    style VALIDATE_TRIPLES fill:#c8e6c9
    style GET_EXISTING fill:#e8f5e9
    style DB_EXISTING fill:#ffebee
    style CHECK_CONFLICT fill:#fff9c4
    style INVALIDATE fill:#ffcdd2
    style STORE_FACTS fill:#e8f5e9
    style STORE_TRIPLES fill:#e8f5e9
    style STORE_PREFS fill:#e8f5e9
    style STORE_ATTRS fill:#e8f5e9
    style DB_STORE fill:#ffebee
```

---

## 5. LLM Provider Fallback Chain - Detailed Design

```mermaid
graph TB
    subgraph "REQUEST"
        LLM_REQUEST["🤖 LLM Request<br/>━━━━━━━━━━━━━━<br/>question<br/>context<br/>model (optional)"]
    end
    
    subgraph "PRIORITY 1 - CLOUD CODE"
        TRY_CC["☁️ Try Cloud Code<br/>━━━━━━━━━━━━━━<br/>FREE Claude/Gemini<br/>Best quality"]
        CC_SUCCESS{"Success?"}
        CC_RESPONSE["✅ Response<br/>━━━━━━━━━━━━━━<br/>answer<br/>provider: cloudcode<br/>model: gemini-3-flash"]
    end
    
    subgraph "PRIORITY 2 - DEEPSEEK"
        TRY_DS["🤖 Try DeepSeek<br/>━━━━━━━━━━━━━━<br/>$0.14/1M tokens<br/>Strong & cheap"]
        DS_SUCCESS{"Success?"}
        DS_RESPONSE["✅ Response<br/>━━━━━━━━━━━━━━<br/>answer<br/>provider: deepseek<br/>model: deepseek-chat"]
    end
    
    subgraph "PRIORITY 3 - GEMINI"
        TRY_GM["🔮 Try Gemini<br/>━━━━━━━━━━━━━━<br/>Free tier: 15 RPM<br/>Good quality"]
        GM_SUCCESS{"Success?"}
        GM_RESPONSE["✅ Response<br/>━━━━━━━━━━━━━━<br/>answer<br/>provider: gemini<br/>model: gemini-1.5-flash"]
    end
    
    subgraph "PRIORITY 4 - GROQ"
        TRY_GQ["⚡ Try Groq<br/>━━━━━━━━━━━━━━<br/>Free tier: 30 RPM<br/>Fast inference"]
        GQ_SUCCESS{"Success?"}
        GQ_RESPONSE["✅ Response<br/>━━━━━━━━━━━━━━<br/>answer<br/>provider: groq<br/>model: llama-3.3-70b"]
    end
    
    subgraph "PRIORITY 5 - OLLAMA"
        TRY_OL["🏠 Try Ollama<br/>━━━━━━━━━━━━━━<br/>Local fallback<br/>Always available"]
        OL_RESPONSE["✅ Response<br/>━━━━━━━━━━━━━━<br/>answer<br/>provider: ollama<br/>model: qwen2.5:7b"]
    end
    
    subgraph "ERROR HANDLING"
        LOG_ERROR["📝 Log Error<br/>━━━━━━━━━━━━━━<br/>• Provider name<br/>• Error type<br/>• Timestamp"]
        KEY_MANAGER["🔑 API Key Manager<br/>━━━━━━━━━━━━━━<br/>• Mark quota exceeded<br/>• Cooldown 1 hour<br/>• Rotate to next key"]
    end
    
    subgraph "FINAL RESPONSE"
        RETURN["✅ Return to Caller<br/>━━━━━━━━━━━━━━<br/>(answer, provider, model,<br/>prompt_tokens, completion_tokens,<br/>latency_ms)"]
    end
    
    LLM_REQUEST -->|Try| TRY_CC
    TRY_CC -->|Check| CC_SUCCESS
    CC_SUCCESS -->|Yes| CC_RESPONSE
    CC_SUCCESS -->|No/Quota| LOG_ERROR
    
    LOG_ERROR -->|Fallback| TRY_DS
    TRY_DS -->|Check| DS_SUCCESS
    DS_SUCCESS -->|Yes| DS_RESPONSE
    DS_SUCCESS -->|No/Quota| LOG_ERROR
    
    LOG_ERROR -->|Fallback| TRY_GM
    TRY_GM -->|Check| GM_SUCCESS
    GM_SUCCESS -->|Yes| GM_RESPONSE
    GM_SUCCESS -->|No/Quota| LOG_ERROR
    
    LOG_ERROR -->|Fallback| TRY_GQ
    TRY_GQ -->|Check| GQ_SUCCESS
    GQ_SUCCESS -->|Yes| GQ_RESPONSE
    GQ_SUCCESS -->|No/Quota| LOG_ERROR
    
    LOG_ERROR -->|Final Fallback| TRY_OL
    TRY_OL -->|Always| OL_RESPONSE
    
    CC_RESPONSE -->|Return| RETURN
    DS_RESPONSE -->|Return| RETURN
    GM_RESPONSE -->|Return| RETURN
    GQ_RESPONSE -->|Return| RETURN
    OL_RESPONSE -->|Return| RETURN
    
    LOG_ERROR -.->|Update| KEY_MANAGER
    
    style LLM_REQUEST fill:#e3f2fd
    style TRY_CC fill:#e0f2f1
    style CC_SUCCESS fill:#fff9c4
    style CC_RESPONSE fill:#c8e6c9
    style TRY_DS fill:#e0f2f1
    style DS_SUCCESS fill:#fff9c4
    style DS_RESPONSE fill:#c8e6c9
    style TRY_GM fill:#e0f2f1
    style GM_SUCCESS fill:#fff9c4
    style GM_RESPONSE fill:#c8e6c9
    style TRY_GQ fill:#e0f2f1
    style GQ_SUCCESS fill:#fff9c4
    style GQ_RESPONSE fill:#c8e6c9
    style TRY_OL fill:#e0f2f1
    style OL_RESPONSE fill:#c8e6c9
    style LOG_ERROR fill:#ffcdd2
    style KEY_MANAGER fill:#fff3e0
    style RETURN fill:#c8e6c9
```

---

## 6. RAG Patterns Comparison - Design Overview

```mermaid
graph TB
    subgraph "PATTERN SELECTOR"
        QUERY["📝 User Query"]
        SELECTOR{"Select<br/>Pattern"}
    end
    
    subgraph "NAIVE RAG"
        NAIVE["📚 Naive RAG<br/>━━━━━━━━━━━━━━<br/>✅ Simple<br/>✅ Fast<br/>❌ No validation<br/>━━━━━━━━━━━━━━<br/>Retrieve → Generate"]
    end
    
    subgraph "CORRECTIVE RAG"
        CORRECTIVE["🔍 Corrective RAG<br/>━━━━━━━━━━━━━━<br/>✅ Validates docs<br/>✅ Web search fallback<br/>⚠️ Slower<br/>━━━━━━━━━━━━━━<br/>Retrieve → Validate<br/>→ Correct → Generate"]
    end
    
    subgraph "SELF RAG"
        SELF["🤔 Self RAG<br/>━━━━━━━━━━━━━━<br/>✅ Self-reflection<br/>✅ Checks hallucinations<br/>⚠️ Multiple iterations<br/>━━━━━━━━━━━━━━<br/>Retrieve → Generate<br/>→ Critique → Refine"]
    end
    
    subgraph "ADAPTIVE RAG"
        ADAPTIVE["🎯 Adaptive RAG<br/>━━━━━━━━━━━━━━<br/>✅ Dynamic strategy<br/>✅ Query complexity aware<br/>✅ Cost-efficient<br/>━━━━━━━━━━━━━━<br/>Classify → Select Strategy<br/>→ Execute"]
    end
    
    subgraph "CORAG"
        CORAG["🌳 CORAG<br/>━━━━━━━━━━━━━━<br/>✅ MCTS optimization<br/>✅ Best chunk selection<br/>⚠️ Computationally expensive<br/>━━━━━━━━━━━━━━<br/>Build Tree → Search<br/>→ Select Best Path"]
    end
    
    subgraph "CORAL"
        CORAL["💬 CORAL<br/>━━━━━━━━━━━━━━<br/>✅ Multi-turn conversation<br/>✅ Context tracking<br/>✅ Pronoun resolution<br/>━━━━━━━━━━━━━━<br/>Track Context → Enhance<br/>→ Retrieve → Generate"]
    end
    
    subgraph "REVEAL"
        REVEAL["🖼️ REVEAL<br/>━━━━━━━━━━━━━━<br/>✅ Multimodal (text+image)<br/>✅ Fusion strategies<br/>⚠️ Requires vision model<br/>━━━━━━━━━━━━━━<br/>Process Text & Image<br/>→ Fuse → Generate"]
    end
    
    subgraph "SPECULATIVE RAG"
        SPECULATIVE["⚡ Speculative RAG<br/>━━━━━━━━━━━━━━<br/>✅ 40% faster<br/>✅ 30% cheaper<br/>✅ Parallel drafts<br/>━━━━━━━━━━━━━━<br/>Generate 3 Drafts<br/>→ Verify → Select Best"]
    end
    
    QUERY -->|Analyze| SELECTOR
    
    SELECTOR -->|Simple query| NAIVE
    SELECTOR -->|Need validation| CORRECTIVE
    SELECTOR -->|Need reflection| SELF
    SELECTOR -->|Complex query| ADAPTIVE
    SELECTOR -->|Optimize cost| CORAG
    SELECTOR -->|Multi-turn| CORAL
    SELECTOR -->|Multimodal| REVEAL
    SELECTOR -->|Speed priority| SPECULATIVE
    
    style QUERY fill:#e3f2fd
    style SELECTOR fill:#fff9c4
    style NAIVE fill:#e8f5e9
    style CORRECTIVE fill:#fff3e0
    style SELF fill:#f3e5f5
    style ADAPTIVE fill:#e1f5ff
    style CORAG fill:#fce4ec
    style CORAL fill:#f1f8e9
    style REVEAL fill:#fce4ec
    style SPECULATIVE fill:#e0f2f1
```

---

**Tác giả**: AI Engineering Team  
**Ngày cập nhật**: January 26, 2026  
**Phiên bản**: 1.0 (Design Diagrams)
