# Phân tích Chat Flow — server/app/services

> Phân loại toàn bộ 116 file `.py` (không tính `__init__.py`) trong `server/app/services/` theo vai trò: **Chat Flow**, **Chức năng khác**, **Chưa tích hợp**.

**Quy ước**: Memori, RAG, AI Providers, OCR, Embedding đều thuộc **Chat Flow** (gọi trực tiếp hoặc gián tiếp từ `chat_pipeline.py`).

> [!NOTE]
> Cập nhật lần cuối: 2026-02-24. Đã tích hợp 6+3+12+5 service vào pipeline: Phase 1-3 (21 services), Phase 4 (function_registry, reranker, prompt_builder, augmentation_pipeline).

---

## 📁 conversation/ — 10 files

| File | Phân loại | Vai trò trong Chat Flow |
|---|---|---|
| `chat_pipeline.py` | ✅ Chat Flow | **Orchestrator chính** (`ChatPipeline`) — điều phối toàn bộ pipeline ①-⑨ (23 bước, bao gồm ④b Registry, ⑤d Multi-RAG, ⑥a/⑥b Prompt+Rerank, ⑧c Augmentation) |
| `intent_detector.py` | ✅ Chat Flow | ③ Hybrid intent routing (SemanticRouter + Groq/Ollama) |
| `semantic_router.py` | ✅ Chat Flow | ③.1 Layer 1 embedding similarity routing |
| `conversation_service.py` | ✅ Chat Flow | `ConversationService` — CRUD conversations, messages, citations, auto-title |
| `memory_service.py` | ✅ Chat Flow | ⑤ Short-term memory (10 messages gần nhất) + long-term summary |
| `memory_cache.py` | ✅ Chat Flow | ⑤ Cache memory + memori context trong Redis |
| `parallel_executor.py` | ✅ Chat Flow | ⑤ Chạy 3 memory retrievers song song (memory + memori + graph) |
| `dedup_cache.py` | ✅ Chat Flow | ① Ngăn duplicate query trong 5s (Redis) |
| `intent_cache.py` | ✅ Chat Flow | ③ Cache kết quả intent detection (Redis) |

> **Kết luận: 10/10 tích hợp, 0 chưa tích hợp** ✅

---

## 📁 quality/ — 12 files

| File | Phân loại | Vai trò |
|---|---|---|
| `guardrails_service.py` | ✅ Chat Flow | ② Input guardrails (jailbreak/PII/injection) + ⑥ Mid-stream quality |
| `safety_checker.py` | ✅ Chat Flow | ②b PII redaction → `[REDACTED]` |
| `hallucination_checker.py` | ✅ Chat Flow | ⑦ Post-stream hallucination scoring (0-1) |
| `grounding_verifier_service.py` | ✅ Chat Flow | ⑦ Post-stream grounding verification |
| `confidence_scorer.py` | ✅ Chat Flow | ⑦c Composite confidence score từ hallucination+grounding+fact_check |
| `fact_checker.py` | ✅ Chat Flow | ⑦b Verify numerical claims (song song với hallucination check) |
| `result_validator.py` | ✅ Chat Flow | ⑦e Consolidated validation pipeline (retrieval+hallucination+relevance+groundedness) |
| `policy_service.py` | ✅ Chat Flow | ⑦d STRICT/BALANCED/OPEN answer policy + dynamic thresholds |
| `feedback_collector.py` | 🔵 Chức năng khác | Thu thập user feedback (API riêng, không thuộc chat pipeline) |
| `deepeval_tester.py` | 🔵 Chức năng khác | DeepEval offline testing tool |
| `evaluation_service.py` | 🔵 Chức năng khác | RAG evaluation metrics (offline) |
| `ragas_evaluator.py` | 🔵 Chức năng khác | RAGAS benchmark (offline) |

> **8/12 tích hợp, 0 chưa tích hợp, 4 chức năng khác**

---

## 📁 core/ — 12 files (gồm rag/)

