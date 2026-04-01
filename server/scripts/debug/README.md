# Debug & Troubleshooting Tools

Scripts để debug và troubleshoot issues trong RAG-Anything.

## Scripts

### `debug_chat.py`
Debug chat functionality và RAG pipeline.

```bash
python scripts/debug/debug_chat.py
```

**Features:**
- Test chat endpoints
- Debug RAG retrieval
- Check LLM responses
- Trace conversation flow
- Inspect memory recall

**Output:**
```
Chat Debug Session
==================
Testing chat endpoint...
✅ Endpoint reachable

Testing RAG retrieval...
✅ Retrieved 5 chunks
✅ Relevance scores: [0.85, 0.82, 0.78, 0.75, 0.70]

Testing LLM generation...
✅ Response generated
✅ Response time: 2.3s

Testing memory recall...
✅ Recalled 3 facts
✅ Memory integration: OK
```

**Use cases:**
- Debug chat not responding
- Check RAG retrieval quality
- Verify LLM integration
- Test memory system
- Troubleshoot slow responses

### `debug_permission.py`
Debug permission và authorization issues.

```bash
python scripts/debug/debug_permission.py
```

**Features:**
- Check user permissions
- Verify workspace access
- Test RBAC rules
- Debug auth tokens
- Trace permission checks

**Output:**
```
Permission Debug
================
User: user@example.com
Workspace: abc-123

Permissions:
✅ Can read documents
✅ Can upload documents
❌ Cannot delete workspace
✅ Can chat

Token Status:
✅ Valid
✅ Not expired
✅ Correct scopes
```

**Use cases:**
- Debug access denied errors
- Verify user permissions
- Test RBAC implementation
- Troubleshoot auth issues
- Check token validity

### `verify_system.py`
Comprehensive system verification.

```bash
python scripts/debug/verify_system.py
```

**Checks:**
- Database connectivity
- Redis connectivity
- AI provider status
- Storage accessibility
- Service health
- Configuration validity

**Output:**
```
System Verification
===================

Database:
✅ PostgreSQL: Connected
✅ pgvector: Installed
✅ Tables: All present

Redis:
✅ Connected
✅ Ping: 1ms

AI Providers:
✅ Cloud Code: 3 accounts active
✅ DeepSeek: Available
✅ Gemini: Available
⚠️  Groq: Rate limited
✅ Ollama: Running

Storage:
✅ Documents: Accessible
✅ Objects: Accessible
✅ RAG Storage: Accessible

Services:
✅ FastAPI: Running
✅ Celery: 2 workers active
✅ Health endpoint: OK

Configuration:
✅ Environment variables: Set
✅ API keys: Valid
⚠️  SMTP: Not configured

Overall Status: ✅ HEALTHY (2 warnings)
```

**Use cases:**
- Pre-deployment verification
- System health check
- Troubleshoot startup issues
- Verify configuration
- Monitor service status

## Common Workflows

### Debug Chat Issues

```bash
# 1. Verify system
python scripts/debug/verify_system.py

# 2. Debug chat
python scripts/debug/debug_chat.py

# 3. Check logs
tail -f ../logs/app.log
```

### Debug Permission Issues

```bash
# 1. Debug permissions
python scripts/debug/debug_permission.py

# 2. Check user in database
python scripts/admin/check_users.py

# 3. Verify RBAC rules
# Review app/core/security.py
```

### System Health Check

```bash
# 1. Verify system
python scripts/debug/verify_system.py

# 2. Check database
python scripts/db/check_table.py

# 3. Check services
docker-compose ps
```

### Troubleshooting Slow Performance

```bash
# 1. Verify system
python scripts/debug/verify_system.py

# 2. Debug chat performance
python scripts/debug/debug_chat.py

# 3. Check Redis cache
redis-cli INFO stats

# 4. Check database queries
# Enable query logging in PostgreSQL
```

## Debug Techniques

### Enable Verbose Logging

```python
# In .env file
LOG_LEVEL=DEBUG
```

### Test Individual Components

```python
# Test RAG retrieval only
from app.services.rag_service import RAGService
service = RAGService()
results = service.retrieve("query")
```

### Profile Performance

```python
# Add timing decorators
import time
from functools import wraps

def timing(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        start = time.time()
        result = f(*args, **kwargs)
        end = time.time()
        print(f'{f.__name__} took {end-start:.2f}s')
        return result
    return wrap
```

### Trace Requests

```bash
# Enable request logging
# Check middleware/logging.py
```

## Troubleshooting Guide

### Chat Not Responding

**Symptoms:**
- Timeout errors
- No response
- Slow responses

**Debug steps:**
```bash
# 1. Verify system
python scripts/debug/verify_system.py

# 2. Check AI providers
# Look for provider errors

# 3. Debug chat
python scripts/debug/debug_chat.py

# 4. Check logs
tail -f ../logs/app.log | grep ERROR
```

### Permission Denied

**Symptoms:**
- 403 errors
- Access denied
- Unauthorized

**Debug steps:**
```bash
# 1. Debug permissions
python scripts/debug/debug_permission.py

# 2. Check token
# Verify JWT token validity

# 3. Check user roles
python scripts/admin/check_users.py
```

### Database Connection Failed

**Symptoms:**
- Connection refused
- Timeout
- Cannot connect

**Debug steps:**
```bash
# 1. Verify system
python scripts/debug/verify_system.py

# 2. Check database
docker-compose ps postgres

# 3. Test connection
psql -h localhost -U user -d raganything
```

### AI Provider Errors

**Symptoms:**
- Model not available
- Quota exceeded
- API errors

**Debug steps:**
```bash
# 1. Verify system
python scripts/debug/verify_system.py

# 2. Check providers
python scripts/cloudcode/check_cloudcode_accounts.py

# 3. Test provider
# Use provider test scripts
```

## Best Practices

### Regular Checks:
- Run verify_system.py daily
- Monitor logs continuously
- Test critical paths regularly

### Debug Workflow:
1. Reproduce issue
2. Run verify_system.py
3. Run specific debug script
4. Check logs
5. Fix issue
6. Verify fix

### Logging:
- Use structured logging
- Include context in logs
- Set appropriate log levels
- Rotate logs regularly

## Related

- [System Architecture](../../../docs/01-SYSTEM-ARCHITECTURE.md)
- [Performance Optimization](../../../docs/03-PERFORMANCE-OPTIMIZATION.md)
- [Admin Scripts](../admin/README.md)
- [Database Scripts](../db/README.md)
