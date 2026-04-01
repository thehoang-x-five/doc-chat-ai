# Memori System Utilities

Scripts để quản lý và maintain Memori memory management system.

## Scripts

### `check_memori.py`
Kiểm tra overall health của Memori system.

```bash
python scripts/memori/check_memori.py
```

**Checks:**
- Database connectivity
- Facts count
- Triples count
- Entities count
- Index health
- Search performance

**Output:**
```
Memori System Health Check
==========================
✅ Database: Connected
✅ Facts: 1,234
✅ Triples: 2,456
✅ Entities: 89
✅ FAISS Index: Healthy
✅ Search: 45ms avg
```

### `check_facts_and_triples.py`
Kiểm tra chi tiết facts và semantic triples.

```bash
python scripts/memori/check_facts_and_triples.py
```

**Output:**
```
Facts Analysis:
- Total: 1,234
- By Type: Facts (800), Preferences (234), Attributes (200)
- Avg Importance: 0.75
- With Triples: 95%

Triples Analysis:
- Total: 2,456
- Valid: 2,400 (98%)
- Invalid: 56 (2%)
- Avg Confidence: 0.82
```

### `extract_triples_from_existing_facts.py`
Extract semantic triples từ facts đã có (migration tool).

```bash
python scripts/memori/extract_triples_from_existing_facts.py
```

**Use cases:**
- Migrate old facts to new triple format
- Backfill triples for existing data
- Rebuild knowledge graph

**Process:**
1. Load all facts without triples
2. Extract triples using LLM
3. Validate triples
4. Save to database

### `validate_triples.py`
Validate tất cả semantic triples trong database.

```bash
python scripts/memori/validate_triples.py
```

**Validation checks:**
- Subject-Predicate-Object format
- Entity references valid
- Confidence scores in range
- No duplicates
- Semantic consistency

**Output:**
```
Triple Validation Report
========================
Total Triples: 2,456
✅ Valid: 2,400 (98%)
❌ Invalid: 56 (2%)

Issues Found:
- Missing subject: 12
- Invalid confidence: 8
- Duplicate triples: 36

Recommendations:
- Remove duplicates
- Fix confidence scores
- Re-extract missing subjects
```

### `resolve_entities.py`
Resolve entity conflicts và duplicates.

```bash
python scripts/memori/resolve_entities.py
```

**Resolves:**
- Duplicate entities (same person, different IDs)
- Name variations (John vs John Smith)
- Merge entity data
- Update references

**Example:**
```
Entity Resolution
=================
Found duplicates:
- "John Smith" (ID: 123)
- "John" (ID: 456)

Merging...
✅ Merged to: "John Smith" (ID: 123)
✅ Updated 45 references
✅ Removed duplicate entity
```

## Memori System Overview

### Architecture:
```
Facts → Semantic Triples → Knowledge Graph
  ↓           ↓                  ↓
FAISS     Validation         Search
```

### Components:
1. **Facts:** Raw memory items (facts, preferences, attributes)
2. **Triples:** Semantic relationships (subject-predicate-object)
3. **Knowledge Graph:** Connected entity relationships
4. **FAISS Index:** Fast semantic search
5. **Validation:** Ensure data quality

## Common Workflows

### Health Check
```bash
# Quick check
python scripts/memori/check_memori.py

# Detailed analysis
python scripts/memori/check_facts_and_triples.py
```

### Data Migration
```bash
# Extract triples from old facts
python scripts/memori/extract_triples_from_existing_facts.py

# Validate results
python scripts/memori/validate_triples.py
```

### Maintenance
```bash
# 1. Check health
python scripts/memori/check_memori.py

# 2. Validate triples
python scripts/memori/validate_triples.py

# 3. Resolve entities
python scripts/memori/resolve_entities.py

# 4. Re-check
python scripts/memori/check_facts_and_triples.py
```

### Troubleshooting
```bash
# Issue: Low search performance
python scripts/memori/check_memori.py
# Check FAISS index health

# Issue: Invalid triples
python scripts/memori/validate_triples.py
# Identify and fix issues

# Issue: Duplicate entities
python scripts/memori/resolve_entities.py
# Merge duplicates
```

## Performance Tips

### FAISS Index:
- Rebuild periodically for optimal performance
- Monitor index size
- Use appropriate index type for data size

### Triple Extraction:
- Batch process for efficiency
- Use caching for repeated extractions
- Monitor LLM costs

### Entity Resolution:
- Run weekly to prevent buildup
- Use fuzzy matching for name variations
- Keep entity aliases updated

## Data Quality

### Best Practices:
1. **Regular Validation:** Run validate_triples.py weekly
2. **Entity Resolution:** Run resolve_entities.py monthly
3. **Health Checks:** Run check_memori.py daily
4. **Backups:** Backup before major operations

### Metrics to Monitor:
- Triple validity rate (target: >95%)
- Entity duplication rate (target: <5%)
- Search performance (target: <100ms)
- Fact coverage (target: >90% with triples)

## Troubleshooting

### Low Triple Validity
```bash
python scripts/memori/validate_triples.py
# Review issues
# Re-extract problematic triples
```

### Slow Search
```bash
python scripts/memori/check_memori.py
# Check index health
# Rebuild FAISS index if needed
```

### Entity Duplicates
```bash
python scripts/memori/resolve_entities.py
# Merge duplicates
# Update references
```

## Related

- [Memori System Documentation](../../../docs/02-MEMORI-SYSTEM.md)
- [System Architecture](../../../docs/01-SYSTEM-ARCHITECTURE.md)
- [API Reference](../../../docs/API_REFERENCE.md)