| File | Phân loại | Vai trò |
|---|---|---|
| `embedding_service.py` | ✅ Chat Flow | ③ Embedding model (paraphrase-multilingual-MiniLM-L12-v2) |
| `retriever_service.py` | ✅ Chat Flow | ⑥ Retrieval interface cho hybrid.py |
| `rag/service.py` | ✅ Chat Flow | ⑥ **RAGService** — entry point cho RAG operations |
| `rag/factory.py` | ✅ Chat Flow | ⑥ Tạo RAG patterns (hybrid, pipeline) |
| `rag/wrappers.py` | ✅ Chat Flow | ⑥ LLM + Retriever + Embedding wrappers |
| `rag/types.py` | ✅ Chat Flow | ⑥ RAGResponse, config types |
| `rag/utils.py` | ✅ Chat Flow | ⑥ Utility functions cho RAG |
| `base_service.py` | ❌ **Chưa tích hợp** | Abstract base class — không ai kế thừa trong chat flow |
| `context_budget.py` | ✅ Chat Flow | ⑤b Token budget management — trim memory/history trước RAG |
| `latency_budget_service.py` | ✅ Chat Flow | ⑤c SLA timing allocation + ⑨ post-check budget |
| `reranker_service.py` | ✅ Chat Flow | ⑥b Cross-encoder citation reranking (top-20→top-5, graceful без sentence-transformers) |
| `service_registry.py` | ⚠️ **Bỏ qua** | DI framework disabled (circular imports, dòng 224) — cần refactor BaseService |

> **10/12 tích hợp, 1 chưa tích hợp, 1 bỏ qua**

---

## 📁 infrastructure/ — 16 files (gồm ai_providers/)

| File | Phân loại | Vai trò |
|---|---|---|
| `redis_manager.py` | ✅ Chat Flow | ①⑤ Redis connection pool (dedup, memory cache, intent cache) |
| `ai_providers/manager.py` | ✅ Chat Flow | ⑥ AIProviderManager — quản lý tất cả providers với fallback |
| `ai_providers/base_provider.py` | ✅ Chat Flow | ⑥ Abstract base class cho providers (import bởi manager) |
| `ai_providers/config_loader.py` | ✅ Chat Flow | ⑥ Load AI provider config (import bởi manager) |
| `ai_providers/groq.py` | ✅ Chat Flow | ③⑥ Groq provider (intent Layer 2 + RAG generation) |
| `ai_providers/ollama.py` | ✅ Chat Flow | ③⑥ Ollama provider (intent Layer 2 + RAG fallback) |
| `ai_providers/deepseek.py` | ✅ Chat Flow | ⑥ DeepSeek provider (import bởi manager, RAG generation) |
| `ai_providers/gemini.py` | ✅ Chat Flow | ⑥ Gemini provider (import bởi manager, RAG generation) |
| `ai_providers/cloudcode.py` | ✅ Chat Flow | ⑥ CloudCode provider (import bởi manager) |
| `ai_providers/cloudcode_provider_service.py` | ✅ Chat Flow | ⑥ CloudCode extended service |
| `retry_handler.py` | ✅ Chat Flow | ⑤ Retry logic — bọc memory recall với exponential backoff (2 retries) |
| `config_loader.py` | 🔵 Chức năng khác | Global config loader (startup, không phải chat-specific) |
| `health_monitor.py` | 🔵 Chức năng khác | Health check endpoint |
| `logging_service.py` | 🔵 Chức năng khác | Logging configuration |
| `phoenix_tracer.py` | 🔵 Chức năng khác | Phoenix/OpenTelemetry tracing |
| `trace_collector.py` | 🔵 Chức năng khác | Trace collection và export |

> **11/16 tích hợp, 0 chưa tích hợp, 5 chức năng khác**

---

## 📁 memori/ — 14 files

