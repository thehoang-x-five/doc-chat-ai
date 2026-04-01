# RAG-Anything Upload Pipeline (Architecture v2.0)

Tài liệu này giải thích chi tiết flow xử lý tài liệu (upload & processing pipeline) mới được refactor. Kiến trúc mới chuyển từ cơ chế xử lý đồng bộ tuyến tính (monolithic) sang xử lý bất đồng bộ, chia thành nhiều worker độc lập giúp tăng tốc độ xử lý, tránh blocking và đảm bảo chất lượng trích xuất dữ liệu.

---

## 1. Flow Sơ Đồ (Architecture Diagram)

Sơ đồ dưới đây mô tả quá trình từ lúc người dùng submit file cho đến khi dữ liệu sẵn sàng cho Chat/Search.

```mermaid
graph TD
    %% Tầng API & Storage
    User([Người dùng]) -->|1. Upload File| API(Documents API)
    API -->|2. Validate (Type, Size)| Validator{Hợp lệ?}
    Validator -->|Không| Reject[Báo lỗi 400]
    Validator -->|Có| MinIO[(MinIO Storage)]
    
    %% Tầng Database
    MinIO -->|3. Lưu bản gốc| DB[(Database: PostgreSQL)]
    DB -->|4. Tạo Document: NEW| DocV[Tạo Document Version]
    DocV -->|5. Cập nhật Status: INDEXING| JobQ[Tạo Job: OCR_QUEUED]
    
    %% Tầng OCR Worker (Queue: ocr, convert)
    JobQ -->|6. Enqueue OCR| CeleryOCR((Celery OCR Worker))
    CeleryOCR -->|7. Phân tích loại file| Router{Parser Router}
    
    Router -->|Route 0: .txt, .md, .csv| ParserDirect[Direct Text Parser]
    Router -->|Route 1: Image, .pdf có flag, config| ParserSurya[Surya Engine<br>OCR chuyên sâu]
    Router -->|Route 2: Default, Office| ParserDocling[Docling Engine<br>Structural Extraction]
    
    ParserDirect --> Normalize[Bước 8: Normalize Module<br>Chuẩn hóa Schema]
    ParserSurya --> Normalize
    ParserDocling --> Normalize
    
    Normalize -->|9. Kiểm tra chất lượng| QGate{Quality Gate}
    QGate -->|Rỗng hoặc Dưới Threshold| Fail[Document FAILED]
    QGate -->|Pass| Split[Bước 10: Tách luồng (Fork)]
    
    %% Tầng Async Workers song song
    Split -->|File Markdown + JSON| CeleryIndex((Celery INDEX Worker))
    Split -->|JSON + Content_list| CeleryEnrich((Celery ENRICHMENT Worker))
    
    %% Nhánh 1: Indexing
    subgraph Vector RAG nhánh
        CeleryIndex -->|Chunking| Chunk[Cắt văn bản]
        Chunk -->|Embedding API| Embed[Vectorise]
        Embed -->|Lưu pgvector| PGVector[(PGVectorDB)]
        PGVector -->|11a. Cập nhật Status| ReadyBasic[Trạng thái: READY_BASIC<br>Có thể Search RAG!]
    end
    
    %% Nhánh 2: Enrichment (Graph RAG)
    subgraph Graph RAG nhánh
        CeleryEnrich -->|Khởi tạo RAGAnything| RAGA[Graph Pipeline]
        RAGA -->|Trích xuất Entities, Relations| LLM[LLM Processing]
        LLM -->|Lưu Neo4j/LightRAG| GraphDB[(Knowledge Graph)]
        GraphDB -->|11b. Cập nhật Status| ReadyEnriched[Trạng thái: READY_ENRICHED<br>Hoàn thành Semantic Graph!]
    end

    %% Tầng RAG Search (Hybrid)
    ReadyBasic -.-> Hybrid[Hybrid Retriever]
    ReadyEnriched -.-> Hybrid
    User -->|Chat/Search| Hybrid

    classDef worker fill:#f9f,stroke:#333,stroke-width:2px;
    classDef db fill:#bbf,stroke:#333,stroke-width:2px;
    classDef status fill:#cfc,stroke:#333,stroke-width:2px;
    
    class CeleryOCR,CeleryIndex,CeleryEnrich worker;
    class DB,MinIO,PGVector,GraphDB db;
    class ReadyBasic,ReadyEnriched,Fail status;
```

---

## 2. Giải thích chi tiết các bước

### Bước 1-5: Tiếp nhận (Ingestion)
1. **API Upload**: `app/api/v1/documents.py` nhận file. File được validate kích thước và định dạng tệp (whitelist extensions).
2. **Storage**: File gốc được tải lên MinIO/S3 object storage thông qua `ObjectStore`.
3. **Database Records**: Cập nhật vào PosgreSQL:
   - Tạo 1 đối tượng `Document` (status mặc định là `NEW`).
   - Tạo 1 `DocumentVersion` để quản lý versioning (giữ original_file_key).
   - Tạo 1 đối tượng `Job` với type=`OCR`.
4. **Thay đổi trạng thái**: Document chuyển sang `INDEXING`. Tác vụ OCR được đưa vào hàng đợi `ocr` của Celery. Chuyển token cho client để kết thúc request HTTP (Xử lý non-blocking).

