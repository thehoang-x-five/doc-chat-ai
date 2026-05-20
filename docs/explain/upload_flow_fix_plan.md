# Upload Flow Fix Plan

Date: 2026-04-08

## Implementation Status Update

This plan is no longer purely proposed work. The following items have been implemented in code in the current repository state:

- Workstream 1: PDF routing now classifies scanned vs digital PDFs before choosing PaddleOCR vs Docling
- Workstream 1A: mixed PDFs now stay on Docling for the main parse and use PaddleOCR only for low-text pages / sub-OCR recovery
- Workstream 2: Surya is explicitly marked legacy-only in the active upload path
- Workstream 3: local startup scripts now run `enrichment`
- Workstream 4: strict Neo4j enforcement is implemented; the backend now fails loudly instead of silently falling back when Neo4j is required
- Workstream 5: `KnowledgeBase.tsx` now validates files before upload and uses a ref-backed polling loop
- Workstream 7: delete flow now has an explicit `EmbeddingService.delete_document_vectors()` path
- Workstream 8A: chunking is upgraded from sentence-only input to structure-aware canonical `content_list`
- Workstream 8B: embedding runtime now follows configured provider/model while staying compatible with the current 768-dim pgvector schema
- Hotfix 2026-05-16: `.xlsx` upload failure fixed by adding `InputFormat.XLSX`
  to the Docling `DocumentConverter.allowed_formats` list in
  `server/app/core/engines/ocr.py`. The intended route (`DOCX/PPTX/XLSX ->
  Docling`) was already correct; the converter whitelist was stale.
- Hotfix 2026-05-16: strict Neo4j enrichment failure fixed by resolving
  `ParserFactory.create_parser("auto")` to Docling instead of recursively
  reusing `config.parser="auto"`, and by making `insert_content_list()` stop
  immediately if LightRAG initialization fails.

Operational prerequisite now:

- because `STRICT_NEO4J` is enabled in server settings, the environment must actually provide reachable Neo4j-backed LightRAG storage or enrichment will fail by design
- with `STRICT_NEO4J=true`, index completion intentionally keeps the document at `INDEXING` progress 95 until enrichment succeeds; immediate `READY_BASIC` applies when strict enrichment is disabled

## Goal

Bring the upload flow to a state where these claims are actually true in code and runtime:

1. digital documents follow Docling
2. image files and scanned PDFs follow PaddleOCR
3. sub-OCR follows PaddleOCR
4. chunking uses `LlamaIndex SentenceSplitter`
5. local embedding model is explicitly controlled
6. enrichment really runs through RAG-Anything and Neo4j when enabled
7. `KnowledgeBase.tsx` accurately reflects backend progress and constraints

## Recommended Execution Order

### Phase 0 - Lock the truth first

Priority: P0

Before changing behavior, freeze the intended routing matrix in code comments and tests:

- `txt/md/csv/html/xhtml` -> direct read
- image files -> PaddleOCR
- digital PDF -> Docling
- scanned PDF -> PaddleOCR
- DOCX/PPTX/XLSX -> Docling
- embedded images / inline images -> PaddleOCR sub-OCR

Deliverable:

- one short markdown spec in docs
- one test matrix for fixtures

## Workstream 1 - Fix parser routing for PDFs

Priority: P0

### Problem

Current upload flow does not detect scanned PDFs automatically. `KnowledgeBase.tsx` also cannot send parser preferences.

### Files

- `server/app/queue/tasks/ocr.py`
- `server/app/core/engines/paddleocr_engine.py`
- optionally add `server/app/core/engines/pdf_routing.py`

### Required changes

1. Add a PDF classifier step before route 1 / route 2.
2. Detect whether a PDF has a usable text layer.
3. Route:
   - digital PDF -> Docling
   - scanned PDF -> PaddleOCR
4. Keep `USE_PADDLEOCR_FOR_PDF` only as override, not as primary strategy.
5. Record the routing reason in metadata, for example:
   - `routing_decision = digital_pdf_docling`
   - `routing_decision = scanned_pdf_paddleocr`

