# Upload Flow Code Reality Analysis

Date: 2026-04-08

## Implementation Update After Audit

The findings below capture the original code reality at audit time.

Implementation status after the fix pass in this repository:

- fixed: scanned PDF routing is now classified in `server/app/queue/tasks/ocr.py` and routed toward PaddleOCR when the PDF is detected as scanned
- fixed: mixed PDFs now follow `Docling + PaddleOCR page/sub-OCR`; low-text PDF pages are recovered with targeted PaddleOCR instead of routing the whole mixed file to Paddle
- fixed: `.xlsx` uploads now work through Docling. On 2026-05-16 the worker log showed `File format not allowed: tmp*.xlsx`; the route was correct, but `DocumentEngine` omitted `InputFormat.XLSX` from the custom Docling `allowed_formats` list.
- fixed: strict Neo4j enrichment no longer fails before storage init because `ParserFactory.create_parser("auto")` now resolves to Docling instead of recursively calling itself when `config.parser` is also `auto`. `insert_content_list()` also fails fast if LightRAG initialization returns an error.
- fixed: local startup scripts now include the `enrichment` queue
- fixed: frontend upload now reuses `validateFile()` and polling no longer depends on a stale closure over `processingDocs`
- fixed: embedding runtime now honors configured provider/model and logs actual runtime settings
- fixed: document delete no longer calls a missing vector cleanup method
- improved: chunking now works from canonical `content_list` with structure-aware handling for text, tables, and equations while still using `LlamaIndex SentenceSplitter` for text blocks
- fixed: strict Neo4j mode is now implemented; the enrichment path raises and the document remains `INDEXING` or becomes `FAILED` instead of silently falling back

Runtime prerequisite after implementation:

- because `STRICT_NEO4J` is now enabled by default in server settings, the environment must actually provide working Neo4j-backed LightRAG storage or enrichment will fail by design
- with `STRICT_NEO4J=true`, INDEX completion keeps the document at `INDEXING` progress 95 until enrichment succeeds; `READY_BASIC` immediately after index only applies to non-strict mode

## Scope

Audit only the upload flow that starts from `frontend/src/routes/KnowledgeBase.tsx` and ends at:

- upload API entrypoints
- object storage / presigned upload
- OCR/parser routing
- normalize / quality gate
- chunking / embedding
- RAG-Anything enrichment
- Neo4j usage

This review is based on real code paths, not on the docs alone.

## Executive Verdict

The upload flow is not "100% correct" yet.

It is already a solid thesis-grade architecture because it combines:

- React upload UI
- presigned upload + storage fallback
- async Celery pipeline
- Docling for digital documents
- PaddleOCR for image OCR and sub-OCR
- sentence-aware chunking
- vector indexing
- optional graph enrichment

But the current code still has several gaps between intended design and actual behavior:

1. Scanned PDF files are not automatically routed to PaddleOCR on the main upload flow.
2. Neo4j is prepared but not guaranteed to be active at runtime.
3. Local startup scripts do not run the `enrichment` queue, so local behavior can stop at `READY_BASIC`.
4. Embedding configuration and actual runtime model selection are inconsistent.
5. Frontend upload/polling in `KnowledgeBase.tsx` is functional but still has correctness gaps.

My practical conclusion:

- For a thesis/demo: the stack is appropriate and defensible.
- For a claim like "flow da chuan 100%": not yet.

## Verified End-to-End Flow

### 1. Frontend entry: `KnowledgeBase.tsx`

Main upload entry:

- `frontend/src/routes/KnowledgeBase.tsx:294-355`
- file input uses `accept={FILE_INPUT_ACCEPT}` at `frontend/src/routes/KnowledgeBase.tsx:987-997`
- `FILE_INPUT_ACCEPT` comes from `frontend/src/components/common/DocumentViewer.tsx:13-21`

Actual frontend behavior:

- accepts `pdf, docx, pptx, xlsx, jpg, jpeg, png, bmp, tif, tiff, webp, gif, txt, md, csv, json, rtf, odt, html, xhtml`
- uploads up to 3 files concurrently
- only filters zero-byte files before upload
- does not call `validateFile()` from `frontend/src/utils/file.ts`
- document preview behavior in `DocumentViewer`:
  - PDF, images, and DOCX use browser/native renderers with authenticated blob fetches
  - TXT/MD/CSV/JSON/RTF/ODT/HTML use raw text or iframe preview where applicable
  - PPTX/XLSX use extracted markdown text from the backend content endpoint; XLSX pipe tables are rendered as HTML tables in the Original tab