| File | Phân loại | Vai trò |
|---|---|---|
| `auto_cognify_service.py` | ✅ Chat Flow | ⑧ Background: extract facts từ Q&A pair |
| `manager_service.py` | ✅ Chat Flow | ⑤⑧ **MemoriManager** — gọi bởi parallel_executor + auto_cognify |
| `recall_service.py` | ✅ Chat Flow | ⑤ Recall facts theo query (gọi bởi MemoriManager) |
| `graph_search_service.py` | ✅ Chat Flow | ⑤ Graph search (gọi trực tiếp bởi parallel_executor) |
| `models.py` | ✅ Chat Flow | Data models cho memori (dùng bởi manager/recall) |
| `extraction.py` | ✅ Chat Flow | Fact extraction (dùng bởi auto_cognify → manager) |
| `entity_resolver_service.py` | ✅ Chat Flow | Entity resolution (dùng bởi manager khi add_facts) |
| `triple_validator_service.py` | ✅ Chat Flow | Validate semantic triples (dùng bởi manager) |
| `search.py` | ✅ Chat Flow | Search utilities (dùng bởi recall_service) |
| `memify_service.py` | ✅ Chat Flow | ⑧b Background knowledge graph enrichment (infer relationships) |
| `augmentation_service.py` | ✅ Chat Flow | ⑧c Augmentation infrastructure (DbWriterRuntime, AugmentationManager, batch writes) |
| `augmentation_processors_service.py` | ✅ Chat Flow | ⑧c AugmentationPipeline — 3 processors song song (Fact+Preference+Attribute) |
| `temporal_operations.py` | ⚠️ **Bỏ qua** | Memori internal — cần rag_service LLM calls + SemanticTriple |
| `analytics_service.py` | 🔵 Chức năng khác | Memori analytics (API riêng) |

> **12/14 tích hợp, 0 chưa tích hợp, 1 chức năng khác, 1 bỏ qua**

---

## 📁 rag_patterns/ — 28 files

| File | Phân loại | Vai trò |
|---|---|---|
| `patterns/hybrid.py` | ✅ Chat Flow | ⑥ **HybridRAGService** — Graph+Vector+BM25 retrieval → LLM |
| `pipeline/pipeline.py` | ✅ Chat Flow | ⑥ RAGPipeline (import bởi factory.py → RAGAnything) |
| `pipeline/config.py` | ✅ Chat Flow | ⑥ RAGConfig (import bởi factory.py) |
| `pipeline/processors.py` | ✅ Chat Flow | ⑥ Document processors (dùng bởi pipeline) |
| `pipeline/parsers.py` | ✅ Chat Flow | ⑥ Document parsers (dùng bởi pipeline) |
| `pipeline/prompts.py` | ✅ Chat Flow | ⑥ Prompt templates (dùng bởi pipeline) |
| `pipeline/types.py` | ✅ Chat Flow | ⑥ Type definitions (dùng bởi pipeline) |
| `pipeline/utils.py` | ✅ Chat Flow | ⑥ Utilities (dùng bởi pipeline) |
| `pipeline/batch.py` | 🔵 Chức năng khác | Batch processing (document ingestion, không phải chat) |
| `monitoring.py` | ✅ Chat Flow | ⑨ Pattern performance metrics — record_query sau mỗi RAG call |
| `orchestration/analyzer.py` | ✅ Chat Flow | ⑤d QueryAnalyzer — phân tích complexity/domain/intent cho Multi-RAG |
| `orchestration/orchestrator.py` | ✅ Chat Flow | ⑤d PatternOrchestrator — điều phối chạy nhiều pattern (sequential/parallel) |
| `orchestration/planner.py` | 🔵 Chức năng khác | Execution planner (dùng nội bộ bởi orchestrator nếu cần) |
| `orchestration/router.py` | ✅ Chat Flow | ⑤d SmartRouter — chọn pattern tối ưu dựa trên query analysis |
| `orchestration/registry.py` | ✅ Chat Flow | ⑤d PatternRegistry — đăng ký 12 pattern + metadata (dùng bởi orchestrator) |
| `orchestration/combinations.py` | ✅ Chat Flow | ⑤d ALL_COMBINATIONS — 5 tổ hợp Multi-RAG (High-Accuracy, Cost-Optimized...) |
| `patterns/accuracy/corrective.py` | ✅ Chat Flow | ⑤d CorrectiveRAGService — validate + correct retrieved docs |
| `patterns/accuracy/self_rag.py` | ✅ Chat Flow | ⑤d SelfRAGService — iterative self-refinement + hallucination detection |
| `patterns/accuracy/models.py` | ✅ Chat Flow | ⑤d Data models cho accuracy patterns (dùng bởi corrective/self_rag) |
| `patterns/optimization/adaptive.py` | ✅ Chat Flow | ⑤d AdaptiveRAGService — intelligent routing dựa trên LLM confidence |
| `patterns/optimization/corag.py` | ✅ Chat Flow | ⑤d CORAGService — cost-constrained optimization (MCTS chunk selection) |
| `patterns/optimization/semantic.py` | ✅ Chat Flow | ⑤d SemanticHighlightRAGService — token optimization |
| `patterns/optimization/speculative.py` | ✅ Chat Flow | ⑤d SpeculativeRAGService — parallel draft generation + verification |
| `patterns/optimization/models.py` | ✅ Chat Flow | ⑤d Data models cho optimization patterns |
| `patterns/specialized/code_rag.py` | ✅ Chat Flow | ⑤d CodeRAGService — code-aware retrieval + generation |
| `patterns/specialized/coral.py` | ✅ Chat Flow | ⑤d CORALService — conversational multi-turn context tracking |
| `patterns/specialized/reveal.py` | ✅ Chat Flow | ⑤d REVEALService — visual-language multimodal RAG |
| `patterns/specialized/models.py` | ✅ Chat Flow | ⑤d Data models cho specialized patterns |

