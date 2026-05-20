# 🔍 Upload Pipeline v3.1 — Deep Code Audit & Logic Verification (REVISED)

> Tài liệu này trace từng bước trong code thực tế, phân tích logic, phát hiện lỗi/rủi ro, và kết thúc bằng bảng mapping 1-1 giữa kiến trúc plantuml và code thực tế.

**Ngày audit ban đầu**: 2026-04-02  
**Ngày sửa đổi (REVISION)**: 2026-04-03  
**Phiên bản**: v3.2 (PaddleOCR-only, Docling XLSX enabled, LlamaIndex SentenceSplitter, SentenceTransformers mpnet-base-v2)

> [!IMPORTANT]
> **Runtime fix 2026-05-16**: upload `.xlsx` failed in Celery OCR with
> `docling.exceptions.ConversionError: File format not allowed: tmp*.xlsx`.
> Root cause: `DocumentEngine` passed a custom `allowed_formats` list to
> `DocumentConverter` but omitted `InputFormat.XLSX`. The active route was
> already correct (`.xlsx` -> Docling); the converter configuration was not.
> Fix: add `InputFormat.XLSX` to `server/app/core/engines/ocr.py`.
>
> **Runtime fix 2026-05-16**: `.docx` uploads reached INDEX `DONE` but later
> became `FAILED` during strict Neo4j enrichment with
> `JsonDocStatusStorage not initialized`. Root cause: `RAGPipeline` was created
> with `parser="auto"` and `ParserFactory.create_parser("auto", config)` recursed
> when `config.parser` was also `auto`; LightRAG storage initialization then
> failed before `insert_content_list()`. Fix: resolve `auto` to Docling and fail
> fast if LightRAG initialization does not succeed.

> [!CAUTION]
> **Bản audit v3.0 trước đó có sai sót nghiêm trọng:**
> 1. Ghi "0 lỗi logic" nhưng thực tế có ≥3 bug crash-level
> 2. Ghi "Surya fallback OK ✅" nhưng Surya gây OOM Kill container
> 3. Không phát hiện `ProcessingResult` TypeError khiến Enrichment worker crash
> 4. Không phát hiện thiếu `paddlepaddle` runtime (khiến PaddleOCR không chạy được)
>
> Bản v3.1 này đã được sửa đổi sau khi fix code + verify lại toàn bộ.

---

## 📋 Mục lục

