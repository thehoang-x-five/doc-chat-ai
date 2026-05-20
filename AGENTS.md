# Repository Guidelines for TheDocAI

## Project Overview
TheDocAI (formerly doc-chat-ai/RAG-Anything) is a full-stack AI knowledge assistant system leveraging RAG (Retrieval-Augmented Generation), advanced OCR (**PaddleOCR PP-OCRv5 / PPStructureV3** for images, scanned PDFs, and mixed-PDF page/sub-OCR, **Docling** for digital docs, Surya legacy retained, PDF routing via `server/app/core/engines/pdf_routing.py`), structure-aware chunking built on LlamaIndex SentenceSplitter, configurable local embeddings, and a specialized Memory Graph (Memori) with optional strict Neo4j enforcement.

## Target Audience for this Document
**AI Coding Agents**: When performing tasks in this repository, you MUST follow these directory structures, dependency rules, and architectural guidelines to maintain consistency.

---

## 🏗️ Directory Structure & Module Organization

```text
TheDocAI/
├── AGENTS.md                 # 🤖 AI Guidelines & Rules (This file)
├── docker-compose.yml        # 🐳 Main deployment config (Bind mounts enabled)
├── docs/                     # 📚 System Architecture & Documentation
│   ├── README.md             # Project & Setup documentation
│   ├── ERD_DIAGRAM.md        # Database schema diagrams
│   └── SYSTEM_ARCHITECTURE_DIAGRAM.md
├── frontend/                 # 💻 Web UI (React + Vite)
│   ├── Dockerfile            # Vite Dev Server Setup (Hot Reload)
│   ├── package.json          # Node dependencies & UI scripts
│   ├── tailwind.config.ts    # Styling configuration & design tokens
│   └── src/                  # Frontend Source Code
│       ├── App.tsx           # Main React component, routing wrapper
│       ├── main.tsx          # React DOM entry
│       ├── routes/           # 🗺️ Core Pages (Chat, KnowledgeBase, MemoryManagement)
│       ├── components/       # 🧩 UI Component folders (auth, chat, common, layout, memori, search, ui)
│       ├── hooks/            # 🪝 React Hooks (e.g., useMemori.ts)
│       ├── lib/              # 🔌 Utilities & Connections
│       │   ├── hooks/        # Specialized logic hooks (useCitations, useMessages)
│       │   ├── i18n/         # Internationalization and translation files
│       │   └── api.ts        # Axios client
│       ├── utils/            # Shared TS utilities (file.ts)
│       └── types/            # TypeScript interfaces
└── server/                   # 🧠 Backend (FastAPI + Python)
    ├── Dockerfile            # Multi-layer build configuration
    ├── requirements.txt      # 📦 FROZEN – DO NOT EDIT (see §2 below)
    ├── requirements-extra.txt# 🪶 ALL new packages go HERE (see §2 below)
    ├── alembic/              # Database migration scripts
    ├── config/               # YAML configurations (Guardrails, Orchestration)
    ├── scripts/              # Admin scripts (DB reset, memory debug)
    └── app/                  # Application Code
        ├── main.py           # Application entrypoint
        ├── api/              # 🔌 API Route Controllers
        │   ├── deps.py       # FastAPI Dependencies (auth, db get)
        │   └── v1/           # Endpoints (chat, memori, documents, auth)
        ├── core/             # Application configs and core processors
        │   ├── config.py             # Env Settings
        │   ├── security.py           # JWT & Auth
        │   ├── engines/              # OCR/Extraction Engines
        │   │   ├── surya_engine.py   # (Legacy – retained, not active by default)
        │   │   ├── paddleocr_engine.py # ✅ Active – PaddleOCR PP-OCRv5 + PPStructureV3
        │   │   └── docling (inline)  # Used via DocumentConverter in ocr.py
        │   └── processors/           # Data normalizers (e.g., Vietnamese text)
        ├── db/               # PostgreSQL & SQLAlchemy Models
        │   ├── session.py            # DB Session/Connection
        │   ├── models.py             # ORM Definitions
        │   └── repos/                # Repository Pattern wrappers
        ├── middleware/       # FastAPI Middleware (Rate Limit, Error Handling, Logging)
        ├── models/           # Logic Enums & Legacy schemas
        ├── schemas/          # Pydantic Request/Response DTOs (auth, chat, etc.)
        ├── queue/            # ⚡ Celery Background Task Definitions
        │   ├── celery_app.py
        │   └── tasks/        # Workers (ocr, index, convert, enrichment)
        ├── storage/          # 🗄️ MinIO/S3 integrations
        ├── utils/            # Helper functions
        └── services/         # 🏢 Core Business Logic Domains
            ├── analytics/            # System metrics and dashboard data
            ├── auth/                 # API Key & JWT authorization logic
            ├── conversation/         # Chat pipelines, Intent detectors, Semantic Routers
            ├── core/                 # Retrieval, Embeddings, Context Budget
            │   └── rag/              # RAG Wrappers & Factory
            ├── documents/            # Chunking (LlamaIndex SentenceSplitter) and file processing
            ├── generation/           # Prompt Builders, Response Formatters, Summarize
            ├── infrastructure/       # Telemetry, Cache
            │   └── ai_providers/     # DeepSeek, Gemini, OpenAI wrappers
            ├── memori/               # 🧠 Graph memory, Entity extraction
            ├── quality/              # NeMo Guardrails, Verification
            ├── rag_patterns/         # Advanced Orchestration
            │   ├── orchestration/
            │   ├── pipeline/
            │   └── patterns/         # Specialized RAG (accuracy, optimization)
            ├── search/               # Hybrid search
            └── tools/                # Agentic function calling integrations
```