> **21/28 tích hợp, 0 chưa tích hợp, 7 chức năng khác**

---

## 📁 tools/ — 3 files

| File | Phân loại | Vai trò |
|---|---|---|
| `function_calling_service.py` | ✅ Chat Flow | ④ Function calling cho metadata queries (đếm/list docs) |
| `tools_service_v2.py` | ✅ Chat Flow | ④ V2 Pydantic tools — **import trực tiếp** bởi function_calling_service |
| `function_registry.py` | ✅ Chat Flow | ④b Extended tool registry — 5 built-in tools (search, calculate, time, format, get_doc) + multi-provider schemas |

> **3/3 tích hợp** ✅

---

## 📁 generation/ — 5 files

| File | Phân loại | Vai trò |
|---|---|---|
| `image_generation_service.py` | ✅ Chat Flow | ④b Tạo ảnh khi intent = IMAGE_GENERATION |
| `prompt_builder.py` | ✅ Chat Flow | ⑥a Standardized RAG prompt (vi/en, memory context, citations formatting) |
| `response_formatter.py` | 🔵 Chức năng khác | Format OCR/compare/extract/summarize (chức năng khác, không phải chat) |
| `compare_service.py` | 🔵 Chức năng khác | So sánh document (API riêng) |
| `summarize_service.py` | 🔵 Chức năng khác | Tóm tắt document (API riêng) |

> **2/5 tích hợp, 0 chưa tích hợp, 3 chức năng khác**

---

## 📁 analytics/ — 5 files

| File | Phân loại | Vai trò |
|---|---|---|
| `analytics_service.py` | 🔵 Chức năng khác | Analytics dashboard |
| `job_service.py` | 🔵 Chức năng khác | Job scheduling |
| `learning_pipeline_service.py` | 🔵 Chức năng khác | Learning pipeline |
| `metrics_collector_service.py` | 🔵 Chức năng khác | Metrics collection |
| `workspace_service.py` | 🔵 Chức năng khác | Workspace analytics |

> **0/5 tích hợp, 0 chưa tích hợp, 5 chức năng khác**

---

## 📁 auth/ — 3 files

| File | Phân loại | Vai trò |
|---|---|---|
| `api_key_service.py` | 🔵 Chức năng khác | API key management |
| `auth_service.py` | 🔵 Chức năng khác | Authentication/Authorization |
| `oauth_callback_server.py` | 🔵 Chức năng khác | OAuth callback server |

> **0/3 tích hợp, 0 chưa tích hợp, 3 chức năng khác**

---

## 📁 documents/ — 4 files

| File | Phân loại | Vai trò |
|---|---|---|
| `document_service.py` | 🔵 Chức năng khác | CRUD documents |
| `chunking_service.py` | 🔵 Chức năng khác | Document chunking |
| `extraction_service.py` | 🔵 Chức năng khác | Content extraction / OCR |
| `category_service.py` | 🔵 Chức năng khác | Document categories |

> **0/4 tích hợp, 0 chưa tích hợp, 4 chức năng khác**

---

## 📁 search/ — 5 files

