# Admin Utilities

Scripts cho admin tasks và system maintenance.

## Scripts

### `check_users.py`
Kiểm tra user accounts trong hệ thống.

```bash
python scripts/admin/check_users.py
```

**Output:**
```
User Accounts:
==============
Total Users: 15
Active: 12
Inactive: 3

Recent Users:
- user@example.com (Active, Last login: 2026-01-20)
- admin@example.com (Active, Last login: 2026-01-19)
```

**Use cases:**
- Audit user accounts
- Check user status
- Monitor user activity
- Verify user permissions

### `check_docs.py`
Kiểm tra documents trong hệ thống.

```bash
python scripts/admin/check_docs.py
```

**Output:**
```
Document Statistics:
===================
Total Documents: 1,234
By Status:
- Processed: 1,100 (89%)
- Processing: 50 (4%)
- Failed: 84 (7%)

By Type:
- PDF: 800
- Images: 300
- Text: 134

Storage Used: 15.5 GB
```

**Use cases:**
- Monitor document processing
- Check storage usage
- Identify failed documents
- System health monitoring

### `requeue_stuck.py`
Requeue stuck background jobs.

```bash
python scripts/admin/requeue_stuck.py
```

**Output:**
```
Checking for stuck jobs...
==========================
Found 5 stuck jobs:
- Job abc-123 (stuck for 2 hours)
- Job def-456 (stuck for 1 hour)
...

Requeuing...
✅ Requeued 5 jobs
✅ Jobs will be retried
```

**Use cases:**
- Fix stuck processing jobs
- Recover from failures
- Maintain job queue health
- Troubleshoot processing issues

## Common Workflows

### Daily Health Check
```bash
# 1. Check users
python scripts/admin/check_users.py

# 2. Check documents
python scripts/admin/check_docs.py

# 3. Check for stuck jobs
python scripts/admin/requeue_stuck.py
```

### Troubleshooting Processing Issues
```bash
# 1. Check document status
python scripts/admin/check_docs.py

# 2. Requeue stuck jobs
python scripts/admin/requeue_stuck.py

# 3. Monitor logs
tail -f ../logs/app.log
```

### User Management
```bash
# Check all users
python scripts/admin/check_users.py

# Check specific user (modify script)
# Add user_id parameter to script
```

## Best Practices

### Regular Monitoring:
- Run check_users.py daily
- Run check_docs.py daily
- Run requeue_stuck.py when issues occur

### Maintenance Schedule:
- **Daily:** Health checks
- **Weekly:** Review failed documents
- **Monthly:** User audit

### Alerts:
- Set up alerts for stuck jobs
- Monitor storage usage
- Track failed document rate

## Troubleshooting

### High Failed Document Rate
```bash
# Check failed documents
python scripts/admin/check_docs.py

# Review logs for errors
tail -f ../logs/app.log | grep ERROR
```

### Stuck Jobs
```bash
# Requeue stuck jobs
python scripts/admin/requeue_stuck.py

# Check Celery workers
celery -A app.queue.celery_app inspect active
```

### Storage Issues
```bash
# Check storage usage
python scripts/admin/check_docs.py

# Clean up old documents if needed
# (implement cleanup script)
```

## Security

- Admin scripts should be run by authorized personnel only
- Protect access to production database
- Log all admin actions
- Review changes before applying

## Related

- [System Architecture](../../../docs/01-SYSTEM-ARCHITECTURE.md)
- [Deployment Guide](../../../docs/04-DEPLOYMENT-GUIDE.md)
- [Database Scripts](../db/README.md)
