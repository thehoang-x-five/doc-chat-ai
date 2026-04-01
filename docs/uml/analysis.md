# Phân Tích Chi Tiết Flow Chat RAG — Cập Nhật Sau Fix

> **Ngày phân tích:** 2026-02-22
> **Trạng thái:** ✅ ĐÃ FIX 7/7 VẤN ĐỀ
> **Files sửa:** `hybrid.py`, `service.py`, `stream_manager.py`

---

## 1. Tổng Quan Các Fix Đã Áp Dụng

### 🔴 3 Bug Nghiêm Trọng (P0)

| # | Bug | Root Cause | Fix |
|---|-----|-----------|-----|
| 1 | Memory/Memori/Graph bị mất | `hybrid.py` bỏ qua `kwargs['memory_context']` | `_build_system_prompt()` inject memory vào prompt |
| 2 | Conversation history bị mất | `hybrid.py` chỉ gửi `[system, user]` | `_build_messages()` inject history vào messages |
| 3 | System prompt hardcoded English | String cứng thay vì PromptBuilder | Dùng `PromptBuilder(language="vi")` |

### 🟠 4 Issues Cải Thiện (P1-P2)

| # | Issue | Before | After |
|---|-------|--------|-------|
| 4 | Duplicate query_stream | Query chạy **2 lần** | Query chạy **1 lần** |
| 5 | Intent trước Guardrails | Bypass bảo mật qua GREETING | Guardrails **TRƯỚC** Intent |
| 6 | FC timeout 100ms | Function calling hiếm trigger | Timeout **300ms** |
| 7 | SafetyChecker không dùng | PII không redact | PII **redacted** trước RAG |

---

## 2. Flow Pipeline Mới (Đã Fix)

```
[User Message]
      │
      ▼
① Dedup Cache (Redis)
  ├── HIT → stream cached answer → return
  └── MISS → continue
      │
      ▼
② Input Guardrails ← ✅ TRƯỚC Intent
  ├── Jailbreak detection
  ├── PII filter
  ├── Topic restriction
  ├── Prompt injection
  └── SQL injection
  ├── BLOCKED → safe rejection → return
  └── PASS → continue
      │
      ▼
②b PII Redaction ← ✅ MỚI
  └── SafetyChecker.check_pii(query, redact=True)
      query = redacted_text (if PII found)
      │
      ▼
③ Intent Detection ← ✅ SAU Guardrails
  ├── GREETING/CHITCHAT → direct response → return
  ├── IMAGE_GENERATION → pass to ⑤
  └── DOCUMENT_QUERY/OTHER → continue
      │
      ▼
④ Function Calling ← ✅ 300ms timeout
  ├── Metadata query → FC result → return
  └── Not applicable → continue
      │
      ▼
⑤ Image Generation
  ├── IMAGE_GENERATION intent → generate → return
  └── Otherwise → continue
      │
      ▼
⑥ Memory Recall (parallel)
  ├── MemoryManager (session context)
  ├── MemoriManager (long-term facts)
  └── GraphSearchService (knowledge graph)
  → combined_memory = Memory + Facts + Graph
      │
      ▼
⑦ RAG Stream + Prompt Construction ← ✅ FIXED
  │
  │  HybridRAGService.query_stream() now:
  │  1. Retrieves top-5 chunks (Vector Search)
  │  2. _build_system_prompt():
  │     ├── PromptBuilder.get_system_prompt(RAG, "vi")
  │     ├── + "Lịch sử hội thoại:" + memory_context ← ✅
  │     └── + "Ngữ cảnh từ tài liệu:" + chunks
  │  3. _build_messages():
  │     ├── {"role": "system", "content": full_prompt}
  │     ├── conversation_history[0..9] ← ✅
  │     └── {"role": "user", "content": question}
  │  4. manager.stream_chat_completion(messages)
  │  5. yield citations metadata
      │
      ▼
⑧ Post-Stream Quality
  ├── HallucinationChecker.check_faithfulness
  └── GroundingVerifier.verify
  → Append disclaimers if needed
      │
      ▼
⑨ Save + Background
  ├── Save assistant message + citations
  ├── Auto-title conversation
  ├── AutoCognify (background)
  └── DedupCache.set (background)
      │
      ▼
[Response Complete → DONE event]
```