| File | Phân loại | Vai trò |
|---|---|---|
| `hybrid_retriever_service.py` | 🔵 Chức năng khác | Search API (không qua chat) |
| `query_rewriter_service.py` | 🔵 Chức năng khác | Query rewriting (search API) |
| `rag_cache_service.py` | 🔵 Chức năng khác | RAG cache (search API) |
| `search_cache_service.py` | 🔵 Chức năng khác | Search cache |
| `timeline_service.py` | 🔵 Chức năng khác | Timeline view |

> **0/5 tích hợp, 0 chưa tích hợp, 5 chức năng khác**

---

## Tổng kết

| Phân loại | Số lượng | Tỷ lệ |
|---|---|---|
| ✅ **Chat Flow** (đang tích hợp) | **76** | 66% |
| ❌ **Chưa tích hợp** (code có nhưng chưa gọi) | **1** | 1% |
| ⚠️ **Bỏ qua** (có lý do cụ thể) | **3** | 3% |
| 🔵 **Chức năng khác** (API riêng, offline tools) | **36** | 31% |
| **Tổng** | **116** | 100% |

---

## Đã tích hợp mới (2026-02-23)

| # | File | Bước | Mô tả |
|---|---|---|---|
| 1 | `core/context_budget.py` | ⑤b | Trim memory/history tokens trước RAG |
| 2 | `core/latency_budget_service.py` | ⑤c/⑨ | SLA timing allocation + post-check |
| 3 | `quality/fact_checker.py` | ⑦b | Verify numerical claims (song song hallucination) |
| 4 | `quality/confidence_scorer.py` | ⑦c | Composite score từ hallucination+grounding+fact |
| 5 | `quality/policy_service.py` | ⑦d | STRICT/BALANCED/OPEN policy + dynamic thresholds |
| 6 | `rag_patterns/monitoring.py` | ⑨ | Pattern performance metrics recording |
| 7 | `quality/result_validator.py` | ⑦e | Consolidated validation (retrieval+hallucination+relevance+groundedness) |
| 8 | `infrastructure/retry_handler.py` | ⑤ | Exponential backoff cho memory recall (2 retries) |
| 9 | `memori/memify_service.py` | ⑧b | Background knowledge graph enrichment |
| 10 | `orchestration/analyzer.py` | ⑤d | QueryAnalyzer — phân tích complexity/domain/intent |
| 11 | `orchestration/router.py` | ⑤d | SmartRouter — chọn pattern tối ưu |
| 12 | `orchestration/orchestrator.py` | ⑤d | PatternOrchestrator — điều phối Multi-RAG |
| 13 | `orchestration/registry.py` | ⑤d | PatternRegistry — đăng ký 12 pattern |
| 14 | `orchestration/combinations.py` | ⑤d | 5 tổ hợp Multi-RAG sẵn có |
| 15-21 | `patterns/accuracy,optimization,specialized/*` | ⑤d | 9 pattern services + 3 models |
| 22 | `tools/function_registry.py` | ④b | Extended tool calling (5 built-in: search, calculate, time, format, get_doc) |
| 23 | `core/reranker_service.py` | ⑥b | Cross-encoder citation reranking (top-20→top-5) |
| 24 | `generation/prompt_builder.py` | ⑥a | Standardized RAG prompt (vi/en, memory, citations) |
| 25 | `memori/augmentation_processors_service.py` | ⑧c | AugmentationPipeline (fact+preference+attribute extraction) |
| 26 | `memori/augmentation_service.py` | ⑧c | Augmentation infrastructure (DbWriter, Runtime) |

---

## Bỏ qua / Hoãn lại (có lý do)

| # | File | Lý do |
|---|---|---|
| 1 | `memori/temporal_operations.py` | Memori internal — cần rag_service LLM calls + SemanticTriple, pipeline bên trong manager_service |
| 2 | `generation/response_formatter.py` | Chức năng khác (format OCR/compare/extract/summarize), không phải chat |

---

## Danh sách 1 file chưa tích hợp

| # | Module | File | Lý do |
|---|---|---|---|
| 1 | `core/` | `base_service.py` | Abstract base — không ai kế thừa, cần refactor kiến trúc |

> `service_registry.py` đã được disable (circular imports, dòng 224). Cần refactor toàn bộ services kế thừa BaseService + fix circular imports.
