# 🚀 Hướng dẫn cài đặt TheDocAI

## Yêu cầu

- Docker & Docker Compose
- Hoặc: Python 3.10+, Node.js 18+, PostgreSQL 16, Redis

---

## 🐳 Cách 1: Docker (Khuyến nghị)

### Bước 1: Clone & Cấu hình

```bash
git clone https://github.com/your-username/TheDocAI.git
cd TheDocAI

# Copy file cấu hình
cp server/.env.example server/.env
```

### Bước 2: Chỉnh sửa server/.env

```env
# Tối thiểu cần 1 API key
GROQ_API_KEY=gsk_your_key      # https://console.groq.com/keys
# hoặc
DEEPSEEK_API_KEY=sk_your_key   # https://platform.deepseek.com
# hoặc
GEMINI_API_KEY=AIza_your_key   # https://aistudio.google.com/apikey

# JWT Secret (thay đổi!)
JWT_SECRET_KEY=your-secret-key-here
```

### Bước 3: Chạy Docker

```bash
# Start tất cả services
docker-compose up -d

# Kiểm tra status
docker-compose ps
```

### Bước 4: Chạy Migrations (lần đầu)

```bash
docker exec -it thedocai-backend alembic upgrade head
```

### Bước 5: Truy cập

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### Lệnh Docker hữu ích

```bash
# Xem logs
docker-compose logs -f
docker-compose logs -f backend

# Dừng
docker-compose down

# Reset database
docker-compose down -v
docker-compose up -d
docker exec -it thedocai-backend alembic upgrade head

# Rebuild
docker-compose build --no-cache
docker-compose up -d

# Vào shell backend
docker exec -it thedocai-backend bash

# Vào PostgreSQL
docker exec -it thedocai-postgres psql -U postgres -d thedocai
```

---

## 💻 Cách 2: Chạy thủ công

### 2.1 Cài đặt PostgreSQL + pgvector

**Windows:**
```powershell
# Tải PostgreSQL từ https://www.postgresql.org/download/windows/
# Cài pgvector extension

psql -U postgres
CREATE DATABASE thedocai;
\c thedocai
CREATE EXTENSION vector;
\q
```

**Ubuntu:**
```bash
sudo apt install postgresql postgresql-16-pgvector
sudo -u postgres psql
CREATE DATABASE thedocai;
\c thedocai
CREATE EXTENSION vector;
\q
```

### 2.2 Cài đặt Redis

**Windows:**
```powershell
# Dùng Docker
docker run -d -p 6379:6379 redis:7-alpine
```

**Ubuntu:**
```bash
sudo apt install redis-server
sudo systemctl start redis
```

### 2.3 Chạy Backend

```bash
cd server

# Tạo virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Cài dependencies
pip install -r requirements.txt

# Cấu hình
cp .env.example .env
# Chỉnh sửa .env

# Chạy migrations
alembic upgrade head

# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2.4 Chạy Frontend

```bash
cd ../OCR_Ink

# Cài dependencies
npm install

# Start dev server
npm run dev
```

### 2.5 Chạy Celery Worker (optional)

```bash
cd server
celery -A app.queue.celery_app worker --loglevel=info
```

---

## 🤖 Cài Ollama (Optional - Local AI)

```bash
# Windows: Tải từ https://ollama.com/download/windows
# Linux:
curl -fsSL https://ollama.com/install.sh | sh

# Tải models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

---

## ✅ Kiểm tra

```bash
# Health check
curl http://localhost:8000/api/health

# Expected response
{
  "ok": true,
  "version": "1.0.0",
  "enableRag": true
}
```