---

## 3. Chi Tiết Fix: hybrid.py

### Trước Fix:
```python
# HARDCODED English, no memory, no history
system_prompt = (
    "You are a helpful AI assistant..."
    f"Context:\n{context_text}\n\n"
)
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": question}   # ← NO history
]
```

### Sau Fix:
```python
# _build_system_prompt() — PromptBuilder + memory
def _build_system_prompt(self, context_text, memory_context=None):
    builder = PromptBuilder(language="vi")
    base = builder.get_system_prompt(PromptType.RAG, "vi")
    # + memory_context section
    # + context_text section
    return full_prompt

# _build_messages() — history injection
def _build_messages(self, question, system_prompt, conversation_history=None):
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        for msg in conversation_history:
            messages.append(msg)         # ← HISTORY INJECTED
    messages.append({"role": "user", "content": question})
    return messages
```

---

## 4. Chi Tiết Fix: service.py

### Trước Fix (duplicate code):
```python
# Block 1 — simulated streaming (dòng 299-307)
response = await self.query(...)  # ← Chạy LẦN 1
for i in range(0, len(text), chunk_size): yield ...

# Block 2 — copy-paste y hệt (dòng 310-338)
response = await self.query(...)  # ← Chạy LẦN 2
for i in range(0, len(text), chunk_size): yield ...
```

### Sau Fix:
```python
# Single fallback — chạy 1 lần duy nhất
response = await self.query(...)  # ← Chạy 1 LẦN
for i in range(0, len(text), chunk_size): yield ...
# + yield citations
```

---

## 5. Chi Tiết Fix: stream_manager.py

### Thay Đổi Thứ Tự:
```diff
- ② Intent Detection (TRƯỚC guardrails → bypass possible)
- ③ Guardrails

+ ② Guardrails (TRƯỚC intent → no bypass)
+ ②b PII Redaction (SafetyChecker)
+ ③ Intent Detection (SAU guardrails → safe only)
```

### FC Timeout:
```diff
- timeout=0.1  # 100ms timeout
+ timeout=0.3  # 300ms timeout
```

### PII Redaction (mới):
```python
from app.services.quality.safety_checker import SafetyChecker
safety = SafetyChecker(guardrails_service=guardrails)
pii_result = safety.check_pii(query, redact=True)
if pii_result.has_pii:
    query = pii_result.redacted_text
```

---

## 6. So Sánh Trước/Sau Fix

| Tiêu chí | Trước Fix | Sau Fix |
|---|---|---|
| Memory đến LLM | ❌ Mất | ✅ Injected |
| History đến LLM | ❌ Mất | ✅ Injected |
| System prompt | EN hardcoded | ✅ VI PromptBuilder |
| Guardrails order | Intent trước | ✅ Guardrails trước |
| PII handling | Block only | ✅ Block + Redact |
| FC timeout | 100ms | ✅ 300ms |
| query_stream calls | 2x (duplicate) | ✅ 1x |
| Bot nhớ context? | ❌ | ✅ |
| Bot biết history? | ❌ | ✅ |
| Bot trả lời VN? | ⚠️ EN prompt | ✅ VN prompt |

---

## 7. Công Việc Còn Lại (P2-P3)

### P2 — Performance
- [ ] RAGCacheService — cache RAG results trong StreamManager
- [ ] Cache graph_context

### P3 — Code Quality
- [ ] Refactor repeated message-saving pattern
- [ ] Tạo UML: OCR flow
- [ ] Tạo UML: Document indexing
- [ ] Tích hợp ConfidenceScorer
- [ ] Tích hợp FactChecker