### Suggested implementation

Add a helper such as:

- `detect_pdf_content_type(file_path) -> {"digital" | "scanned" | "mixed" | "unknown"}`

Candidate techniques:

- quick text-layer probe with `pypdf` or `pdfminer.six`
- page-level fallback: if extracted text is below threshold and page images are dominant, treat as scanned

### Acceptance criteria

- a digital PDF always ends with `parser_used` beginning with `docling`
- a scanned PDF always ends with `parser_used` beginning with `paddleocr`
- a mixed PDF has a documented policy and matching metadata

## Workstream 2 - Keep Surya code but fully disable it in the active path

Priority: P0

### Problem

Surya is legacy-only in runtime, but still part of default dependencies.

### Files

- `server/requirements.txt`
- optionally add `server/requirements-legacy.txt`
- `server/app/core/engines/surya_engine.py`

### Required changes

1. Keep `surya_engine.py` in the repo if you want historical reference.
2. Remove `surya-ocr` from default installation path.
3. Move Surya dependencies to a legacy extra file or comment them as unsupported legacy code.
4. Add a docstring at the top of `surya_engine.py`:
   - `LEGACY ONLY - not used by upload flow`

### Acceptance criteria

- no active upload code imports Surya
- default environment installs only the real active OCR stack

## Workstream 3 - Make local runtime match Docker runtime

Priority: P0

### Problem

Docker runs `enrichment`, but local `.bat` scripts do not.

### Files

- `server/start_all.bat`
- `server/start_celery.bat`
- optionally add `server/start_full_pipeline.bat`

### Required changes

1. Add `enrichment` queue to local startup scripts.
2. If machine resources are limited, create 2 startup options:
   - minimal: `ocr,index,convert,default`
   - full: `ocr,index,convert,default,enrichment`
3. Document clearly which mode is required for graph enrichment demos.

### Acceptance criteria

- local upload can reach `READY_ENRICHED`
- local graph enrichment no longer depends on Docker-only behavior

## Workstream 4 - Guarantee and observe Neo4j usage

Priority: P0

### Problem

The factory can silently fall back from Neo4j, and logs can still look too positive.

### Files

- `server/app/services/core/rag/factory.py`
- `server/app/queue/tasks/enrichment.py`
- optionally `server/app/api/v1/health.py`

### Required changes

1. Detect the actual graph storage backend after `LightRAG` initialization.
2. Log the real backend:
   - `Neo4JStorage`
   - fallback backend
   - disabled
3. If `ENABLE_RAGANYTHING_PARSING=true` and Neo4j is expected but unavailable, choose one policy:
   - strict mode: fail enrichment loudly
   - soft mode: continue, but mark `graph_backend=fallback` in metadata
4. Store backend info in `structured.json` or job metadata.

### Acceptance criteria

- a reviewer can prove from logs or metadata whether Neo4j was truly used
- the system no longer gives ambiguous "KG: Neo4j" messaging

## Workstream 5 - Unify upload validation across frontend and backend

Priority: P1

### Problem

Upload size/type rules are duplicated and inconsistent.

### Files

- `frontend/src/routes/KnowledgeBase.tsx`
- `frontend/src/components/common/DocumentViewer.tsx`
- `frontend/src/utils/file.ts`
- `frontend/src/types.ts`
- `server/app/utils/validation.py`
- `server/app/core/config.py`

### Required changes

1. Create one shared frontend source of truth for:
   - allowed extensions
   - max file size
2. Make `KnowledgeBase.tsx` call `validateFile()` before upload.
3. Update frontend whitelist to match backend exactly.
4. Change backend validation default to `settings.MAX_FILE_SIZE`, not hardcoded 50 MB.
5. Return max-size metadata in upload errors if helpful.

### Acceptance criteria

- the browser rejects unsupported files before request
- frontend and backend show the same max file size
- accepted extensions are identical across UI and API

## Workstream 6 - Fix polling/state handling in `KnowledgeBase.tsx`

Priority: P1