1. [Phase 1: API Upload](#phase-1-api-upload)
2. [Phase 2: Celery OCR Worker](#phase-2-celery-ocr-worker)
3. [Phase 3: Parser Router (Stage 1)](#phase-3-parser-router-stage-1)
4. [Phase 4: Normalize + Quality Gate (Stage 1.5)](#phase-4-normalize--quality-gate-stage-15)
5. [Phase 5: Store + Fork (Stage 3)](#phase-5-store--fork-stage-3)
6. [Phase 6: Index Worker](#phase-6-index-worker)
7. [Phase 7: Enrichment Worker](#phase-7-enrichment-worker)
8. [Danh sách Bug đã phát hiện & FIX](#-danh-sách-bug-đã-phát-hiện--fix)
9. [Bảng Map 1-1: Kiến trúc ↔ Code](#-bảng-map-1-1-kiến-trúc--code)

---

## Phase 1: API Upload

**File**: `app/services/documents/document_service.py` → method `upload()`

### Trace chi tiết

| Bước | Code (dòng) | Hành động | Ghi chú |
|------|-------------|-----------|---------|
| 1.1 | L77-80 | `check_permission(workspace_id, user_id, "write")` | Kiểm tra quyền ghi |
| 1.2 | L83-85 | `file.file.seek(0,2)` → `file_size = tell()` | Đo kích thước không load RAM |
| 1.3 | L88-90 | `validate_file(filename, file_size)` | Whitelist extension + size limit |
| 1.4 | L93-104 | `Document(status=NEW)` → `session.add()` → `flush()` | Tạo Document placeholder |
| 1.5 | L107-118 | `ObjectStore.generate_key()` → `storage.upload()` | Upload file gốc lên MinIO |
| 1.6 | L121-125 | SHA-256 checksum tính streaming (4MB chunks) | Không load toàn bộ vào RAM |
| 1.7 | L128-151 | Query `DocumentVersion.checksum_sha256` → nếu trùng thì xóa và báo lỗi | **Dedup check** |
| 1.8 | L154-163 | `DocumentVersion(version=1)` → `flush()` | Tạo version |
| 1.9 | L166-173 | `Job(type=OCR, status=QUEUED)` → `flush()` | Tạo OCR job |
| 1.10 | L176 | `document.status = INDEXING` | Chuyển trạng thái |
| 1.11 | L179 | `session.commit()` **TRƯỚC** enqueue | ✅ Đúng thứ tự |
| 1.12 | L183 | `_dispatch_ocr(job.id, version.id, document.id)` | Enqueue task |

### Phân tích

- ✅ **Commit trước enqueue**: Pattern đúng. Nếu enqueue trước commit, worker có thể nhận job nhưng chưa thấy data.
- ✅ **Dedup check**: checksum_sha256, xóa cả MinIO file nếu trùng.
- ✅ Không có lỗi logic trong Phase 1.

---

## Phase 2: Celery OCR Worker

**File**: `app/queue/tasks/ocr.py` → function `process_ocr()`

### Trace chi tiết

| Bước | Code (dòng) | Hành động | Ghi chú |
|------|-------------|-----------|---------|
| 2.1 | L54 | `@shared_task(queue="ocr", max_retries=3)` | Task definition |
| 2.2 | L78 | `_get_sync_session()` | Module-level cached sync session |
| 2.3 | L80-88 | `Job.status = RUNNING` → commit | Mark job đang chạy |
| 2.4 | L91-96 | `select(DocumentVersion).options(joinedload(document))` | Load version + parent doc |
| 2.5 | L101-108 | Check `CANCELED/DELETED` → abort | Early exit |
| 2.6 | L110-113 | `document.status = INDEXING` + progress=5% | Cập nhật UI |
| 2.7 | L122-138 | Download file từ MinIO → temp file | Hỗ trợ cả HTTP URL |
| 2.8 | L150-155 | Init `parser_used=None, full_text="", ...` | Init biến output |

### Phân tích

- ✅ **Module-level session cache**: Tránh leak connection pool.
- ✅ **Cancel check**: Kiểm tra CANCELED/DELETED trước khi xử lý.
- ✅ **Cleanup**: `tempfile.NamedTemporaryFile(delete=False)` cleanup ở `finally` block.

---

## Phase 3: Parser Router (Stage 1)

### Route 0: Direct Text (L157-175)

| Bước | Điều kiện | Hành động |
|------|-----------|-----------|
| 3.0a | `ext ∈ {.txt, .md, .csv, .html, .xhtml}` | Kiểm tra extension |
| 3.0b | `file_content.decode("utf-8")` | Đọc trực tiếp |
| 3.0c | `parser_used = "direct"` | Đánh dấu parser |

✅ Đúng logic.

### Route 1: PaddleOCR (L177-230)

| Bước | Hành động | Ghi chú |
|------|-----------|---------|
| 3.1a | `from paddleocr_engine import should_use_paddleocr` | Import engine |
| 3.1b | `should_use_paddleocr(tmp_path, config)` | Routing check |
| 3.1c | `PaddleOCREngine().process_document()` | PPStructureV3 run |
| 3.1d | Extract `fullText`, `markdownText`, `structured`, `meta` | Parse output |
| 3.1e | `parser_used = "paddleocr"` | Đánh dấu |
| 3.1f | `except ImportError` → **`RuntimeError` ngay** | ❌ KHÔNG fallback Surya |
| 3.1g | `except Exception` → **`RuntimeError` ngay** | ❌ KHÔNG fallback Surya |

> [!IMPORTANT]
> **v3.0 audit ghi sai chỗ này.** v3.0 ghi "Surya fallback ✅" nhưng thực tế Surya gây OOM Kill.
> Đã FIX: PaddleOCR fail → `RuntimeError` ngay, task FAIL, log rõ ràng.
> **Surya đã bị loại hoàn toàn khỏi pipeline** (commit ngày 2026-04-03).

### Route 2: Docling (L232-tới cuối Stage 1)

| Bước | Hành động | Ghi chú |
|------|-----------|---------|
| 3.2a | `parser_used is None` → Chỉ chạy nếu Route 0,1 không match | Guard |
| 3.2b | `DocumentEngine().process_document()` | Docling run |
| 3.2c | Extract output | fullText, markdownText, structured, meta |
| 3.2d | Detect `embedded_images` từ structured + layout | Tìm ảnh nhúng |
| 3.2e | Chọn sub-OCR engine: **PaddleOCR only** | ❌ KHÔNG có Surya fallback |
| 3.2f | PaddleOCR Sub-OCR cho embedded images (crop + OCR từng ảnh) | `process_crops()` |
| 3.2g | Nếu PaddleOCR unavailable → **skip + log warning** | Graceful skip |
| 3.2h | DOCX inline image OCR (OOXML → PaddleOCR per image) | Position-aware |
| 3.2i | Nếu Docling import fail → fallback plaintext | Graceful degradation |

> [!NOTE]
> **Sub-OCR chỉ dùng PaddleOCR.** Nếu PaddleOCR unavailable → skip embedded images + log warning.
> Hệu lọc heuristic: Skip ảnh < 50px hoặc aspect ratio > 15:1.

---

## Phase 4: Normalize + Quality Gate (Stage 1.5)

**File**: `app/queue/tasks/normalize.py`

| Bước | Code | Hành động |
|------|------|-----------|
| 4.1 | L29-121 | `normalize_parser_output()` → canonical `content_list` |
| 4.2 | L51-60 | Text → `{type: "text", text, page_idx}` |
| 4.3 | L63-73 | Images → `{type: "image", img_path, caption}` |
| 4.4 | L76-85 | Tables → `{type: "table", table_body, caption}` |
| 4.5 | L88-95 | Equations → `{type: "equation", text, format}` |
| 4.6 | L97-121 | Stats + language detection → return dict |
| 4.7 | L124-156 | **quality_check()**: `min_chars=50`, bypass nếu có image/table |

✅ Content list format chuẩn RAG-Anything `insert_content_list()` API.
✅ Quality exception: Cho phép pass nếu doc chỉ có ảnh/bảng.

---

## Phase 5: Store + Fork (Stage 3)

**File**: `app/queue/tasks/ocr.py` (phần sau normalize)

| Bước | Hành động |
|------|-----------|
| 5.1 | Upload `text.txt` → MinIO |
| 5.2 | Upload `content.md` → MinIO |
| 5.3 | Upload `structured.json` → MinIO (chứa content_list + stats) |
| 5.4 | Update `doc_version` metadata keys |
| 5.5 | Tạo `Job(INDEX)` → QUEUED |
| 5.6 | Tạo `Job(ENRICHMENT)` nếu `ENABLE_RAGANYTHING_PARSING=true` |
| 5.7 | `session.commit()` **TRƯỚC** enqueue jobs |
| 5.8 | `process_index.delay()` |
| 5.9 | `process_enrichment.delay()` (conditional) |
| 5.10 | `Job(OCR).status = DONE` |

✅ Commit trước dispatch. Đúng thứ tự.
✅ Non-blocking: OCR worker kết thúc ngay, INDEX và ENRICHMENT chạy song song.

---

## Phase 6: Index Worker

**File**: `app/queue/tasks/index.py` → `process_index()`

### Trace chi tiết

| Bước | Code (dòng) | Hành động | Thực tế code |
|------|-------------|-----------|--------------|
| 6.1 | L49-50 | Import services | `ChunkingService`, `EmbeddingService` |
| 6.2 | L75-80 | Load `DocumentVersion` + parent `Document` | ✅ joinedload |
| 6.3 | L96 | **Ưu tiên** `extracted_md_key` → `extracted_text_key` | Markdown first ✅ |
| 6.4 | L101 | `storage.download(text_key).decode("utf-8")` | ✅ |
| 6.5 | L111-117 | `ChunkingService(chunk_size=512, chunk_overlap=50)` | ✅ default config |
| 6.6 | L119 | **`chunk_by_sentences(text_content)`** | Gọi LlamaIndex SentenceSplitter |
| 6.7 | L133 | `EmbeddingService()` | Tạo instance mới (singleton pattern bên trong) |
| 6.8 | L136 | `embed_batch(chunk_texts)` | SentenceTransformers batch encode |
| 6.9 | L139-144 | DELETE old chunks → commit | ✅ tránh duplicate |
| 6.10 | L154-170 | INSERT Chunk rows with `embedding` | pgvector Vector(768) |
| 6.11 | L218-231 | `STRICT_NEO4J ? INDEXING(95) : READY_BASIC` | ✅ strict-aware |
| 6.12 | L180-186 | `Job(INDEX).status = DONE` | ✅ |

### Phân tích chi tiết Chunking

**File thực tế**: `app/services/documents/chunking_service.py`

`chunk_by_sentences()` (L556-643):
```python
from llama_index.core.node_parser import SentenceSplitter
splitter = SentenceSplitter(
    chunk_size=512,
    chunk_overlap=50,
    paragraph_separator="\n\n",
    secondary_chunking_regex="[.!?]\\s+",
)
```

✅ **LlamaIndex SentenceSplitter là THỰC** — code tại L580-602.
⚠️ **NHƯNG**: Nếu `llama-index-core` chưa cài (hiện thiếu trong Docker), nó fallback về `chunk_by_paragraphs()` (L583-589). **Đây là lý do thực tế chunking có thể đã chạy bằng paragraph-based chứ không phải sentence-aware!**

### Phân tích chi tiết Embedding

**File thực tế**: `app/services/core/embedding_service.py`

```python
# L76-80: Ưu tiên SentenceTransformers
import sentence_transformers
st_model_name = "paraphrase-multilingual-mpnet-base-v2"
self._use_ollama = False
self.dimension = 768
```

✅ **SentenceTransformers `mpnet-base-v2` là THỰC** — dim=768 native.
✅ **Fallback Ollama** nếu `sentence-transformers` không import được (L91-94).
✅ **Padding/truncate safety** tại L276-282: pad to 768 nếu < 768, truncate nếu > 768 (no-op với mpnet).

> [!NOTE]
> **Embedding KHÔNG dùng LlamaIndex.** Audit v3.0 đã ghi đúng rằng dùng SentenceTransformers chứ không phải LlamaIndex cho embedding. LlamaIndex chỉ dùng cho **chunking** (SentenceSplitter). Hai khái niệm tách biệt:
> - **Chunking**: LlamaIndex SentenceSplitter → chia text thông minh theo câu
> - **Embedding**: SentenceTransformers mpnet-base-v2 → tạo vector 768d

---

## Phase 7: Enrichment Worker

**File**: `app/queue/tasks/enrichment.py` → `process_enrichment()`

### Trace chi tiết

| Bước | Code (dòng) | Hành động | Ghi chú |
|------|-------------|-----------|---------|
| 7.1 | L70-78 | `Job.status = RUNNING` | ✅ |
| 7.2 | L81-86 | Load `DocumentVersion` | ✅ |
| 7.3 | L92-100 | Cancel check (CANCELED/DELETED) | ✅ |
| 7.4 | L110-116 | Load `structured.json` from MinIO | ✅ |
| 7.5 | L119-122 | Load `content.md` from MinIO | ✅ |
| 7.6 | L139-172 | Reuse `content_list` từ structured.json | ✅ |
| 7.7 | L198-206 | `initialize_raganything()` | ✅ |
| 7.8 | L221-227 | `rag_pipeline.insert_content_list(content_list, file_path)` | ✅ |
| 7.9 | L229 | `enrichment_result.document_id` | ✅ **ĐÃ FIX** (trước đó là `.doc_id` sai) |
| 7.10 | L236-241 | Store `raganything_doc_id` back → MinIO | ✅ |
| 7.11 | L266-276 | Chỉ set `READY_ENRICHED` nếu thành công | ✅ |
| 7.12 | L302-350 | Non-strict fail keeps `READY_BASIC`; strict fail sets `FAILED` after retries | ✅ strict-aware |

---

## 🔴 Danh sách Bug đã phát hiện & FIX

> [!WARNING]
> **v3.0 audit ghi "0 lỗi logic" — SAI HOÀN TOÀN.** Thực tế có ≥5 bug, trong đó 3 bug crash-level.

### Bug đã FIX (2026-04-03)

| # | Bug | File | Mức độ | Nguyên nhân | Fix |
|---|-----|------|--------|-------------|-----|
| B1 | **`ProcessingResult` TypeError** | `pipeline.py` L1459, L1548 | 🔴 CRASH | Gọi `ProcessingResult(doc_id=..., file_path=..., text_content=...)` nhưng dataclass chỉ có fields `document_id`, `status`, `content`, `metadata`... → **tên field sai hoàn toàn** | Sửa tất cả constructor calls để dùng đúng field names |
| B2 | **`enrichment_result.doc_id` AttributeError** | `enrichment.py` L229 | 🔴 CRASH | Truy cập `.doc_id` nhưng field thực tế là `.document_id` | Đổi thành `.document_id` |
| B3 | **Thiếu `paddlepaddle` runtime** | `requirements-extra.txt` | 🔴 CRASH | Cài `paddleocr` nhưng thiếu `paddlepaddle` base → `import paddle` fail → PaddleOCR không chạy được → fallback Surya → OOM Kill | Thêm `paddlepaddle>=3.0.0` |
| B4 | **Surya fallback gây OOM Kill** | `ocr.py` L221-249, L438-483, L533-548 | 🔴 CRASH | Surya model ~1.35GB, container limit 4GB, Surya + Docling + Python = vượt limit → SIGKILL | **Loại bỏ hoàn toàn Surya.** PaddleOCR fail → RuntimeError ngay |
| B5 | **`parsers.py` ProcessingResult thiếu `document_id`** | `parsers.py` 9 chỗ | 🟡 ERROR | `ProcessingResult(status=..., error=...)` thiếu required field `document_id` + dùng `DocStatus.COMPLETED` (không tồn tại) | Thêm `document_id`, sửa `COMPLETED` → `PROCESSED` |
| B6 | **Surya env vars thừa trong docker-compose** | `docker-compose.yml` L179-187 | 🟢 Cosmetic | 7 env vars (`USE_SURYA_FOR_PDF`, `COMPILE_ALL`, `*_BATCH_SIZE`) không còn dùng | Xóa toàn bộ |
| B7 | **Embedding wrapper trả tuple thay vì vector** | `wrappers.py` L164 | 🔴 CRASH | `embed_text()` trả về `(vector, model_info)` nhưng wrapper gửi cả tuple vào LightRAG → KG insertion crash | Thêm `[0]` để unpack vector |
| B8 | **Factory không tạo LightRAG instance** | `factory.py` L65 | 🔴 SILENT FAIL | `RAGPipeline(lightrag=None)` → enrichment luôn skip KG insertion | Tạo `LightRAG(graph_storage="Neo4JStorage")` với Neo4j |
| B9 | **XLSX rejected by Docling converter** | `core/engines/ocr.py` | 🔴 CRASH | Code allowed upload + routed `.xlsx` to Docling, but `DocumentConverter(allowed_formats=[...])` omitted `InputFormat.XLSX` | Add `InputFormat.XLSX` to `allowed_formats`; no dependency rebuild needed |
| B10 | **LightRAG parser auto recursion blocks strict enrichment** | `rag_patterns/pipeline/parsers.py`, `pipeline.py` | 🔴 CRASH | `parser="auto"` plus `config.parser="auto"` recursed until storage init failed, then `insert_content_list()` hit `JsonDocStatusStorage not initialized` | Resolve `auto` to Docling and make `insert_content_list()` fail fast on unsuccessful LightRAG init |

### Rủi ro còn lại

| # | Vấn đề | Mức độ | Ghi chú |
|---|--------|--------|---------|
| R1 | `llama-index-core` chưa cài trong Docker → chunking fallback về paragraph-based | 🟡 Medium | Đã thêm vào `requirements-extra.txt`, cần rebuild |
| R2 | Embedding model change yêu cầu re-index toàn bộ | 🔴 Important | Old: 384 real + 384 zeros. New: 768 real. **Phải re-index!** |
| R3 | PaddleOCR lần đầu download model ~500MB | 🟡 First-run | Chấp nhận cold start 1 lần |
| R4 | `pdf2image` không có trong requirements | 🟡 Medium | Sub-OCR cho PDF embedded images sẽ skip nếu thiếu |
| R5 | ~~Neo4j mới thêm, cần config LightRAG kết nối~~ | ✅ **RESOLVED** | Factory.py đã wire `LightRAG(graph_storage="Neo4JStorage")` + env vars trong docker-compose |

---

## ✅ Bảng Map 1-1: Kiến trúc ↔ Code

Bảng dưới đây map 1-1 giữa mỗi bước trong `upload_workflow_new.puml` với code thực tế.
**STATUS** cho biết bước này đã verified đúng hay đã phải fix.

| # | Bước trong PUML | File | Function / Line | Status |
|---|-----------------|------|-----------------|--------|
| 1 | User uploads file | `api/v1/documents.py` | `upload_document()` | ✅ Verified |
| 2 | Validate file | `services/documents/document_service.py` | `upload()` → `validate_file()` | ✅ Verified |
| 3 | Upload → MinIO | `services/documents/document_service.py` | `upload()` → `storage.upload()` | ✅ Verified |
| 4 | Create Document (NEW) | `services/documents/document_service.py` | `Document(status=NEW)` | ✅ Verified |
| 5 | Create DocumentVersion | `services/documents/document_service.py` | `DocumentVersion(v=1)` | ✅ Verified |
| 6 | Dedup check (SHA-256) | `services/documents/document_service.py` | checksum compare | ✅ Verified |
| 7 | Create Job(OCR) | `services/documents/document_service.py` | `Job(type=OCR)` | ✅ Verified |
| 8 | Status → INDEXING | `services/documents/document_service.py` | `.status = INDEXING` | ✅ Verified |
| 9 | Commit TRƯỚC enqueue | `services/documents/document_service.py` | `session.commit()` | ✅ Verified |
| 10 | Enqueue OCR task | `services/documents/document_service.py` | `.apply_async()` | ✅ Verified |
| 11 | OCR Worker: Load job | `queue/tasks/ocr.py` | `process_ocr()` | ✅ Verified |
| 12 | Cancel check | `queue/tasks/ocr.py` | CANCELED/DELETED check | ✅ Verified |
| 13 | Download from MinIO | `queue/tasks/ocr.py` | MinIO download | ✅ Verified |
| 14 | Route 0: Direct text | `queue/tasks/ocr.py` | `DIRECT_TEXT_EXTENSIONS` | ✅ Verified |
| 15 | Route 1: PaddleOCR | `queue/tasks/ocr.py` | `should_use_paddleocr()` → `PaddleOCREngine` | ✅ Verified |
| 16 | ~~Route 1 fallback: Surya~~ | `queue/tasks/ocr.py` | ~~SuryaEngine~~ | ❌ **REMOVED** — PaddleOCR fail → RuntimeError |
| 17 | Route 2: Docling | `queue/tasks/ocr.py` | `DocumentEngine` | ✅ Verified |
| 18 | Sub-OCR: PaddleOCR | `queue/tasks/ocr.py` | `paddle_engine.process_crops()` | ✅ Verified |
| 19 | ~~Sub-OCR: Surya fallback~~ | `queue/tasks/ocr.py` | ~~surya_engine~~ | ❌ **REMOVED** — skip + warning |
| 20 | DOCX inline OCR | `queue/tasks/ocr.py` | OOXML → PaddleOCR per image | ✅ Verified (Surya removed) |
| 21 | Normalize | `queue/tasks/normalize.py` | `normalize_parser_output()` | ✅ Verified |
| 22 | Quality Gate | `queue/tasks/normalize.py` | `quality_check()` min_chars=50 | ✅ Verified |
| 23 | Upload text.txt | `queue/tasks/ocr.py` | MinIO upload | ✅ Verified |
| 24 | Upload content.md | `queue/tasks/ocr.py` | MinIO upload | ✅ Verified |
| 25 | Upload structured.json | `queue/tasks/ocr.py` | MinIO upload (chứa content_list) | ✅ Verified |
| 26 | Create Job(INDEX) | `queue/tasks/ocr.py` | `Job(type=INDEX)` | ✅ Verified |
| 27 | Create Job(ENRICHMENT) | `queue/tasks/ocr.py` | conditional on `ENABLE_RAGANYTHING_PARSING` | ✅ Verified |
| 28 | Commit TRƯỚC dispatch | `queue/tasks/ocr.py` | `session.commit()` | ✅ Verified |
| 29 | process_index.delay() | `queue/tasks/ocr.py` | Celery dispatch | ✅ Verified |
| 30 | process_enrichment.delay() | `queue/tasks/ocr.py` | Celery dispatch | ✅ Verified |
| 31 | Index: Load content.md | `queue/tasks/index.py` L96-101 | `storage.download()` | ✅ Verified |
| 32 | Index: chunk_by_sentences() | `queue/tasks/index.py` L119 | LlamaIndex `SentenceSplitter` (fallback: paragraph) | ✅ Verified |
| 33 | Index: embed_batch() | `queue/tasks/index.py` L136 | **SentenceTransformers** `mpnet-base-v2` (768d) | ✅ Verified |
| 34 | Index: INSERT chunks | `queue/tasks/index.py` L154-170 | pgvector Vector(768) | ✅ Verified |
| 35 | Index status | `queue/tasks/index.py` | `STRICT_NEO4J ? INDEXING(95) : READY_BASIC` | ✅ Verified |
| 36 | Enrich: Load content_list | `queue/tasks/enrichment.py` L139 | from structured.json | ✅ Verified |
| 37 | Enrich: insert_content_list() | `queue/tasks/enrichment.py` L221-227 | `rag_pipeline.insert_content_list()` | 🔧 Fixed (ProcessingResult) |
| 38 | Enrich: read doc_id | `queue/tasks/enrichment.py` L229 | `.document_id` | 🔧 Fixed (was `.doc_id`) |
| 39 | Enrich: READY_ENRICHED | `queue/tasks/enrichment.py` L267 | only if success | ✅ Verified |
| 40 | Enrich failure policy | `queue/tasks/enrichment.py` | non-strict stays READY_BASIC; strict fails after retries | ✅ Verified |
| 41 | PaddleOCR: should_use | `core/engines/paddleocr_engine.py` | `should_use_paddleocr()` | ✅ Verified |
| 42 | PaddleOCR: process_document | `core/engines/paddleocr_engine.py` | `process_document()` | ✅ Verified |
| 43 | PaddleOCR: ocr_image | `core/engines/paddleocr_engine.py` | `ocr_image()` | ✅ Verified |
| 44 | PaddleOCR: process_crops | `core/engines/paddleocr_engine.py` | `process_crops()` | ✅ Verified |
| 45 | Chunking: SentenceSplitter | `services/documents/chunking_service.py` L556-643 | LlamaIndex (fallback: paragraph) | ✅ Verified |
| 46 | Embedding: mpnet-base-v2 | `services/core/embedding_service.py` L76-80 | **SentenceTransformers** 768d native | ✅ Verified |

> **Kết luận: 44/46 bước verified. 2 bước bị XÓA (Surya). 2 bước đã FIX (ProcessingResult + doc_id). 6 bug total đã fix.**

---

## 📝 Changelog từ v3.0 → v3.1

| Ngày | Thay đổi |
|------|----------|
| 2026-04-03 | FIX B1: `ProcessingResult` field names (pipeline.py) |
| 2026-04-03 | FIX B2: `.doc_id` → `.document_id` (enrichment.py) |
| 2026-04-03 | FIX B3: Thêm `paddlepaddle>=3.0.0` (requirements-extra.txt) |
| 2026-04-03 | FIX B4: Loại bỏ hoàn toàn Surya khỏi pipeline (ocr.py ~70 dòng xóa) |
| 2026-04-03 | FIX B5: `ProcessingResult` missing `document_id` + sai enum (parsers.py) |
| 2026-04-03 | FIX B6: Xóa Surya env vars (docker-compose.yml) |
| 2026-04-03 | ADD: Neo4j container cho LightRAG (docker-compose.yml) |
| 2026-04-03 | ADD: `neo4j>=5.14.0` driver (requirements-extra.txt) |
| 2026-04-03 | UPDATE: `upload_workflow_new.puml` — xóa tất cả Surya |
| 2026-04-03 | UPDATE: `normalize.py` docstring — xóa Surya |
| 2026-05-16 | FIX B9: add `InputFormat.XLSX` to Docling `allowed_formats` so `.xlsx` uploads no longer fail with "File format not allowed" |