- after upload it fire-and-forget calls:
  - `setDocumentCategory()`
  - `categorizeDocument()`

Important note:

- `KnowledgeBase.tsx` does not send parser settings.
- So this page cannot choose `docling` vs `paddleocr` from the UI.

### 2. Frontend API client

Real upload client path:

- `frontend/src/lib/api.ts:580-655`

Behavior:

1. Call `POST /api/v1/workspaces/{workspaceId}/documents/presigned-upload`
2. If backend returns `file://...`, delete placeholder doc and fallback to multipart upload
3. Otherwise `PUT` directly to storage
4. Confirm with `POST /api/v1/documents/{document_id}/presigned-confirm`

This is a good design choice for the thesis because it shows:

- scalable upload path with presigned URL
- local fallback path when MinIO/S3 is unavailable

### 3. Backend upload entrypoint

Endpoints:

- `server/app/api/v1/workspaces.py`
- `server/app/api/v1/documents.py:191-208`

Main service path:

- `server/app/services/documents/document_service.py:60-185`
- presigned flow: `server/app/services/documents/document_service.py:187-264`

Verified behavior:

- validate file type/size
- create `Document`
- upload original file to storage
- compute checksum
- deduplicate inside workspace
- create `DocumentVersion`
- create OCR job
- set document status to `INDEXING`
- enqueue Celery OCR task

Important reality:

- OCR job in the normal upload path is created without `config_json`
- evidence:
  - `server/app/services/documents/document_service.py:165-183`
- therefore the OCR task runs with `config = {}`
- that directly affects parser routing decisions later

### 4. Storage layer

Object store behavior:

- `server/app/storage/object_store.py`

Observed architecture:

- uses MinIO when available
- falls back to local filesystem when MinIO is absent
- presigned upload/download can return `file://...` in local mode

This matches the frontend fallback logic, so storage flow is coherent.

### 5. OCR / parser routing

Real routing is in:

- `server/app/queue/tasks/ocr.py:157-567`

This is the real upload router. The deeper RAG-Anything parser stack is not the main upload decision point.

#### Actual routing matrix

1. Plain text files

- `txt, md, csv, html, xhtml`
- route 0 direct read
- evidence: `server/app/queue/tasks/ocr.py:157-176`
- parser result: `parser_used = "direct"`

2. Images

- `jpg, jpeg, png, webp, tiff, tif, bmp`
- route to `PaddleOCREngine`
- evidence:
  - `server/app/core/engines/paddleocr_engine.py:29-73`
  - `server/app/queue/tasks/ocr.py:177-229`
- parser result: `parser_used = "paddleocr"`

3. PDF files

- not automatically classified as scanned vs digital
- default behavior:
  - PDF goes to Paddle only if `USE_PADDLEOCR_FOR_PDF=true`
  - or if parser is explicitly set to `paddleocr`
- evidence:
  - `server/app/core/engines/paddleocr_engine.py:35-73`

Because `KnowledgeBase.tsx` upload does not send parser settings and `DocumentService.upload()` stores no OCR config, the normal upload flow means:

- image -> PaddleOCR
- PDF -> Docling by default
- scanned PDF is not guaranteed to use PaddleOCR

This is the biggest mismatch against the intended design.

4. Digital PDF / DOCX / PPTX / XLSX and other non-direct-text files

- route to Docling when route 0 and route 1 do not trigger
- evidence: `server/app/queue/tasks/ocr.py:231-567`
- parser result starts as `parser_used = "docling"`
- runtime note: `.xlsx` requires `InputFormat.XLSX` in `DocumentEngine`'s
  `DocumentConverter.allowed_formats`; this was fixed after the 2026-05-16
  upload failure.

5. Embedded image sub-OCR

- after Docling parsing, embedded images are sent to PaddleOCR if available
- evidence:
  - PDF/image crop sub-OCR: `server/app/queue/tasks/ocr.py:274-409`
  - DOCX inline image OCR: `server/app/queue/tasks/ocr.py:411-539`

Result:

- `docling+paddleocr` is real and correctly implemented for sub-OCR

### 6. Docling behavior

Docling engine:

- `server/app/core/engines/ocr.py:45-130`

Important configuration:

- `do_ocr = True`
- `do_table_structure = True`
- `generate_page_images = True`
- `generate_picture_images = True`
- `ocr_options = OcrAutoOptions()`

Meaning:

- even when a PDF is routed to Docling, OCR still happens inside Docling
- so the system is not "broken" for scanned PDFs
- but it is not using PaddleOCR on scanned PDFs by default

### 7. PaddleOCR behavior

Paddle engine:

- `server/app/core/engines/paddleocr_engine.py:76-275`

Verified:

- full-page image OCR is real
- PPStructureV3 is used
- sub-OCR helpers `ocr_image()` and `process_crops()` are used by the upload pipeline

So the statement "sub-OCR da di vao Paddle" is true.

The statement "pdf scan da di vao Paddle" is only partially true.

## Surya Status

### Real status

Surya is legacy code, present in the repo, but not used in the upload flow I audited.

Evidence:

- active upload OCR router imports PaddleOCR and Docling, not Surya:
  - `server/app/queue/tasks/ocr.py:177-239`
- Surya code still exists:
  - `server/app/core/engines/surya_engine.py`
- Surya dependency still exists:
  - `server/requirements.txt:13-16`

Conclusion:

- "giu code Surya nhung khong dung" is true at runtime for upload flow
- but the installation footprint is not clean because `surya-ocr` is still a default dependency

## Normalize and Quality Gate

Normalization is real:

- `server/app/queue/tasks/normalize.py`
- called from `server/app/queue/tasks/ocr.py:569-607`

Verified outcomes:

- canonical `content_list` is created
- `structured.json` stores:
  - `parser_used`
  - `content_list`
  - detected language
  - normalize stats

This is a strong design choice because it standardizes later enrichment.

## Chunking

Chunking is correctly wired to `LlamaIndex SentenceSplitter` when the dependency is installed.

Evidence:

- index task uses `chunk_by_sentences()`:
  - `server/app/queue/tasks/index.py:96-121`
- implementation:
  - `server/app/services/documents/chunking_service.py:560-643`

Reality:

- yes, the main path uses `SentenceSplitter`
- if `llama-index-core` is missing, it silently falls back to paragraph chunking

Conclusion:

- "chunk(LlamaIndex SentenceSplitter)" is true, but conditional on dependency availability

### Recommended chunking upgrade

The better thesis-grade target is not "replace SentenceSplitter", but:

- keep `SentenceSplitter` for long text sections
- chunk from canonical `content_list`
- preserve `section_title`
- emit standalone chunks for tables and equations

That is better than sentence-only chunking because upload OCR already normalizes
document structure before indexing.

## Embedding

### What the config says

- `server/app/core/config.py:157-165`
- default:
  - `EMBEDDING_MODEL = paraphrase-multilingual-MiniLM-L12-v2`
  - `EMBEDDING_PROVIDER = sentence-transformers`

### What the runtime actually does

Embedding runtime:

- `server/app/services/core/embedding_service.py:59-109`
- `server/app/services/core/embedding_service.py:221-279`

Verified behavior:

- service starts from `settings.OLLAMA_EMBED_MODEL`
- then if `sentence_transformers` is installed, it switches to:
  - `paraphrase-multilingual-mpnet-base-v2`
- dimension is normalized to 768
- if sentence-transformers is unavailable, it falls back to Ollama embeddings

Conclusion:

- local embedding exists and is usable
- but it is not aligned with config naming/documentation
- current runtime choice is:
  - `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` if available
  - otherwise Ollama `nomic-embed-text`

So the answer to "Local embedding model da dung chua?" is:

- architecturally yes
- configuration consistency no

### Recommended embedding upgrade

The better target is:

- make runtime honor `EMBEDDING_PROVIDER` and `EMBEDDING_MODEL`
- log the real provider/model used during indexing
- keep current pgvector-compatible dimension unless you are ready to migrate the schema
- optionally evaluate `BAAI/bge-m3` later as a controlled migration, not an implicit swap

## Index Storage Reality

Index task:

- `server/app/queue/tasks/index.py:125-161`

Observed behavior:

- chunks are stored in `chunks`
- embeddings are written to `Chunk.embedding` if pgvector is available

Important gap:

- `ChunkEmbedding` table exists in `server/app/db/models.py`
- but I did not find any active write path to `chunk_embeddings`
- search path only writes `Chunk.embedding`

This is not fatal for the upload flow, but it shows the embedding versioning design is incomplete.

