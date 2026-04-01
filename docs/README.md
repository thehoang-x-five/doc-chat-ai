# RAG-Anything Documentation

## 📁 PlantUML Diagrams

Thư mục này chứa các file PlantUML mô tả chi tiết kiến trúc và workflow của hệ thống.

### Render Diagrams

Để xem các diagram, sử dụng một trong các cách sau:

1. **VS Code Extension**: PlantUML Preview
2. **Online**: https://www.plantuml.com/plantuml/uml/
3. **CLI**: `plantuml <filename>.puml`

---

## 📋 Files

| File | Description |
|------|-------------|
| [chat_workflow.puml](./chat_workflow.puml) | Complete chat flow với 11 phases và annotations |
| [rag_orchestration.puml](./rag_orchestration.puml) | RAG pipeline: Query Rewriting → Hybrid Search → Rerank → LLM |
| [memori_workflow.puml](./memori_workflow.puml) | Memory system: Short-term + Long-term + Fact Extraction |
| [search_workflow.puml](./search_workflow.puml) | Hybrid Search: Vector + BM25 + RRF + Reranker |
| [system_architecture.puml](./system_architecture.puml) | Full system architecture với all components |

---

## 🔄 Workflow Summary

### Main Chat Flow (11 Phases)
```
User Message
    ↓
1. Security (GuardrailsService, SafetyChecker)     [5-20ms]
    ↓
2. Dedup Check (DedupCache)                        [2-5ms]
    ↓
3. Cache Check (RAGCache, SearchCache)             [5-15ms]
    ↓
4. Intent Detection (IntentDetector)               [50-200ms]
    ↓
5. Memory Recall (ParallelExecutor)                [100-500ms]
    ↓
6. RAG Query (RAGService)                          [500-3000ms]
    ↓
7. Quality Checks (Grounding, Hallucination)       [50-150ms]
    ↓
8. Validation (Confidence, Fact, Result)           [30-100ms]
    ↓
9. Evaluation (10% sampling)                       [0-50ms]
    ↓
10. Save (Database)                                [50-100ms]
    ↓
11. Cleanup (Cache set, Timeline)                  [20-50ms]
    ↓
Return Response
```

### Total Response Time
- 🟢 Cache HIT: **50-100ms**
- 🟢 GREETING/CHITCHAT: **100-300ms**
- 🟡 Normal QUESTION: **1.5-3s**
- 🟠 Complex QUESTION: **3-5s**

---

## 🎯 Factors Affecting Chat

### 1. Mode (Combobox)
| Mode | Description | Use When |
|------|-------------|----------|
| RAG_ONLY | Chỉ dùng context từ documents | Cần độ chính xác cao |
| HYBRID | Kết hợp context + LLM knowledge | Cân bằng |
| LLM_ONLY | Chỉ dùng LLM | Không có documents phù hợp |

### 2. Documents (Combobox)
| Option | Effect |
|--------|--------|
| All Documents | Tìm kiếm toàn bộ workspace |
| Selected Documents | Giới hạn theo document_ids |
| Tagged Documents | Lọc theo tags |

### 3. Model (Combobox)
| Model | Speed | Quality | Cost |
|-------|-------|---------|------|
| GPT-3.5-Turbo | ⚡ Fast | Good | $ |
| GPT-4 | 🐢 Slow | Best | $$$$ |
| Claude-3-Haiku | ⚡ Fast | Good | $ |
| Claude-3-Sonnet | Medium | Very Good | $$ |
| Gemini-1.5-Flash | ⚡ Fast | Good | $ |

---

## 📊 Component Status

| Component | Status | Notes |
|-----------|--------|-------|
| GuardrailsService | ✅ 100% | YAML config required |
| SafetyChecker | ✅ 100% | Regex patterns |
| DedupCache | ✅ 100% | Requires Redis |
| RAGCache | ⚠️ 90% | Optional: gptcache |
| IntentDetector | ✅ 100% | LLM-based |
| ParallelExecutor | ✅ 100% | -50% latency |
| RAGService | ✅ 100% | Core pipeline |
| GroundingVerifier | ✅ 100% | Heuristic |
| HallucinationChecker | ✅ 100% | NLI-based |
| ConfidenceScorer | ✅ 100% | Weighted |
| FactChecker | ✅ 100% | Numerical |
| ResultValidator | ✅ 100% | Async |
| EvaluationService | ⚠️ 90% | Optional: RAGAS |
| TimelineService | ⚠️ 80% | Experimental |
