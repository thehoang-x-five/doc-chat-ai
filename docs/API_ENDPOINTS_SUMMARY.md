# API Endpoints Summary - Hệ thống RAG cho Sinh viên

> **Mục đích**: Tài liệu API endpoints phục vụ cho đề tài "Hệ thống AI hỗ trợ sinh viên học tập với RAG"

---

## 🔐 1. Authentication & User Management

### **POST /api/v1/auth/register**
Đăng ký tài khoản mới

**Request**:
```json
{
  "email": "student@example.com",
  "password": "password123",
  "full_name": "Nguyễn Văn A"
}
```

**Response**:
```json
{
  "user": {
    "id": "uuid",
    "email": "student@example.com",
    "full_name": "Nguyễn Văn A",
    "role_global": "USER",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### **POST /api/v1/auth/login**
Đăng nhập

**Request**:
```json
{
  "email": "student@example.com",
  "password": "password123"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "student@example.com",
    "full_name": "Nguyễn Văn A",
    "role_global": "USER"
  }
}
```

---

### **POST /api/v1/auth/refresh**
Refresh access token

**Request**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response**: Tương tự `/login`

---

### **POST /api/v1/auth/logout**
Đăng xuất

**Headers**: `Authorization: Bearer <access_token>`

**Response**:
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

### **GET /api/v1/auth/me**
Lấy thông tin user hiện tại

**Headers**: `Authorization: Bearer <access_token>`

**Response**:
```json
{
  "id": "uuid",
  "email": "student@example.com",
  "full_name": "Nguyễn Văn A",
  "role_global": "USER",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## 🏫 2. Workspace (Môn học) Management

### **POST /api/v1/workspaces**
Tạo môn học mới (Admin only)

**Request**:
```json
{
  "name": "Nhập môn lập trình",
  "plan": "free",
  "answer_policy": "balanced",
  "evidence_threshold": 0.7
}
```

**Response**:
```json
{
  "id": "workspace-uuid",
  "name": "Nhập môn lập trình",
  "owner_id": "user-uuid",
  "plan": "free",
  "answer_policy": "balanced",
  "evidence_threshold": 0.7,
  "created_at": "2024-01-01T00:00:00Z",
  "member_count": 0
}
```

---

### **GET /api/v1/workspaces**
Lấy danh sách môn học

**Query Params**:
- `limit`: int (default: 50)
- `offset`: int (default: 0)

**Response**:
```json
{
  "workspaces": [
    {
      "id": "workspace-uuid",
      "name": "Nhập môn lập trình",
      "owner_id": "user-uuid",
      "plan": "free",
      "answer_policy": "balanced",
      "evidence_threshold": 0.7,
      "created_at": "2024-01-01T00:00:00Z",
      "member_count": 25
    }
  ],
  "total": 1
}
```

---

### **GET /api/v1/workspaces/{workspace_id}**
Lấy chi tiết môn học

**Response**:
```json
{
  "id": "workspace-uuid",
  "name": "Nhập môn lập trình",
  "owner_id": "user-uuid",
  "plan": "free",
  "answer_policy": "balanced",
  "evidence_threshold": 0.7,
  "created_at": "2024-01-01T00:00:00Z",
  "member_count": 25,
  "members": [
    {
      "user_id": "user-uuid",
      "email": "student@example.com",
      "full_name": "Nguyễn Văn A",
      "role": "VIEWER",
      "joined_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

### **POST /api/v1/workspaces/{workspace_id}/members**
Thêm sinh viên vào môn học (Admin/Teacher)

**Request**:
```json
{
  "email": "student@example.com",
  "role": "VIEWER"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Member added successfully"
}
```

---

### **DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}**
Xóa sinh viên khỏi môn học

**Response**:
```json
{
  "success": true,
  "message": "Member removed successfully"
}
```

---

## 📄 3. Document Management

### **POST /api/v1/documents/upload**
Upload tài liệu (Teacher only)

**Request** (multipart/form-data):
```
workspace_id: uuid
file: File (PDF, DOCX, TXT)
tags: string (comma-separated, optional)
```

**Response**:
```json
{
  "id": "document-uuid",
  "workspace_id": "workspace-uuid",
  "title": "Slide Chương 1.pdf",
  "doc_type": "pdf",
  "source": "upload",
  "tags": ["chương-1", "giới-thiệu"],
  "status": "NEW",
  "processing_progress": 0,
  "processing_step": null,
  "created_by": "user-uuid",
  "created_at": "2024-01-01T00:00:00Z",
  "size": 5242880,
  "mime_type": "application/pdf",
  "chunk_count": 0,
  "version": 1
}
```

---

### **GET /api/v1/documents**
Lấy danh sách tài liệu

**Query Params**:
- `workspace_id`: uuid (required)
- `status`: string (optional: NEW, INDEXING, READY, FAILED)
- `tags`: string (comma-separated, optional)
- `search`: string (optional)
- `skip`: int (default: 0)
- `limit`: int (default: 50)

**Response**:
```json
{
  "documents": [
    {
      "id": "document-uuid",
      "workspace_id": "workspace-uuid",
      "title": "Slide Chương 1.pdf",
      "doc_type": "pdf",
      "source": "upload",
      "tags": ["chương-1"],
      "status": "READY",
      "processing_progress": 100,
      "processing_step": "completed",
      "content_summary": "Chương 1 giới thiệu về...",
      "created_by": "user-uuid",
      "created_at": "2024-01-01T00:00:00Z",
      "size": 5242880,
      "mime_type": "application/pdf",
      "chunk_count": 150,
      "version": 1
    }
  ],
  "total": 1
}
```

---

### **GET /api/v1/documents/{document_id}**
Lấy chi tiết tài liệu

**Response**:
```json
{
  "id": "document-uuid",
  "workspace_id": "workspace-uuid",
  "title": "Slide Chương 1.pdf",
  "doc_type": "pdf",
  "source": "upload",
  "tags": ["chương-1"],
  "status": "READY",
  "processing_progress": 100,
  "content_summary": "Chương 1 giới thiệu về...",
  "created_by": "user-uuid",
  "created_at": "2024-01-01T00:00:00Z",
  "size": 5242880,
  "mime_type": "application/pdf",
  "chunk_count": 150,
  "version": 1,
  "versions": [
    {
      "id": "version-uuid",
      "version": 1,
      "mime_type": "application/pdf",
      "size_bytes": 5242880,
      "page_count": 50,
      "language_detected": "vi",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "latest_version": {
    "id": "version-uuid",
    "version": 1,
    "mime_type": "application/pdf",
    "size_bytes": 5242880,
    "page_count": 50,
    "language_detected": "vi",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### **PUT /api/v1/documents/{document_id}**
Cập nhật tags tài liệu

**Request**:
```json
{
  "tags": ["chương-1", "giới-thiệu", "cơ-bản"]
}
```

**Response**: Tương tự GET `/documents/{document_id}`

---

### **DELETE /api/v1/documents/{document_id}**
Xóa tài liệu (soft delete)

**Response**:
```json
{
  "success": true,
  "message": "Document deleted"
}
```

---

### **GET /api/v1/documents/{document_id}/chunks**
Lấy danh sách chunks của tài liệu

**Query Params**:
- `version`: int (optional, default: latest)

**Response**:
```json
[
  {
    "id": "chunk-uuid",
    "chunk_index": 0,
    "content": "Chương 1: Giới thiệu\n\nLập trình là...",
    "token_count": 128,
    "page_start": 1,
    "page_end": 1,
    "section_title": "Chương 1: Giới thiệu"
  }
]
```

---

### **GET /api/v1/documents/tags**
Lấy danh sách tags (với số lượng tài liệu)

**Query Params**:
- `workspace_id`: uuid (optional)

**Response**:
```json
[
  {
    "name": "chương-1",
    "count": 5
  },
  {
    "name": "giới-thiệu",
    "count": 3
  }
]
```

---

## 💬 4. Chat & Conversations

### **POST /api/v1/chat/workspaces/{workspace_id}/conversations**
Tạo conversation mới

**Request**:
```json
{
  "title": "Hỏi về Chương 2",
  "scope_tags": ["chương-2"]
}
```

**Response**:
```json
{
  "id": "conversation-uuid",
  "workspace_id": "workspace-uuid",
  "title": "Hỏi về Chương 2",
  "scope_tags": ["chương-2"],
  "created_by": "user-uuid",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": null,
  "message_count": 0
}
```

---

### **GET /api/v1/chat/workspaces/{workspace_id}/conversations**
Lấy danh sách conversations

**Query Params**:
- `limit`: int (default: 50)
- `offset`: int (default: 0)

**Response**:
```json
{
  "items": [
    {
      "id": "conversation-uuid",
      "workspace_id": "workspace-uuid",
      "title": "Hỏi về Chương 2",
      "scope_tags": ["chương-2"],
      "created_by": "user-uuid",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T01:00:00Z",
      "message_count": 10
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### **GET /api/v1/chat/conversations/{conversation_id}**
Lấy chi tiết conversation

**Response**: Tương tự item trong danh sách

---

### **PUT /api/v1/chat/conversations/{conversation_id}**
Cập nhật conversation

**Request**:
```json
{
  "title": "Hỏi về Chương 2 - Updated",
  "scope_tags": ["chương-2", "lý-thuyết"]
}
```

**Response**: Tương tự GET

---

### **DELETE /api/v1/chat/conversations/{conversation_id}**
Xóa conversation

**Query Params**:
- `hard_delete`: boolean (default: false)

**Response**: 204 No Content

---

### **GET /api/v1/chat/conversations/{conversation_id}/messages**
Lấy danh sách messages

**Query Params**:
- `limit`: int (default: 100)
- `before_id`: uuid (optional, for pagination)

**Response**:
```json
{
  "items": [
    {
      "id": "message-uuid",
      "conversation_id": "conversation-uuid",
      "role": "user",
      "content": "Giải thích khái niệm A là gì?",
      "provider": null,
      "model": null,
      "prompt_tokens": null,
      "completion_tokens": null,
      "latency_ms": null,
      "policy_mode": null,
      "best_retrieval_score": null,
      "fallback_used": false,
      "citations": [],
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "message-uuid-2",
      "conversation_id": "conversation-uuid",
      "role": "assistant",
      "content": "Khái niệm A là một khái niệm cơ bản trong lập trình...",
      "provider": "openai",
      "model": "gpt-4",
      "prompt_tokens": 512,
      "completion_tokens": 256,
      "latency_ms": 2500,
      "policy_mode": "balanced",
      "best_retrieval_score": 0.85,
      "fallback_used": false,
      "citations": [
        {
          "id": "citation-uuid",
          "chunk_id": "chunk-uuid",
          "document_id": "document-uuid",
          "document_title": "Slide Chương 2.pdf",
          "score": 0.85,
          "quote": "Khái niệm A là...",
          "page": 15
        }
      ],
      "created_at": "2024-01-01T00:00:05Z"
    }
  ],
  "conversation_id": "conversation-uuid"
}
```

---

### **POST /api/v1/chat/conversations/{conversation_id}/messages**
Gửi message (RAG query)

**Request**:
```json
{
  "content": "Giải thích khái niệm A là gì?",
  "document_ids": null,
  "tags": null,
  "model": "gpt-4",
  "has_image": false
}
```

**Response**:
```json
{
  "user_message": {
    "id": "message-uuid",
    "conversation_id": "conversation-uuid",
    "role": "user",
    "content": "Giải thích khái niệm A là gì?",
    "provider": null,
    "model": null,
    "prompt_tokens": null,
    "completion_tokens": null,
    "latency_ms": null,
    "policy_mode": null,
    "best_retrieval_score": null,
    "fallback_used": false,
    "citations": [],
    "created_at": "2024-01-01T00:00:00Z"
  },
  "assistant_message": {
    "id": "message-uuid-2",
    "conversation_id": "conversation-uuid",
    "role": "assistant",
    "content": "Khái niệm A là một khái niệm cơ bản trong lập trình...\n\n📚 **Nguồn**:\n[1] Slide Chương 2.pdf, Trang 15 (Score: 0.85)\n[2] Giáo trình.pdf, Trang 42 (Score: 0.78)",
    "provider": "openai",
    "model": "gpt-4",
    "prompt_tokens": 512,
    "completion_tokens": 256,
    "latency_ms": 2500,
    "policy_mode": "balanced",
    "best_retrieval_score": 0.85,
    "fallback_used": false,
    "citations": [
      {
        "id": "citation-uuid",
        "chunk_id": "chunk-uuid",
        "document_id": "document-uuid",
        "document_title": "Slide Chương 2.pdf",
        "score": 0.85,
        "quote": "Khái niệm A là một khái niệm cơ bản...",
        "page": 15
      },
      {
        "id": "citation-uuid-2",
        "chunk_id": "chunk-uuid-2",
        "document_id": "document-uuid-2",
        "document_title": "Giáo trình.pdf",
        "score": 0.78,
        "quote": "A có ưu điểm là...",
        "page": 42
      }
    ],
    "context_stats": {
      "chunks_retrieved": 20,
      "chunks_reranked": 5,
      "chunks_used": 5
    },
    "created_at": "2024-01-01T00:00:05Z"
  }
}
```

---

### **POST /api/v1/chat/query**
Stateless RAG query (không lưu lịch sử)

**Request**:
```json
{
  "workspace_id": "workspace-uuid",
  "question": "Tóm tắt chương 3",
  "document_ids": null,
  "tags": ["chương-3"],
  "top_k": 5,
  "model": "gpt-4",
  "has_image": false,
  "rag_only": true
}
```

**Response**:
```json
{
  "answer": "Chương 3 nói về...",
  "citations": [
    {
      "chunk_id": "chunk-uuid",
      "document_id": "document-uuid",
      "document_title": "Slide Chương 3.pdf",
      "content": "Chương 3 giới thiệu về...",
      "score": 0.85,
      "page": 20,
      "quote": "Chương 3 giới thiệu về..."
    }
  ],
  "policy_evaluation": {
    "policy": "balanced",
    "threshold": 0.7,
    "best_score": 0.85,
    "should_answer": true,
    "is_grounded": true,
    "is_fallback": false,
    "disclaimer": null
  },
  "provider": "openai",
  "model": "gpt-4",
  "prompt_tokens": 512,
  "completion_tokens": 256,
  "images": null,
  "is_image_response": false,
  "tool_calls_made": null
}
```

---

## 🎯 5. Background Jobs

### **GET /api/v1/jobs**
Lấy danh sách jobs

**Query Params**:
- `workspace_id`: uuid (required)
- `status`: string (optional: QUEUED, RUNNING, DONE, ERROR)
- `type`: string (optional: OCR, INDEX, CONVERT)
- `limit`: int (default: 50)
- `offset`: int (default: 0)

**Response**:
```json
{
  "jobs": [
    {
      "id": "job-uuid",
      "workspace_id": "workspace-uuid",
      "document_version_id": "version-uuid",
      "type": "INDEX",
      "status": "RUNNING",
      "progress": 75,
      "step": "generating embeddings",
      "error_message": null,
      "config_json": {},
      "started_at": "2024-01-01T00:00:00Z",
      "finished_at": null,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

### **GET /api/v1/jobs/{job_id}**
Lấy chi tiết job

**Response**: Tương tự item trong danh sách

---

## 📊 6. Analytics (Optional - Cấp độ 3)

### **GET /api/v1/analytics/workspaces/{workspace_id}/usage**
Thống kê sử dụng AI

**Query Params**:
- `start_date`: date (optional)
- `end_date`: date (optional)

**Response**:
```json
{
  "total_tokens": 1000000,
  "total_cost_usd": 10.50,
  "by_provider": {
    "openai": {
      "tokens": 500000,
      "cost_usd": 7.50
    },
    "gemini": {
      "tokens": 500000,
      "cost_usd": 3.00
    }
  },
  "by_model": {
    "gpt-4": {
      "tokens": 300000,
      "cost_usd": 6.00
    },
    "gpt-3.5-turbo": {
      "tokens": 200000,
      "cost_usd": 1.50
    },
    "gemini-1.5-pro": {
      "tokens": 500000,
      "cost_usd": 3.00
    }
  }
}
```

---

### **GET /api/v1/analytics/workspaces/{workspace_id}/documents/popular**
Tài liệu được truy cập nhiều nhất

**Query Params**:
- `limit`: int (default: 10)

**Response**:
```json
[
  {
    "document_id": "document-uuid",
    "document_title": "Slide Chương 2.pdf",
    "citation_count": 150,
    "last_cited_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### **GET /api/v1/analytics/workspaces/{workspace_id}/questions/popular**
Câu hỏi phổ biến

**Query Params**:
- `limit`: int (default: 10)

**Response**:
```json
[
  {
    "question": "Giải thích khái niệm A là gì?",
    "count": 25,
    "last_asked_at": "2024-01-01T00:00:00Z"
  }
]
```

---

## 🔧 7. Health & Status

### **GET /api/health**
Health check

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "vector_db": "healthy",
    "celery": "healthy"
  }
}
```

---

## 📝 Notes

### **Authentication**
Tất cả endpoints (trừ `/auth/register`, `/auth/login`, `/health`) đều yêu cầu JWT token trong header:
```
Authorization: Bearer <access_token>
```

### **Error Responses**
```json
{
  "detail": "Error message"
}
```

**HTTP Status Codes**:
- `200`: Success
- `201`: Created
- `204`: No Content
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `409`: Conflict
- `500`: Internal Server Error

### **Pagination**
Các endpoints list đều hỗ trợ pagination với `limit` và `offset`:
```
GET /api/v1/documents?workspace_id=xxx&limit=50&offset=0
```

### **Filtering**
Các endpoints list hỗ trợ filtering:
```
GET /api/v1/documents?workspace_id=xxx&status=READY&tags=chương-1,chương-2
```

---

## 🚀 Quick Start Example

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Register
response = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
    "email": "student@example.com",
    "password": "password123",
    "full_name": "Nguyễn Văn A"
})

# 2. Login
response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
    "email": "student@example.com",
    "password": "password123"
})
token = response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 3. Get workspaces
response = requests.get(f"{BASE_URL}/api/v1/workspaces", headers=headers)
workspace_id = response.json()["workspaces"][0]["id"]

# 4. Upload document (Teacher only)
files = {"file": open("slide.pdf", "rb")}
data = {"workspace_id": workspace_id, "tags": "chương-1"}
response = requests.post(
    f"{BASE_URL}/api/v1/documents/upload",
    headers=headers,
    files=files,
    data=data
)

# 5. Create conversation
response = requests.post(
    f"{BASE_URL}/api/v1/chat/workspaces/{workspace_id}/conversations",
    headers=headers,
    json={"title": "Hỏi về Chương 1"}
)
conversation_id = response.json()["id"]

# 6. Send message (RAG query)
response = requests.post(
    f"{BASE_URL}/api/v1/chat/conversations/{conversation_id}/messages",
    headers=headers,
    json={"content": "Giải thích khái niệm A là gì?"}
)
answer = response.json()["assistant_message"]["content"]
citations = response.json()["assistant_message"]["citations"]

print(f"Answer: {answer}")
print(f"Citations: {citations}")
```

---

**Lưu ý**: API này đã loại bỏ các endpoints không liên quan (CloudCode, OCR, Image generation) để tập trung vào core RAG features phù hợp với đề tài sinh viên.