## RAG-Anything and Neo4j

### What the upload flow really does

OCR task queues enrichment here:

- `server/app/queue/tasks/ocr.py:702-759`

Enrichment task:

- `server/app/queue/tasks/enrichment.py:40-287`

RAG-Anything insert path:

- `server/app/services/rag_patterns/pipeline/pipeline.py:1480-1560`

Verified behavior:

1. load canonical `content_list` from `structured.json`
2. initialize RAGAnything
3. call `insert_content_list(content_list=..., file_path=...)`
4. if successful, mark document `READY_ENRICHED`

This part is real.

### Does it really use Neo4j?

Factory:

- `server/app/services/core/rag/factory.py:39-104`

What the code does:

- tries to import `lightrag.kg.neo4j_impl.Neo4JStorage`
- if import succeeds, passes `graph_storage="Neo4JStorage"`
- if import fails, silently falls back to default graph storage

Important issue:

- log line uses:
  - `kg_status = "Neo4j" if lightrag_instance else "disabled"`
- evidence: `server/app/services/core/rag/factory.py:101-103`

This is misleading because:

- `lightrag_instance` can exist even when actual storage is not Neo4j

Conclusion:

- code is prepared to use Neo4j
- Docker setup includes Neo4j
- but runtime cannot be claimed as "100% sure using Neo4j" from code alone

### Docker vs local mismatch

Docker:

- `docker-compose.yml:252-293`
- has dedicated `celery-worker-enrichment`
- depends on Neo4j

Local startup scripts:

- `server/start_all.bat:8`
- `server/start_celery.bat:5`
- only run queues `ocr,index,convert,default`
- do not run `enrichment`

Real consequence:

- local upload flow can finish at `READY_BASIC`
- local graph enrichment may never execute
- docs can therefore look correct while local runtime is not equivalent

## KnowledgeBase.tsx Audit

### What is good

- supports presigned upload and local fallback indirectly through `apiClient.uploadDocument()`
- tracks processing documents and progress
- shows OCR content through `DocumentViewer`
- displays `READY_BASIC` and `READY_ENRICHED` separately:
  - `frontend/src/routes/KnowledgeBase.tsx:577-604`

### Problems found

#### 1. No real frontend validation before upload

Evidence:

- upload flow only filters zero-byte files:
  - `frontend/src/routes/KnowledgeBase.tsx:297-305`
- `validateFile()` exists but is unused:
  - `frontend/src/utils/file.ts:14-23`

Impact:

- size/type validation is left to backend
- user feedback is later and less precise

#### 2. Frontend validation sources are inconsistent

Evidence:

- actual upload accept list:
  - `frontend/src/components/common/DocumentViewer.tsx:13-21`
- old whitelist still exists:
  - `frontend/src/types.ts`
  - `frontend/src/utils/file.ts:1-23`

Impact:

- if `validateFile()` is reused later, it will reject formats that the upload input currently accepts

#### 3. Polling effect has stale-set risk

Evidence:

- effect depends on `[processingDocs.size, loadData]`
- but loops over captured `processingDocs`
- `frontend/src/routes/KnowledgeBase.tsx:195-235`

Impact:

- if the set contents change while the size does not change, the interval can keep polling stale document IDs

#### 4. Upload page cannot influence parser routing

Evidence:

- `KnowledgeBase.tsx` upload path sends only file/tags
- `frontend/src/lib/api.ts:580-655`
- backend OCR job is created without parser config
- `server/app/services/documents/document_service.py:165-183`

Impact:

- no UI-level control for:
  - force PaddleOCR
  - force Docling
  - scanned PDF strategy

#### 5. The "95% stuck" comment is a symptom, not the real root cause

Evidence:

- frontend comment:
  - `frontend/src/routes/KnowledgeBase.tsx:337-340`
- backend OCR explicitly sets progress to 95 before downstream jobs:
  - `server/app/queue/tasks/ocr.py:718-720`

Impact:

- if index/enrichment workers are slow or missing, UI naturally appears stuck near 95%
- fire-and-forget categorization reduces extra waiting, but it does not solve missing worker/config issues

## File Size Validation Mismatch

Backend validation utility:

- `server/app/utils/validation.py:49-50`
- default max size is 50 MB

Configured app setting:

- `server/app/core/config.py:292-300`
- `MAX_FILE_SIZE = 15 MB`

Real upload path:

- `DocumentService.upload()` calls `validate_file(file.filename, file_size)` without passing `settings.MAX_FILE_SIZE`
- evidence:
  - `server/app/services/documents/document_service.py:87-90`
  - `server/app/utils/validation.py:168-194`

Conclusion:

- actual upload validation is effectively 50 MB
- docs/frontend config say 15 MB
- this is incorrect and should be fixed

## Deletion Path Gap

`DocumentService.delete()` calls:

- `EmbeddingService.delete_document_vectors(str(document_id))`
- evidence: `server/app/services/documents/document_service.py:497-504`

I did not find any implementation of `delete_document_vectors()` in `EmbeddingService`.

Search result:

- only call site found in `document_service.py`

Impact:

- delete path currently relies on swallowed exception logging
- vectors may be left behind if cleanup is expected through that method

This is adjacent to the KnowledgeBase page because the delete button uses this backend path.

## Direct Answers To The User Questions

### 1. Upload flow da chuan 100% chua?

No.

Main blockers:

- scanned PDF routing to PaddleOCR is not guaranteed
- Neo4j usage is not guaranteed
- local start scripts skip enrichment queue
- embedding config and runtime are inconsistent
- frontend upload guard/polling are not fully robust

### 2. Surya da duoc giu code nhung khong dung chua?

Yes for the upload flow runtime.

But:

- Surya code still exists
- Surya dependencies are still installed by default

So runtime intent is correct, dependency cleanup is not finished.

### 3. Text vao Docling dung chua?

Not for plain text files.

Actual behavior:

- `txt/md/csv/html/xhtml` -> direct read
- `pdf/docx/pptx/xlsx/...` -> Docling unless Paddle route wins

This is acceptable and even better for plain text files.

### 4. Anh + PDF scan + sub-OCR da vao Paddle chua?

Partially.

- image files: yes
- sub-OCR for embedded images / DOCX images: yes
- scanned PDFs on the main upload flow: not reliably yes

### 5. RAG-Anything da dung Neo4j chua?

Prepared, but not guaranteed.

- Docker path: likely yes if dependencies are present
- local startup path: often no enrichment worker at all
- factory can silently fall back from Neo4j

### 6. Embedding local model va chunking da dung chua?

Chunking:

- yes, `SentenceSplitter` is correctly wired when dependency is installed

Embedding:

- usable, but not consistently configured
- actual runtime model selection does not match the config story

## Assessment For Thesis

## Why this stack is suitable

This upload architecture is suitable for a thesis because it demonstrates:

- multi-format ingestion
- hybrid OCR strategy
- asynchronous pipeline design
- vector indexing and graph enrichment
- storage abstraction
- UI-level progress tracking

It is stronger than a simple "upload PDF and split text" project.

## What must be stated honestly in the thesis right now

If you present the system today, do not claim these points as absolute:

- "scanned PDF always goes to PaddleOCR"
- "Neo4j is always used in enrichment"
- "embedding model is controlled cleanly by config"
- "local runtime and Docker runtime are identical"

## Recommended Thesis Positioning

The most accurate thesis claim today is:

"He thong su dung Docling cho tai lieu so, PaddleOCR cho anh va sub-OCR, chunking theo cau bang LlamaIndex SentenceSplitter, vector indexing tren pgvector, va co kha nang mo rong sang Graph RAG voi RAG-Anything + Neo4j, tuy nhien phan tuyen PDF scan va bao dam runtime Neo4j can duoc chuan hoa them."

## Priority Findings Summary

### P1

- Scanned PDF routing to PaddleOCR is not guaranteed on the real upload flow.
- Local startup scripts do not run the `enrichment` queue.
- Neo4j usage can silently fall back while logs remain overly optimistic.

### P2

- File size validation is effectively 50 MB while config/frontend say 15 MB.
- Embedding runtime model does not match config expectations.
- `KnowledgeBase.tsx` upload does not validate type/size before request.
- `KnowledgeBase.tsx` polling effect can use stale `processingDocs`.
- delete flow references a missing `delete_document_vectors()` method.

### P3

- Surya is still installed even though upload flow no longer uses it.
- `ChunkEmbedding` versioned design is present but not actively used.
- frontend upload whitelists are duplicated and inconsistent.

## Final Audit Status

Current upload flow status:

- usable: yes
- technically interesting for thesis: yes
- aligned with current docs at 100%: no
- ready to claim strict parser-routing correctness: no
- fixable without redesign: yes
