# PlantUML Architecture Diagrams - Tổng Hợp

> **Tài liệu này**: Tổng hợp tất cả sơ đồ kiến trúc PlantUML cho hệ thống RAG

---

## 🎉 Đã Hoàn Thành

Tôi đã tạo **10 file PlantUML (.puml)** chi tiết cho tất cả các flow trong hệ thống RAG của bạn!

---

## 📁 Cấu Trúc Files

```
RAG-Anything/docs/plantuml/
├── README.md                              # Hướng dẫn sử dụng chi tiết
├── INDEX.md                               # Index tổng hợp tất cả diagrams
├── generate-all.sh                        # Script generate cho Linux/macOS
├── generate-all.bat                       # Script generate cho Windows
│
├── 01-overall-architecture.puml           # Kiến trúc tổng thể
├── 02-upload-ocr-flow.puml               # Flow Upload & OCR
├── 03-rag-chat-flow.puml                 # Flow RAG Chat Query
├── 04-memori-knowledge-graph-flow.puml   # Flow Memori Knowledge Graph
├── 05-llm-fallback-chain.puml            # LLM Provider Fallback Chain
├── 06-rag-patterns-overview.puml         # Tổng quan RAG Patterns
├── 07-corrective-rag-detail.puml         # Chi tiết Corrective RAG
├── 08-self-rag-detail.puml               # Chi tiết Self RAG
├── 09-speculative-rag-detail.puml        # Chi tiết Speculative RAG
└── 10-deployment-architecture.puml       # Deployment Architecture
```

---

## 📊 Danh Sách Diagrams

### 1. Overall Architecture (Component Diagram)
**File:** `01-overall-architecture.puml`

**Nội dung:**
- 5 layers: Presentation, API Gateway, Service (Core + AI), Workers, Data, External
- Tất cả components: Web, Nginx, FastAPI, Services, Workers, Databases
- Connections giữa các components
- RAG patterns supported
- LLM fallback chain (5 levels)

**Màu sắc:**
- 🔵 Presentation Layer: `#E1F5FF`
- 🟠 API Gateway: `#FFF3E0`
- 🟣 Service Core: `#F3E5F5`
- 🟢 Service AI: `#E8F5E9`
- 🟡 Workers: `#FFF9C4`
- 🔴 Data Layer: `#FFEBEE`
- 🔷 External: `#E0F2F1`

---

### 2. Upload & OCR Flow (Sequence Diagram)
**File:** `02-upload-ocr-flow.puml`

**Phases:**
1. **Upload & Validation**: File validation, create document
2. **Background Processing**: Celery worker picks up job
3. **Parsing**: RAGAnything (Graph RAG) vs Docling (Naive RAG)
4. **Chunking & Embedding**: 500 tokens, 50 overlap, 768-dim vectors
5. **Finalization**: Store outputs, update status to READY

**Participants:**
- User, API, DocumentService, PostgreSQL, MinIO/S3
- Celery Queue, OCR Worker, Parser, EmbeddingService

---

### 3. RAG Chat Flow (Sequence Diagram)
**File:** `03-rag-chat-flow.puml`

**Phases:**
1. **Receive Question**: Save user message
2. **Memory Recall**: Get facts & triples from Memori
3. **Intent Detection**: Pattern matching + LLM fallback
4. **Vector Search**: Embed query, search chunks với pgvector
5. **Reranking**: Cross-encoder (+15-20% precision)
6. **Generate Answer**: LLM với fallback chain
7. **Save Response**: Store message, citations, usage
8. **Queue Memori**: Background fact extraction

**Participants:**
- User, API, ChatService, MemoriManager, RAGService
- IntentDetector, EmbeddingService, RetrieverService
- PostgreSQL, pgvector, LLM Providers, Celery Queue

---

### 4. Memori Knowledge Graph (Sequence Diagram)
**File:** `04-memori-knowledge-graph-flow.puml`