### Problem

Polling depends on `processingDocs.size`, which can keep stale IDs in the interval closure.

### Files

- `frontend/src/routes/KnowledgeBase.tsx`

### Required changes

1. Replace the current interval closure with one of these patterns:
   - dependency on the full `processingDocs`
   - a ref that always stores the latest set
2. Keep `processingDocsInfo` synchronized even when one doc completes and another remains.
3. Preserve progress text from backend:
   - `processingProgress`
   - `processingStep`
4. Optionally separate:
   - upload progress
   - OCR/index/enrichment progress

### Acceptance criteria

- newly added processing docs are always polled
- completed docs disappear from the queue reliably
- no stale polling after set membership changes

## Workstream 7 - Make parser choice explicit in metadata, even if UI stays simple

Priority: P1

### Problem

Current upload flow hides parser strategy from the user and from later debugging.

### Files

- `server/app/queue/tasks/ocr.py`
- `frontend/src/routes/KnowledgeBase.tsx`
- optionally `frontend/src/components/common/DocumentViewer.tsx`

### Required changes

1. Persist these fields in `structured.json`:
   - `routing_decision`
   - `parser_used`
   - `sub_ocr_used`
   - `pdf_classification`
2. Optionally expose parser metadata in document detail endpoint.
3. Optionally show "Processed with Docling/PaddleOCR" in the UI.

### Acceptance criteria

- every uploaded document can be audited without reading worker logs

## Workstream 8 - Fix embedding configuration reality

Priority: P1

### Problem

The config says one model, but runtime may choose another.

### Files

- `server/app/core/config.py`
- `server/app/services/core/embedding_service.py`
- optionally `server/app/queue/tasks/index.py`

### Required changes

1. Decide the real supported policy:
   - explicit `sentence-transformers`
   - explicit `ollama`
   - automatic fallback
2. Make runtime honor:
   - `EMBEDDING_PROVIDER`
   - `EMBEDDING_MODEL`
3. Log actual loaded model on startup and during indexing.
4. Store embedding model metadata for indexed chunks or jobs.

### Acceptance criteria

- a reviewer can state exactly which embedding model indexed a document
- config values are not misleading anymore

## Workstream 8A - Upgrade chunking from sentence-only to structure-aware

Priority: P1

### Problem

Sentence-aware chunking is a good baseline, but the upload flow already has
normalized structure (`content_list`) that is not fully exploited during index.

### Files

- `server/app/queue/tasks/normalize.py`
- `server/app/services/documents/chunking_service.py`
- `server/app/queue/tasks/index.py`

### Required changes

1. Split markdown text into heading-aware text blocks during normalize.
2. Chunk from canonical `content_list`, not only from one large text blob.
3. Keep `SentenceSplitter` inside text blocks.
4. Emit standalone chunks for tables/equations with explicit `chunk_type`.
5. Preserve `section_title` and page metadata when available.

### Acceptance criteria

- text chunks remain sentence-aware
- tables/equations are retrievable as their own chunk types
- section-aware retrieval is better than flat sentence-only chunking

## Workstream 8B - Prepare embedding quality upgrade safely

Priority: P2

### Problem

Higher-quality multilingual embeddings are attractive, but the current pgvector
schema fixes the vector dimension, so a silent model swap is risky.

### Files

- `server/app/core/config.py`
- `server/app/services/core/embedding_service.py`
- `server/app/db/models.py`
- migrations if needed

### Required changes

1. Keep runtime aligned with the configured embedding model first.
2. Only migrate to models like `BAAI/bge-m3` when vector dimension migration is planned.
3. Log both target dimension and native model dimension.
4. Treat "better model" as an explicit migration, not a hidden fallback.

### Acceptance criteria

- embedding quality improvements do not silently corrupt vector compatibility
- model upgrades become auditable and reversible

## Workstream 9 - Decide whether `ChunkEmbedding` is real or dead design

Priority: P2

### Problem

There is a versioned embedding model/table design, but active indexing writes to `Chunk.embedding` only.

### Files

