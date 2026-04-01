# Server Scripts

Utility và management scripts cho RAG-Anything backend.

## 📁 Cấu trúc

### `db/` - Database Management
Scripts quản lý database, migrations, và data management.

- `reset_db.py` - Reset database về trạng thái ban đầu
- `ensure_tables.py` - Đảm bảo tất cả tables được tạo
- `run_migration.py` - Chạy database migrations
- `fix_db_transaction.py` - Sửa lỗi transactions
- `check_table.py` - Kiểm tra cấu trúc tables

**Sử dụng:**
```bash
cd server
python scripts/db/reset_db.py
python scripts/db/ensure_tables.py
```

### `cloudcode/` - Cloud Code Management
Scripts quản lý Cloud Code accounts (FREE Claude/Gemini).

- `add_cloudcode_account.py` - Thêm Cloud Code account mới
- `check_cloudcode_accounts.py` - Kiểm tra status các accounts
- `test_cloudcode.py` - Test Cloud Code functionality

**Sử dụng:**
```bash
python scripts/cloudcode/add_cloudcode_account.py
python scripts/cloudcode/check_cloudcode_accounts.py
```

### `memori/` - Memori System Utilities
Scripts quản lý và maintain Memori memory system.

- `check_memori.py` - Kiểm tra Memori system health
- `check_facts_and_triples.py` - Kiểm tra facts và semantic triples
- `extract_triples_from_existing_facts.py` - Extract triples từ facts có sẵn
- `validate_triples.py` - Validate semantic triples
- `resolve_entities.py` - Resolve entity conflicts

**Sử dụng:**
```bash
python scripts/memori/check_memori.py
python scripts/memori/validate_triples.py
```

### `debug/` - Debug & Troubleshooting
Scripts để debug và troubleshoot issues.

- `debug_chat.py` - Debug chat functionality
- `debug_permission.py` - Debug permission issues
- `verify_system.py` - Verify system configuration

**Sử dụng:**
```bash
python scripts/debug/verify_system.py
python scripts/debug/debug_chat.py
```

### `admin/` - Admin Utilities
Scripts cho admin tasks và maintenance.

- `check_users.py` - Kiểm tra user accounts
- `check_docs.py` - Kiểm tra documents
- `requeue_stuck.py` - Requeue stuck jobs

**Sử dụng:**
```bash
python scripts/admin/check_users.py
python scripts/admin/requeue_stuck.py
```

## 🚀 Chạy Scripts

Tất cả scripts nên được chạy từ thư mục `server/`:

```bash
cd server
python scripts/<category>/<script_name>.py
```

## 📝 Notes

- Scripts sử dụng environment variables từ `.env`
- Đảm bảo database đang chạy trước khi chạy db scripts
- Một số scripts yêu cầu admin privileges

## 🔧 Development

Khi thêm script mới:
1. Đặt vào thư mục phù hợp
2. Thêm docstring rõ ràng
3. Cập nhật README này
4. Test kỹ trước khi commit