**Phases:**
1. **Trigger**: After every 2 messages (message_count % 2 == 0)
2. **Background Extraction**: Get last 6 messages (3 exchanges)
3. **Fact Extraction**: Facts, preferences, attributes
4. **Triple Extraction**: Subject-Predicate-Object với temporal
5. **Validation**: Filter invalid triples
6. **Contradiction Check**: "Latest wins" policy
7. **Store Facts**: With embeddings & importance score
8. **Store Preferences**: Category mapping
9. **Store Attributes**: Category mapping

**Participants:**
- ChatService, Celery Queue, Memori Worker
- MemoriManager, LLM Providers, PostgreSQL

**Highlights:**
- Bi-temporal model (valid_at, invalid_at)
- Pronoun resolution (tôi, mình → user)
- Contradiction detection & resolution

---

### 5. LLM Fallback Chain (Sequence Diagram)
**File:** `05-llm-fallback-chain.puml`

**Priority Levels:**
1. **Cloud Code** (Priority 1): FREE Claude/Gemini, best quality
2. **DeepSeek** (Priority 2): $0.14/1M tokens, strong & cheap
3. **Gemini** (Priority 3): Free tier 15 RPM, good quality
4. **Groq** (Priority 4): Free tier 30 RPM, fast inference
5. **Ollama** (Priority 5): Local fallback, always available

**Participants:**
- RAGService, Cloud Code, DeepSeek, Gemini, Groq, Ollama
- API Key Manager, Redis Cache

**Features:**
- Auto fallback on quota exceeded
- API key rotation
- Cooldown period (1 hour)
- Success/failure tracking

---

### 6. RAG Patterns Overview (Component Diagram)
**File:** `06-rag-patterns-overview.puml`

**8 Patterns:**
1. **Naive RAG**: Simple, fast, no validation
2. **Corrective RAG**: Validates docs, web search fallback
3. **Self RAG**: Self-reflection, checks hallucinations
4. **Adaptive RAG**: Dynamic strategy, query complexity aware
5. **CORAG**: MCTS optimization, best chunk selection
6. **CORAL**: Multi-turn conversation, context tracking
7. **REVEAL**: Multimodal (text + image)
8. **Speculative RAG**: Parallel drafts, 40% faster

**Comparison Table:**
| Pattern | Speed | Quality | Cost | Use Case |
|---------|-------|---------|------|----------|
| Naive | ⚡⚡⚡ | ⭐⭐ | 💰 | Simple Q&A |
| Corrective | ⚡⚡ | ⭐⭐⭐ | 💰💰 | Need accuracy |
| Self | ⚡ | ⭐⭐⭐⭐ | 💰💰💰 | Critical apps |
| Adaptive | ⚡⚡ | ⭐⭐⭐ | 💰💰 | Mixed queries |
| CORAG | ⚡ | ⭐⭐⭐⭐ | 💰💰💰 | Complex research |
| CORAL | ⚡⚡ | ⭐⭐⭐ | 💰💰 | Conversations |
| REVEAL | ⚡⚡ | ⭐⭐⭐⭐ | 💰💰💰 | Multimodal |
| Speculative | ⚡⚡⚡ | ⭐⭐⭐ | 💰 | High throughput |

---

### 7. Corrective RAG Detail (Sequence Diagram)
**File:** `07-corrective-rag-detail.puml`

**Flow:**
1. Retrieve top-k documents (k=10, more than needed)
2. Validate relevance với LLM (score 0.0-1.0)
3. Filter low-quality docs (score < 0.6)
4. If not enough relevant docs → Web search
5. Merge & re-sort documents
6. Generate answer với validated docs

**Benefits:**
- +15% accuracy vs Naive RAG
- Self-correcting
- Handles low-quality documents

**Trade-offs:**
- 2-3x slower
- More LLM calls

---

### 8. Self RAG Detail (Sequence Diagram)
**File:** `08-self-rag-detail.puml`

