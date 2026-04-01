# Cloud Code Management Scripts

Scripts để quản lý Cloud Code accounts (FREE Claude & Gemini access).

## Scripts

### `add_cloudcode_account.py`
Thêm Cloud Code account mới vào hệ thống.

```bash
python scripts/cloudcode/add_cloudcode_account.py
```

**Interactive prompts:**
- Email address
- Account name
- Access token
- Refresh token (optional)

**Example:**
```
Enter email: user@gmail.com
Enter name: My Account
Enter access token: ya29.a0...
Enter refresh token (optional): 1//0g...
✅ Account added successfully
```

### `check_cloudcode_accounts.py`
Kiểm tra status và quota của tất cả Cloud Code accounts.

```bash
python scripts/cloudcode/check_cloudcode_accounts.py
```

**Output:**
```
Cloud Code Accounts Status:
==========================

Account: user@gmail.com (My Account)
  Status: Active
  Best Model: claude-3-5-sonnet-20241022
  Quota Used: 45/100 requests
  Last Used: 2026-01-20 10:30:00
  
Total Accounts: 3
Active: 2
Quota Exceeded: 1
```

### `test_cloudcode.py`
Test Cloud Code functionality với sample requests.

```bash
python scripts/cloudcode/test_cloudcode.py
```

**Tests:**
- Account authentication
- Model availability
- Request/response flow
- Quota tracking
- Token refresh

## Cloud Code Overview

Cloud Code provides FREE access to:
- **Claude 3.5 Sonnet** (Anthropic)
- **Gemini 1.5 Pro** (Google)

### How it works:
1. User adds Google account với OAuth
2. System stores access/refresh tokens
3. Requests routed through Cloud Code API
4. Automatic token refresh
5. Quota tracking per account

### Benefits:
- ✅ FREE (no API keys needed)
- ✅ High-quality models
- ✅ Multi-account support
- ✅ Automatic fallback
- ✅ Quota management

## Adding Accounts

### Method 1: OAuth Flow (Recommended)
```bash
# Start server
python start_server.py

# Visit in browser
http://localhost:8000/api/v1/oauth/google

# Follow OAuth flow
# Account automatically added
```

### Method 2: Manual Script
```bash
python scripts/cloudcode/add_cloudcode_account.py
```

**Get tokens:**
1. Visit [Google OAuth Playground](https://developers.google.com/oauthplayground/)
2. Authorize Cloud Code API
3. Copy access & refresh tokens
4. Paste into script

## Managing Accounts

### Check Status
```bash
python scripts/cloudcode/check_cloudcode_accounts.py
```

### Remove Account
```python
# In Python shell
from app.services.cloudcode_provider import get_cloudcode_manager
manager = get_cloudcode_manager()
manager.remove_account("user@gmail.com")
```

### Refresh Tokens
Tokens auto-refresh, but manual refresh:
```python
from app.services.cloudcode_provider import get_cloudcode_manager
manager = get_cloudcode_manager()
await manager.refresh_account_token("user@gmail.com")
```

## Quota Management

### Quota Limits:
- **Claude:** 100 requests/day per account
- **Gemini:** 50 requests/day per account

### Quota Reset:
- Resets daily at midnight UTC
- Tracked per account
- Automatic fallback when exceeded

### Check Quota:
```bash
python scripts/cloudcode/check_cloudcode_accounts.py
```

## Troubleshooting

### Account Not Working
```bash
# Check status
python scripts/cloudcode/check_cloudcode_accounts.py

# Test account
python scripts/cloudcode/test_cloudcode.py
```

### Token Expired
```
❌ Error: Token expired
```
**Solution:** Tokens auto-refresh. If fails, re-add account.

### Quota Exceeded
```
❌ Error: Quota exceeded
```
**Solution:** 
- Wait for daily reset
- Add more accounts
- Use other providers (DeepSeek, Gemini API)

### Model Not Available
```
❌ Error: Model not available
```
**Solution:** Check account has access to model:
```bash
python scripts/cloudcode/check_cloudcode_accounts.py
```

## Best Practices

1. **Multiple Accounts:** Add 3-5 accounts for redundancy
2. **Monitor Quota:** Check daily usage
3. **Rotate Accounts:** System auto-rotates, but monitor
4. **Backup Tokens:** Save refresh tokens securely
5. **Test Regularly:** Run test script weekly

## Security

- Tokens stored encrypted in database
- Never commit tokens to git
- Use environment variables for sensitive data
- Rotate tokens periodically
- Monitor for unauthorized access

## Related

- [Cloud Code Documentation](https://cloud.google.com/code)
- [AI Providers Guide](../../../docs/AI_PROVIDERS.md)
- [System Architecture](../../../docs/01-SYSTEM-ARCHITECTURE.md)