### Bước 6-8: Trích xuất Dữ liệu (Parsing & Extraction)
OCR worker (`celery-worker-ocr`) nhận job:
1. Load nội dung file từ MinIO lên temp memory.
2. Tại `surya_engine.py`, hàm **Parser Router** quyết định xem engine nào sẽ xử lý:
   - **Route 0 (Trực tiếp)**: Nếu file là dạng raw text (`.txt`, `.md`, `.csv`, `.json`), bỏ qua AI, đọc nội dung trực tiếp vì file không cần nhận dạng layout.
   - **Route 1 (Deep CV/Surya OCR)**: Khi file là hình ảnh (`.jpg`, `.png`), hoặc có tuỳ chọn Force-Surya từ config. Surya dùng Neural Nets để nhận dạng văn bản trong ảnh/scan, tốc độ chậm nhưng chính xác với văn bản khó.
   - **Route 2 (Docling Structural Extraction)**: Route mặc định cho các file tài liệu số (`.pdf`, `.docx`, `.xlsx`,...). Docling thực hiện chuyển đổi cấu trúc tài liệu sang định dạng DoclingDocument để trích xuất Markdown/JSON trung thực nhất với layout gốc.
3. Sau khi Parsers trả kết quả (dù đi bằng đường nào), dữ liệu thô sẽ qua module **`normalize.py`** (Normalize). Module này sẽ ép kiểu tất cả kết quả về 1 định dạng duy nhất `content_list` chuẩn của thư viện RAG-Anything (chứa block text, image, table caption, math formula...).

### Bước 9: Kiểm duyệt nội dung (Quality Gate)
- Module **Quality Gate** kiểm tra xem lượng chữ (chars) có trên 50 ký tự hay không.
- Nếu Parser chạy xong mà text xuất ra bị rỗng (hoặc chỉ toàn rác), tài liệu bị đánh dấu `FAILED` và luồng kết thúc ngay lập tức, báo lỗi cho người dùng. Điều này ngăn DB bị rác.

### Bước 10+11: Tách luồng (Pipeline Fork)
Đây là thay đổi cốt lõi nhất. Thay vì Worker OCR tự làm nốt các bước (gây nghẽn mạng và treo hàng đợi), ta chia công việc ra làm 2 nhiệm vụ chạy song song:

1. **INDEX Worker** (nhanh, bắt buộc): 
   - Hàm `index.py` sử dụng nội dung văn bản (Markdown/Text) để thực hiện embedding, nhưng **`structured.json` (canonical schema)** luôn là "nguồn sự thật" (Source of Truth) để giữ metadata, toạ độ, số trang và citation chính xác.
   - Dùng `ChunkingService` cắt đoạn và nhúng vector bằng Embedding LLM API.
   - Lưu vào bảng chunk (PGVector).
   - **Update trạng thái**: Tài liệu chuyển sang `READY_BASIC`. *(Lúc này Người dùng đã có thể chat và search nội dung tài liệu ngay lập tức với Vector RAG).*

2. **ENRICHMENT Worker** (chậm, option thêm):
   - Hàm `enrichment.py` nhận gói thông tin cấu trúc (JSON + Tables + Image Data).
   - Khởi động pipeline RAG-Anything Graph. Gọi LLM backend đã cấu hình (Provider Manager) để phân tích Entity, tạo Knowledge Graph Network.
   - **Update trạng thái**: Tài liệu lên cấp cao nhất `READY_ENRICHED`. *(Người dùng lúc này có thêm tính năng Graph RAG nâng cao).*

---

## 3. Hệ Sinh Thái Trạng Thái (Document Statuses)

Các trạng thái được quản lý xuyên suốt `app/db/models.py`. Search Retriever Service hiện tại sẽ lọc theo các status `READY`.

| Tên trạng thái | Diễn giải | Mức khả dụng (Search) |
| --- | --- | --- |
| `NEW` | Mới khởi tạo, API vừa tiếp nhận. | ❌ Trống rỗng |
| `INDEXING` | Nằm đang ở hàng đợi Celery, hoặc đang Parser cắt chữ. | ❌ Trống rỗng |
| `FAILED` | Phân tích thất bại do lỗi file, lỗi mô hình, hoặc rỗng nội dung (Bị Quality Gate chặn). | ❌ Bị loại bỏ |
| **`READY_BASIC`** | **(Trạng thái Mới)** Parser và Vector Index hoàn tất. Dữ liệu đã chia chunk ổn định. Hệ thống Graphic Enrichment chưa xong. | ✅ Query bằng BM25 và Vector. Response khá nhanh. |
| **`READY_ENRICHED`** | **(Trạng thái Mới)** Mọi pipeline RAG Network chạy xong, Knowledge Graph map 100%. | ✅ Tối đa (BM25 + Vector + Graph RAG). |
| `READY` | *(Trạng thái cũ)* Các tài liệu cũ trong CSDL chưa migration. | ✅ Tương đương `READY_BASIC`. |
| `DELETED`/`ARCHIVED` | Xóa mềm hệ thống hoặc khóa tạm thời. | ❌ Bị chặn |

## 4. Tương tác Worker và Hệ thống (Docker Stack)

Hệ thống có cấu hình qua Docker compose.

*   `celery-worker-ocr` (concurrency: 2): Lắng nghe `ocr,convert` queue. Chuyên gọi model AI nặng. Nhanh hay chậm tùy VRAM.
*   `celery-worker-index` (concurrency: 2): Lắng nghe `index,default` queue. Cắt chữ chia nhỏ và embedding API. Nhẹ, tốc độ nhanh.
*   `celery-worker-enrichment` (concurrency: 1): Lắng nghe `enrichment` queue chạy RAG-Anything. Khống chế process=1 để không làm nghẽn cạn LLM Rate Limit bằng các API Calls.

Kiến trúc Async Fork này giúp UI mở khoá linh hoạt, thay vì loading circle báo "đang chờ" hàng giờ đồng hồ như ở version siêu cũ.