**Flow:**
1. Retrieve documents
2. Generate candidate answer
3. Self-critique với 3 checks:
   - **Relevance**: Is answer relevant to question?
   - **Grounding**: Is answer grounded in docs? (No hallucinations)
   - **Utility**: Is answer useful & complete?
4. If checks pass → Return answer
5. If checks fail → Refine & retry (max 3 iterations)

**Benefits:**
- Highest quality answers
- Detects hallucinations
- Confidence scores

**Trade-offs:**
- Slowest (3-5s)
- Most expensive

---

### 9. Speculative RAG Detail (Sequence Diagram)
**File:** `09-speculative-rag-detail.puml`

**Flow:**
1. Retrieve documents
2. Small model generates 3 drafts in parallel:
   - Draft 1: Comprehensive (temp=0.7)
   - Draft 2: Concise (temp=0.5)
   - Draft 3: Creative (temp=0.9)
3. Large model verifies & scores each draft
4. Select best draft or merge them

**Performance:**
- **Latency**: 1.8s (vs 3.0s traditional) → 40% faster
- **Cost**: $0.002 (vs $0.003 traditional) → 30% cheaper
- **Quality**: 8.3/10 (vs 8.5/10 traditional) → -2%

**Benefits:**
- Much faster
- Much cheaper
- Good quality

---

### 10. Deployment Architecture (Deployment Diagram)
**File:** `10-deployment-architecture.puml`

**Components:**
- **Load Balancer**: Nginx (SSL, rate limiting)
- **Application Server**: Frontend + Backend + Workers
- **Database Server**: PostgreSQL 15 + pgvector
- **Cache Server**: Redis 7
- **Storage Server**: MinIO/S3
- **External Services**: LLM providers
- **GPU Server**: Ollama (optional)

**Docker Compose Services:**
- frontend (React, port 3000)
- backend (FastAPI, port 8000, 4 workers)
- celery-worker-ocr (concurrency 2)
- celery-worker-memori (concurrency 2)
- celery-beat (scheduled tasks)
- postgres (pgvector extension)
- redis (cache + queue)
- minio (object storage)
- nginx (reverse proxy)

---

## 🚀 Cách Sử Dụng

### 1. View Online (Nhanh nhất)

**PlantUML Online:**
```
1. Truy cập: https://www.plantuml.com/plantuml/uml/
2. Copy nội dung file .puml
3. Paste vào editor
4. Click "Submit"
5. Download PNG/SVG
```

**PlantText:**
```
1. Truy cập: https://www.planttext.com/
2. Paste code
3. Real-time preview
4. Export PNG/SVG/PDF
```

### 2. VS Code Extension

**Cài đặt:**
```bash
code --install-extension jebbs.plantuml
```

**Sử dụng:**
```
1. Mở file .puml trong VS Code
2. Press Alt + D để preview
3. Right-click → "Export Current Diagram"
```

### 3. Command Line

**Generate tất cả diagrams:**

**Linux/macOS:**
```bash
cd RAG-Anything/docs/plantuml
chmod +x generate-all.sh
./generate-all.sh png
```

**Windows:**
```cmd
cd RAG-Anything\docs\plantuml
generate-all.bat png
```

**Docker:**
```bash
cd RAG-Anything/docs/plantuml
docker run --rm -v $(pwd):/data plantuml/plantuml -tpng /data/*.puml
```

**Output:**
```
Diagrams sẽ được generate vào folder: output/
- 01-overall-architecture.png
- 02-upload-ocr-flow.png
- 03-rag-chat-flow.png
- ...
```

---

## 📚 Documentation Files

| File | Mô Tả |
|------|-------|
| `README.md` | Hướng dẫn chi tiết cách sử dụng PlantUML |
| `INDEX.md` | Index tổng hợp tất cả diagrams với links |
| `generate-all.sh` | Script generate cho Linux/macOS |
| `generate-all.bat` | Script generate cho Windows |

---

## 🎯 Use Cases

