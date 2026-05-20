# Phân Tích So Sánh Parser Pipeline: Chatbot vs TheDocAI

> Sơ đồ UML chi tiết: [parser_comparison.puml](file:///c:/Users/THINKPAD/Documents/GitHub/doc-chat-ai/docs/uml/parser_comparison.puml)

---

## 1. Tổng Quan Kiến Trúc

### Chatbot — `AdvancedParser`

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| PDF Parser | **pdfplumber** + **PyMuPDF** (fitz) | Text layer + metadata + images |
| OCR Engine | **Pytesseract** (Tesseract 4.x LSTM) | Scanned pages + embedded images |
| DOCX Parser | **python-docx** + XML parse | Text + inline image positions |
| Chunker | **LlamaIndex** SentenceSplitter | Sentence-aware chunking |
| Embedder | **SentenceTransformer** (local CPU) | Vector embedding |
| Vector Store | **ChromaDB** | Lưu trữ vector |
| Async Workers | **1 Celery worker duy nhất** | Xử lý tuần tự |

### TheDocAI — `SuperRAG Pipeline`

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Digital Parser | **Docling** (DocLayNet model) | Layout-aware parsing |
| OCR Engine | **Surya 0.12** (Vision Transformer) | Full-page vision OCR |
| Normalize | Custom `normalize.py` | Canonical schema → content_list |
| Chunker | Custom `ChunkingService` | Structure-aware chunking |
| Embedder | API-based (Gemini/OpenAI) | Vector embedding |
| Vector Store | **pgvector** (PostgreSQL) | Lưu trữ vector |
| Graph Store | **RAG-Anything** (Knowledge Graph) | Entity + relation enrichment |
| Async Workers | **3 Celery workers** (OCR, Index, Enrichment) | Song song hóa |

---

## 2. So Sánh OCR Engine: Tesseract vs Surya

### Bảng Benchmark

| Tiêu chí | 🟢 Pytesseract (Chatbot) | 🔵 Surya (TheDocAI) |
|---|---|---|
| **Kiến trúc** | LSTM (1 layer, C++ native) | Vision Transformer (ViT, PyTorch) |
| **Số models** | 1 (tesseract binary) | **5 models** (Foundation, Detection, Recognition, Layout, TableRec) |
| **RAM tối thiểu** | ~100-200 MB | **~2-4 GB** (5 models) |
| **Hỗ trợ GPU** | ❌ Không (CPU only) | ✅ **Có** (CUDA nếu có), **fallback CPU** |
| **Thời gian xử lý (1 trang)** | ~1-3 giây | ~10-30 giây (CPU) / ~3-8 giây (GPU) |
| **Accuracy tiếng Việt** | ~80-85% | **~93-97%** |
| **Accuracy tiếng Anh** | ~90% | **~97%** |
| **Layout Analysis** | ❌ Không | ✅ 12+ loại vùng (heading, table, equation, figure, code...) |
| **Table Recognition** | pdfplumber (rule-based) | ✅ **ML-based** Table Structure Recognition |
| **Math/Equation OCR** | ❌ Không | ✅ `math_mode=True` (LaTeX output) |
| **Reading Order** | Không (top-to-bottom) | ✅ Smart reading order detection |
| **Highres Support** | ❌ | ✅ DPI 96 (detect) + DPI 192 (recognize) |
| **Confidence Score** | Có (per-character) | ✅ Có (per-line, tổng hợp per-page) |

> [!IMPORTANT]
> ### Surya chạy CPU hay GPU?
> 
> Surya là **PyTorch model**, tự động detect hardware:
> - **Có CUDA GPU** → chạy GPU (nhanh gấp ~3-5x)
> - **Không có GPU** → **fallback CPU** (chậm nhưng vẫn hoạt động)
> 
> Trong Docker container của TheDocAI hiện tại, **không có GPU** (image base là `python:3.10-slim`), nên Surya **đang chạy hoàn toàn bằng CPU**. Đây là lý do xử lý lâu.
>
> Chatbot dùng Tesseract — cũng **chỉ CPU**, nhưng Tesseract là C++ compiled binary nên nhanh hơn nhiều so với PyTorch inference trên CPU.

---

## 3. So Sánh Text Parsing: Docling vs pdfplumber

| Tiêu chí | 🟢 pdfplumber (Chatbot) | 🔵 Docling (TheDocAI) |
|---|---|---|
| **Phương pháp** | Rule-based (heuristic) | **ML-based** (DocLayNet) |
| **Digital PDF accuracy** | ~90% | **~97%** |
| **Table extraction** | Heuristic (viền rõ ràng) | ML structure detection |
| **Output format** | Plain text | **Markdown + JSON structured** |
| **DOCX support** | python-docx (basic) | **Full OOXML parse** |
| **PPTX support** | python-pptx (basic) | ✅ Docling native |
| **XLSX support** | openpyxl (basic) | ✅ Docling native |
| **Multi-format nhất quán** | ❌ Mỗi format 1 parser riêng | ✅ Cùng 1 API: `DocumentConverter.convert()` |
| **Image region detection** | ❌ Không | ✅ PictureItem + bbox pixel |
| **RAM** | ~50-100 MB | ~500 MB - 1 GB |

> [!NOTE]
> ### Điểm mạnh thực sự của Docling
> Docling không chỉ extract text — nó **hiểu cấu trúc**. Với 1 file PDF phức tạp có cả heading, table, figure, equation, Docling sẽ:
> 1. Phân loại từng vùng theo loại (text, table, picture, equation...)
> 2. Xuất Markdown có heading levels đúng (`# ## ###`)
> 3. Table → structured JSON (có thể query)
> 4. Image → bbox tọa độ pixel → crop → sub-OCR
>
> pdfplumber chỉ extract text "phẳng" và tables (nếu có viền rõ ràng).

---

## 4. So Sánh Image Processing: Tesseract vs Surya

### Với ảnh embedded trong DOCX

| Bước | Chatbot | TheDocAI |
|---|---|---|
| Tìm ảnh | XML parse `word/_rels/` | XML parse `word/_rels/` (giống nhau) |
| OCR ảnh | `pytesseract.image_to_string(img, lang='vie+eng')` | `SuryaEngine._recognition_predictor([pil_img])` |
| Position-aware | ✅ Insert text đúng vị trí paragraph | ✅ Insert text đúng vị trí paragraph |
| Quality | ~80-85% | **~93-97%** |
| Speed | **Nhanh** (~0.5-2s/ảnh) | Chậm (~5-15s/ảnh trên CPU) |

> [!WARNING]
> ### Cả 2 project đều có cùng logic inline DOCX image OCR
> Code XML parse, namespace handling, rId→media mapping, paragraph-position insertion gần như **copy 1:1** giữa 2 project. Sự khác biệt duy nhất là OCR engine gọi bên trong (Tesseract vs Surya).

### Với ảnh standalone (JPG/PNG upload trực tiếp)

| Bước | Chatbot | TheDocAI |
|---|---|---|
| OCR | Tesseract (`vie+eng`) | Surya (Detection → Recognition) |
| Layout | ❌ | ✅ 12+ region types |
| Table trong ảnh | ❌ | ✅ TableRecPredictor |
| Equation | ❌ | ✅ LaTeX OCR |
| Fallback nếu text ít | Tạo description text placeholder | Quality gate → FAILED |

---

## 5. So Sánh Pipeline Tổng Thể

| Tiêu chí | 🟢 Chatbot | 🔵 TheDocAI |
|---|---|---|
| **Số worker** | 1 | 3 (OCR, Index, Enrichment) |
| **Song song hóa** | ❌ Serial | ✅ Index + Enrichment song song |
| **Knowledge Graph** | ❌ | ✅ RAG-Anything |
| **Quality Gate** | `len(text) < 50` → fail | `normalize.py` + multimodal check |
| **Dedup** | ❌ | ✅ SHA-256 checksum |
| **Error Recovery** | Status FAILED, no retry | Retry (max 3), graceful degradation |
| **Normalize** | ❌ Mỗi parser ra format riêng | ✅ Canonical schema chung |
| **Chunking** | LlamaIndex sentence-based | Custom structure-aware (heading/section) |

---

## 6. Phân Tích: Nên Làm Gì?

### 🔴 Vấn đề hiện tại của TheDocAI

1. **Surya chạy CPU quá chậm**: 5 PyTorch models inference trên CPU → 10-30s/trang
2. **RAM cao**: 2-4 GB cho Surya models, chưa kể Docling (~1 GB)
3. **Lãng phí**: Dùng Surya để OCR ảnh nhỏ trong DOCX (icons, logos) khi Tesseract có thể làm nhanh hơn

### 🟢 Điểm mạnh cần giữ của TheDocAI

1. **Docling cho digital docs**: Accuracy rất cao, structured output tốt
2. **Normalize + Quality Gate**: Pipeline chuẩn, mọi parser đều về 1 schema
3. **3 workers song song**: Index không đợi Enrichment
4. **Knowledge Graph enrichment**: RAG-Anything cho semantic search nâng cao

### 🟢 Điểm mạnh cần học từ Chatbot

1. **Tesseract nhanh**: Phù hợp cho OCR nhanh, ảnh nhỏ, text rõ ràng
2. **LlamaIndex SentenceSplitter**: Sentence-aware tốt hơn fixed-size chunking
3. **Local embedding model**: Không tốn API call → zero-cost, zero-latency

---

## 7. Đề Xuất Chiến Lược Tối Ưu (Hybrid Smart Parser)

> [!IMPORTANT]
> ### Nguyên tắc: Router Thông Minh — Chọn Engine Theo Đặc Tính File

```
File vào
  │
  ├─ Digital PDF / DOCX / PPTX / XLSX
  │   └→ Docling (nhanh, chính xác, structured)
  │       └─ Nếu có ảnh embedded:
  │           ├─ Ảnh nhỏ (<200px) → SKIP (decorative)
  │           ├─ Ảnh text rõ ràng → Tesseract (nhanh)
  │           └─ Ảnh phức tạp (bảng/formula/handwriting) → Surya (chính xác)
  │
  ├─ Scanned PDF (không text layer)
  │   ├─ Ưu tiên: Surya + GPU (nếu có CUDA)
  │   └─ Fallback: Tesseract (nếu không có GPU hoặc timeout)
  │
  ├─ Image file (JPG/PNG)
  │   ├─ Ưu tiên: Surya (layout + OCR)
  │   └─ Fallback: Tesseract (nếu timeout > 30s)
  │
  └─ TXT / MD / CSV / JSON
      └→ Đọc trực tiếp (không cần parse)
```

### Hành động cụ thể:

| # | Việc cần làm | Ưu tiên | Lý do |
|:---:|---|:---:|---|
| 1 | **Thêm Tesseract** vào TheDocAI Docker image | 🔴 Cao | OCR nhanh cho ảnh nhỏ, fallback khi Surya chậm |
| 2 | **Thêm GPU support** cho Surya | 🟡 Trung bình | `nvidia/cuda:12.x` base image + `torch+cu12x`. Tăng tốc 3-5x |
| 3 | **Smart image router** trong DOCX inline OCR | 🔴 Cao | Skip ảnh <200px, dùng Tesseract cho ảnh rõ, Surya cho ảnh phức tạp |
| 4 | **Timeout + fallback** cho Surya | 🔴 Cao | Nếu Surya xử lý > 60s/trang → fallback Tesseract |
| 5 | **Cache Surya models** cross-task | 🟡 Trung bình | Tránh load 5 models mỗi lần (hiện đã có lazy init) |
| 6 | **Batch processing** tối ưu | 🟢 Thấp | Batch size = 2 (hiện tại) là OK cho CPU, tăng nếu có GPU |

> [!TIP]
> ### Tóm tắt 1 câu
> Giữ **Docling + Surya** cho độ chính xác cao, nhưng **thêm Tesseract** làm fast-path OCR cho ảnh nhỏ và fallback timeout. Đầu tư **GPU Docker image** nếu muốn Surya nhanh ngang Tesseract mà accuracy vẫn cao.
