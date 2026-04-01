# Database Management Scripts

Scripts để quản lý PostgreSQL database và migrations.

## Scripts

### `reset_db.py`
Reset database về trạng thái ban đầu (xóa tất cả data).

**⚠️ WARNING:** Script này sẽ xóa TẤT CẢ data trong database!

```bash
python scripts/db/reset_db.py
```

**Use cases:**
- Development: Reset để test từ đầu
- Testing: Clean state cho tests
- Troubleshooting: Fix corrupted data

### `ensure_tables.py`
Đảm bảo tất cả tables được tạo đúng schema.

```bash
python scripts/db/ensure_tables.py
```

**Use cases:**
- First-time setup
- After schema changes
- Verify table structure

### `run_migration.py`
Chạy Alembic migrations để update schema.

```bash
python scripts/db/run_migration.py
```

**Use cases:**
- Apply new migrations
- Update database schema
- Version control database

### `fix_db_transaction.py`
Sửa lỗi transactions bị stuck hoặc deadlock.

```bash
python scripts/db/fix_db_transaction.py
```

**Use cases:**
- Fix stuck transactions
- Resolve deadlocks
- Clean up orphaned locks

### `check_table.py`
Kiểm tra cấu trúc và data của tables.

```bash
python scripts/db/check_table.py
```

**Use cases:**
- Verify table structure
- Check data integrity
- Debug schema issues

## Prerequisites

### 1. Database Running
```bash
docker-compose up -d postgres
```

### 2. Environment Variables
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/raganything
```

### 3. Alembic Configured
```bash
# Check alembic.ini exists
ls ../alembic.ini
```

## Common Workflows

### Fresh Setup
```bash
# 1. Reset database
python scripts/db/reset_db.py

# 2. Run migrations
python scripts/db/run_migration.py

# 3. Verify tables
python scripts/db/ensure_tables.py
```

### Schema Update
```bash
# 1. Create migration
cd ..
alembic revision --autogenerate -m "Add new column"

# 2. Run migration
python scripts/db/run_migration.py

# 3. Verify
python scripts/db/check_table.py
```

### Troubleshooting
```bash
# 1. Check tables
python scripts/db/check_table.py

# 2. Fix transactions
python scripts/db/fix_db_transaction.py

# 3. If needed, reset
python scripts/db/reset_db.py
```

## Safety

- Always backup before running reset_db.py
- Test migrations on dev database first
- Use transactions for data modifications
- Keep backups of production data

## Related

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Database Schema](../../../docs/DATABASE.md)
- [Migration Guide](../../../docs/INSTALLATION.md)