### Cho Sinh Viên (Đồ án)
✅ Hiểu kiến trúc hệ thống RAG  
✅ Học các RAG patterns  
✅ Implement từng flow  
✅ Viết báo cáo đồ án  

### Cho Developers
✅ Onboarding nhanh  
✅ Debug issues  
✅ Optimize performance  
✅ Code review  

### Cho Architects
✅ System design  
✅ Pattern selection  
✅ Infrastructure planning  
✅ Technical documentation  

---

## 🎨 Đặc Điểm

### ✅ Chi Tiết & Đầy Đủ
- Tất cả flows được vẽ chi tiết
- Mỗi phase có giải thích rõ ràng
- Code examples trong notes
- Performance metrics

### ✅ Màu Sắc Rõ Ràng
- Mỗi layer có màu riêng
- Dễ phân biệt components
- Professional design

### ✅ Dễ Customize
- PlantUML syntax đơn giản
- Có thể edit dễ dàng
- Export nhiều formats (PNG, SVG, PDF)

### ✅ Production Ready
- Deployment architecture
- Docker Compose setup
- Configuration examples
- Best practices

---

## 📖 Tài Liệu Liên Quan

Các tài liệu khác trong project:

1. **ARCHITECTURE_DESIGN_DIAGRAMS.md** - Mermaid diagrams (design-style)
2. **SYSTEM_ARCHITECTURE_DIAGRAM.md** - Text-based chi tiết
3. **DATABASE_SCHEMA_FOR_STUDENT_PROJECT.md** - Database schema
4. **ERD_DIAGRAM.md** - Entity Relationship Diagram
5. **USE_CASE_DIAGRAM.md** - Use cases & sequence diagrams
6. **API_ENDPOINTS_SUMMARY.md** - API documentation

---

## 🔗 Links

**PlantUML Resources:**
- Official: https://plantuml.com/
- Sequence Diagram: https://plantuml.com/sequence-diagram
- Component Diagram: https://plantuml.com/component-diagram
- Deployment Diagram: https://plantuml.com/deployment-diagram

**Tools:**
- VS Code Extension: https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml
- Online Editor: https://www.plantuml.com/plantuml/uml/
- PlantText: https://www.planttext.com/

---

## ✨ Highlights

### So với Mermaid Diagrams:

| Feature | PlantUML | Mermaid |
|---------|----------|---------|
| **Syntax** | More verbose | Simpler |
| **Features** | More powerful | Basic |
| **Customization** | Extensive | Limited |
| **Export** | PNG, SVG, PDF, LaTeX | PNG, SVG |
| **Offline** | Yes (with Java) | Yes (with CLI) |
| **GitHub Support** | No (need image) | Yes (native) |
| **Professional** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

### Khi nào dùng PlantUML:
✅ Cần diagrams chi tiết & professional  
✅ Export nhiều formats  
✅ Customization cao  
✅ Báo cáo, presentation, documentation  

### Khi nào dùng Mermaid:
✅ Quick diagrams trong Markdown  
✅ GitHub README  
✅ Simple & fast  
✅ No installation needed  

---

## 🎉 Kết Luận

Bạn đã có **10 file PlantUML** chi tiết cho tất cả flows trong hệ thống RAG!

**Điểm mạnh:**
- ✅ Chi tiết & đầy đủ nhất
- ✅ Professional design
- ✅ Dễ customize
- ✅ Export nhiều formats
- ✅ Phù hợp cho đồ án sinh viên

**Next Steps:**
1. Generate diagrams: `./generate-all.sh png`
2. View trong VS Code với PlantUML extension
3. Hoặc view online tại: https://www.plantuml.com/plantuml/uml/
4. Sử dụng trong báo cáo đồ án

---

**Tác giả**: AI Engineering Team  
**Ngày tạo**: January 26, 2026  
**Phiên bản**: 1.0

**Liên hệ**: Nếu cần thêm diagrams hoặc customize, hãy cho tôi biết!