> **📌 For an EXHAUSTIVE, file-by-file list including all exported functions, classes, and methods, refer to [`docs/CODEBASE_INVENTORY.md`](./docs/CODEBASE_INVENTORY.md).**

---

## 🛠️ Development & Workflow Guidelines

### 0. Context Gathering (MANDATORY)
Before writing any code or modifying existing features, you MUST:
1. Review the Directory Structure in this file (`AGENTS.md`) to locate the relevant domain (e.g., `services/conversation/`).
2. Search through `docs/CODEBASE_INVENTORY.md` to identify all exported functions and classes related to the task.
3. Use your tools to read the actual contents of every relevant file identified in step 2 to fully understand the existing architecture, dependencies, and execution flow. 
**Never modify a file without comprehensively understanding its surrounding context.**

### 1. Zero-Rebuild Code Changes (Bind Mounts)
Both Frontend and Backend use Docker **bind mounts** for development. DO NOT rebuild the entire container just for code changes.
- **Frontend Changes**: Vite dev server is running. Just save the file, and changes reflect instantly via Hot Module Replacement (HMR).
- **Backend/Celery Changes**: Save the file, then restart the specific container:
  ```bash
  docker-compose restart backend
  docker-compose restart celery-worker-ocr
  # (or index/enrichment workers depending on what was edited)
  ```

### 2. Dependency Management (⚠️ CRITICAL — READ CAREFULLY)
To avoid massive 15-minute rebuild times caused by heavy ML libraries, the Python backend uses a **two-layer dependency system**.

**🔒 `server/requirements.txt` — FROZEN. DO NOT EDIT.**
> This file is the Docker-cached heavy layer (Docling, Surya, SQLAlchemy, FastAPI, sentence-transformers, etc.). Modifying it triggers a full Docker rebuild (~15 min). It must NEVER be touched for routine work.

**✅ `server/requirements-extra.txt` — ALL new packages go here. NO EXCEPTIONS.**
> Whether the package is large or small, if it is **new**, it goes into `requirements-extra.txt`. This includes PaddleOCR, LlamaIndex, and any future additions. After adding, run:
> ```bash
> docker-compose up -d --build
> ```
> Docker will reuse the cached heavy layer and only install the new packages (~30 seconds).

**Summary rule**: _If the package is not already in `requirements.txt`, it goes into `requirements-extra.txt`. Period._

### 3. File Addition and Modification Rules
- **Additions**: When adding a new feature, mirror the existing structure. If adding an API, add the route in `app/api/`, logic in `app/services/`, and schemas in `app/models/`.
- **Modifications**: Keep changes localized. Do not alter the core execution flow unless explicitly asked.
- **Naming**: Use `snake_case` for Python files/variables/functions and `PascalCase` for Python classes. Use `PascalCase` for React components (`.tsx`) and `camelCase` for TypeScript utilities (`.ts`).
- **Imports**: Ensure absolute imports map correctly (Backend uses `app.module`, Frontend uses `@/module`).

### 4. Code & Documentation Sync (⛔ ABSOLUTE RULE — ZERO TOLERANCE)
Whenever you create a new file, add a new class, or create/delete a significant function, you **MUST IMMEDIATELY** update **BOTH** of the following documents before finishing the task:

1. **`docs/CODEBASE_INVENTORY.md`** — Add/remove the file path, class names, and exported functions so the inventory is always 100% accurate.
2. **`AGENTS.md`** (this file) — If a new module folder or engine is created, update the directory structure tree above.

_Failure to update **BOTH** files after modifying the codebase is considered a **severe violation** of instructions. No exceptions._

## 📊 Infrastructure
- **Main DB**: PostgreSQL + pgvector (port 5432).
- **Cache & Queue Broker**: Redis (port 6379).
- **Blob Storage**: MinIO (port 9000).
- **Background Workers**: 3 dedicated Celery queues (`ocr`, `index`, `enrichment`).