- `server/app/db/models.py`
- `server/app/queue/tasks/index.py`
- migration files if needed

### Options

Option A:

- keep simple design
- remove `ChunkEmbedding` table/model if not needed

Option B:

- fully implement versioned embeddings
- write each embedding to `chunk_embeddings`
- store `embedding_model_id`

### Recommendation

For a thesis project, Option A is cleaner unless you truly need multi-model re-embedding experiments.

### Acceptance criteria

- there is only one clear embedding storage strategy in the codebase

## Workstream 10 - Fix deletion cleanup path

Priority: P1

### Problem

`DocumentService.delete()` calls a method that does not exist in `EmbeddingService`.

### Files

- `server/app/services/documents/document_service.py`
- `server/app/services/core/embedding_service.py`

### Required changes

Choose one:

1. Implement `delete_document_vectors(document_id)` properly
2. Remove the dead call and rely on chunk deletion only
3. If graph cleanup is also needed, clean RAG-Anything/Neo4j artifacts too

### Acceptance criteria

- delete flow no longer depends on swallowed exceptions
- KnowledgeBase delete action leaves no unclear vector-cleanup behavior

## Workstream 11 - Add upload-path integration tests

Priority: P0

### Test fixtures

Create a small fixture set:

- `sample.txt`
- `sample.md`
- `digital.pdf`
- `scanned.pdf`
- `mixed.pdf`
- `image.png`
- `docx_with_inline_images.docx`

### Required test assertions

1. `txt/md/csv/html/xhtml` -> `parser_used=direct`
2. image -> `parser_used=paddleocr`
3. digital PDF -> `parser_used=docling...`
4. scanned PDF -> `parser_used=paddleocr...`
5. DOCX with inline images -> `parser_used=docling+paddleocr`
6. index stage creates chunks
7. enrichment stage records backend info

### Suggested test layers

- unit tests for routing helpers
- integration tests for OCR task
- one end-to-end upload test covering API + worker + storage

## Workstream 12 - Improve observability for thesis demo

Priority: P2

### Files

- `server/app/queue/tasks/ocr.py`
- `server/app/queue/tasks/index.py`
- `server/app/queue/tasks/enrichment.py`
- `frontend/src/routes/KnowledgeBase.tsx`

### Add logs/metadata

- parser route chosen
- why route was chosen
- OCR engine actually used
- chunk count
- embedding model actually used
- graph backend actually used
- enrichment success / skipped / fallback

### Acceptance criteria

- when a document is uploaded, the entire path can be explained from metadata and logs in less than 1 minute

## Suggested Milestone Plan

### Milestone 1

Focus:

- Workstream 1
- Workstream 3
- Workstream 4
- Workstream 11

Outcome:

- parser routing becomes truthful
- local runtime matches Docker
- Neo4j usage becomes provable

### Milestone 2

Focus:

- Workstream 5
- Workstream 6
- Workstream 7

Outcome:

- `KnowledgeBase.tsx` becomes reliable and aligned with backend constraints

### Milestone 3

Focus:

- Workstream 8
- Workstream 9
- Workstream 10
- Workstream 12

Outcome:

- config story, cleanup story, and thesis observability become consistent

## Minimal Fix Set If Time Is Limited

If you only have time for the smallest high-impact fix set, do these first:

1. auto-detect scanned PDFs and route them to PaddleOCR
2. add `enrichment` queue to local startup
3. expose actual graph backend and stop ambiguous Neo4j logs
4. unify frontend/backend file-size and extension validation
5. fix `KnowledgeBase.tsx` polling stale-set issue

## Definition Of Done

The upload flow can be considered "close to 100%" only when all of these are true:

1. scanned PDF routing is deterministic
2. Surya is fully legacy-only, not a default runtime dependency
3. local and Docker both support enrichment
4. Neo4j usage is observable and verifiable
5. frontend and backend validation rules match
6. embedding model is explicitly controlled and logged
7. `KnowledgeBase.tsx` polling and progress are stable
8. integration tests prove the routing matrix
