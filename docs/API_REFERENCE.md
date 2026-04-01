# 🔌 API Reference

Base URL: `http://localhost:8000`

## Authentication

Tất cả endpoints (trừ auth) yêu cầu JWT token:
```
Authorization: Bearer <access_token>
```

---

## Auth Endpoints

### POST /api/v1/auth/register
Đăng ký tài khoản mới.

```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "Nguyen Van A"
}
```

### POST /api/v1/auth/login
Đăng nhập.

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### POST /api/v1/auth/refresh
Refresh access token.

---

## Workspace Endpoints

### GET /api/v1/workspaces
Lấy danh sách workspaces.

### POST /api/v1/workspaces
Tạo workspace mới.

```json
{
  "name": "My Workspace"
}
```

### GET /api/v1/workspaces/{workspace_id}
Lấy chi tiết workspace.

---

## Document Endpoints

### POST /api/v1/workspaces/{workspace_id}/documents
Upload tài liệu.

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf" \
  http://localhost:8000/api/v1/workspaces/{id}/documents
```

### GET /api/v1/workspaces/{workspace_id}/documents
Lấy danh sách tài liệu.

### DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}
Xóa tài liệu.

---

## Chat Endpoints

### POST /api/v1/workspaces/{workspace_id}/chat
Gửi câu hỏi RAG.

```json
{
  "message": "Tóm tắt nội dung tài liệu",
  "conversation_id": "uuid-optional"
}
```

Response:
```json
{
  "answer": "Tài liệu nói về...",
  "citations": [
    {
      "document_title": "report.pdf",
      "content": "...",
      "page": 5,
      "score": 0.85
    }
  ],
  "provider": "deepseek",
  "model": "deepseek-chat"
}
```

### GET /api/v1/workspaces/{workspace_id}/conversations
Lấy lịch sử hội thoại.

---

## OCR Endpoints

### POST /api/ocr/process
OCR tài liệu.

```bash
curl -X POST \
  -F "file=@scan.pdf" \
  -F "parser=docling" \
  http://localhost:8000/api/ocr/process
```

---

## Health Endpoints

### GET /api/health
Kiểm tra trạng thái hệ thống.

Response:
```json
{
  "ok": true,
  "version": "1.0.0",
  "enableRag": true,
  "aiProviders": {
    "cloudcode": {"available": true},
    "deepseek": {"available": true},
    "gemini": {"available": true},
    "groq": {"available": true},
    "ollama": {"available": false}
  }
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Default | 100/minute |
| Auth | 10/minute |
| Upload | 20/minute |
