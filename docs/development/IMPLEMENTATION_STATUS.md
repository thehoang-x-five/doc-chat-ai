# Memori Enterprise-Grade Implementation Status

## Summary

Đã bắt đầu implement **Phase 1: Critical Issues** để nâng cấp Memori lên enterprise-grade.

**Total Progress**: 15% (2/14 days estimated)

---

## ✅ Completed (Phase 1.1 - Temporal Support Foundation)

### 1. Database Schema Updates

**File**: `app/db/models.py`

Added temporal fields to `MemoriKnowledgeGraph`:
```python
# Temporal fields (Graphiti-inspired bi-temporal model)
valid_at: Optional[datetime]  # When fact became true in reality
invalid_at: Optional[datetime]  # When fact stopped being true
expired_at: Optional[datetime]  # When invalidated by contradiction
```

**Impact**: Enables temporal tracking of all knowledge graph triples.

---

### 2. Temporal Operations Module

**File**: `app/services/memori/temporal_operations.py`

Implemented 3 core functions:

#### `extract_edge_dates()`
Extracts temporal information from conversation:
```python
# Example
User: "Trước đây tôi sống ở Hà Nội, từ tháng 6 chuyển về Huế"

Edge: "Tài Thế lives_in Hà Nội"
→ valid_at=None, invalid_at=2024-06-01

Edge: "Tài Thế lives_in Huế"  
→ valid_at=2024-06-01, invalid_at=None
```

#### `get_edge_contradictions()`
Detects contradictions between new and existing edges:
```python
# Example
New: "Tài Thế lives_in Huế"
Existing: ["Tài Thế lives_in Hà Nội", "Tài Thế likes Python"]

→ Returns: ["Tài Thế lives_in Hà Nội"]  # Contradicted
```

#### `invalidate_contradicted_edges()`
Marks contradicted edges as expired in database:
```python
# Sets expired_at timestamp on contradicted edges
```

**Impact**: Core temporal logic for handling contradictions and versioning.

---

### 3. Planning Documents

**Files Created**:
1. `GRAPHITI_ANALYSIS_AND_IMPROVEMENTS.md` - Detailed Graphiti analysis
2. `MEMORI_REMAINING_ISSUES_AND_SOLUTIONS.md` - Issues and solutions
3. `IMPLEMENTATION_PLAN.md` - Detailed implementation roadmap

**Impact**: Clear roadmap for remaining work.

---

## 🔄 In Progress

### Database Migration

**Need to create**: `alembic/versions/xxx_add_temporal_fields.py`

```sql
-- Migration script
ALTER TABLE memori_knowledge_graph 
ADD COLUMN valid_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN invalid_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN expired_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_memori_kg_valid_at ON memori_knowledge_graph(valid_at);
CREATE INDEX idx_memori_kg_invalid_at ON memori_knowledge_graph(invalid_at);
CREATE INDEX idx_memori_kg_expired_at ON memori_knowledge_graph(expired_at);
```

---

## ⏳ Remaining Work

### Phase 1.1: Temporal Support (Remaining)

**Estimated**: 1-2 days

**Tasks**:
1. [ ] Integrate temporal_operations into MemoriManager
2. [ ] Update `_extract_triples_from_facts()` to extract dates
3. [ ] Update `add_semantic_triples()` to detect contradictions
4. [ ] Create database migration script
5. [ ] Add tests for temporal operations
6. [ ] Update API to expose temporal data

**Integration Example**:
```python
# In manager.py _extract_triples_from_facts()

# After extracting triples
for triple in all_triples:
    # Extract temporal dates
    valid_at, invalid_at = await extract_edge_dates(
        rag_service,
        triple,
        facts,
        datetime.utcnow(),
    )
    triple.valid_at = valid_at
    triple.invalid_at = invalid_at

# Before adding to database
# Check for contradictions
existing_edges = await get_existing_edges(entity_id)
for new_triple in all_triples:
    contradicted = await get_edge_contradictions(
        rag_service,
        new_triple,
        existing_edges,
    )
    if contradicted:
        await invalidate_contradicted_edges(
            session,
            contradicted,
            datetime.utcnow(),
        )
```

---

### Phase 1.2: Enhanced Coreference Resolution

**Estimated**: 2-3 days

**Files to Create**:
1. `app/services/memori/coreference_resolver.py`

**Key Functions**:
```python
async def resolve_pronoun(
    pronoun: str,
    conversation_context: List[str],
    existing_entities: List[str],
) -> Optional[str]:
    """
    Resolve pronoun to actual entity.
    
    Example:
    User: "Tôi là Tài Thế"
    User: "Nó rất thông minh"
    
    resolve_pronoun("nó", context, ["Tài Thế"])
    → Returns: "Tài Thế"
    """

async def resolve_entity_with_llm(
    extracted_entity: str,
    existing_entities: List[str],
    conversation_context: List[str],
) -> Optional[str]:
    """
    Use LLM to resolve entity against existing entities.
    
    Example:
    resolve_entity_with_llm("ảnh", ["Tài Thế", "Khanh"], context)
    → Returns: "Tài Thế" (if context indicates "ảnh" refers to Tài Thế)
    """
```

---

### Phase 2: Important Issues

**Estimated**: 2-4 days

**Components**:
1. Negation & Conditional Handling (1-2 days)
2. Predicate Ontology & Normalization (1-2 days)

---

### Phase 3: Nice-to-Have

**Estimated**: 3-4 days

**Components**:
1. Confidence Gating & Quarantine (2-3 days)
2. Location Hierarchy (1 day)

---

## How to Continue Implementation

### Step 1: Complete Phase 1.1 (Temporal Support)

1. **Create migration script**:
```bash
cd RAG-Anything/server
alembic revision -m "add_temporal_fields_to_knowledge_graph"
# Edit the generated file with the SQL above
alembic upgrade head
```

2. **Integrate into MemoriManager**:
```python
# In app/services/memori/manager.py

from app.services.memori.temporal_operations import (
    extract_edge_dates,
    get_edge_contradictions,
    invalidate_contradicted_edges,
)

# In _extract_triples_from_facts()
# After extracting triples, before validation
for triple in all_triples:
    valid_at, invalid_at = await extract_edge_dates(
        rag_service,
        triple,
        facts,
        datetime.utcnow(),
    )
    # Store in triple object (need to update SemanticTriple struct)
    triple.valid_at = valid_at
    triple.invalid_at = invalid_at

# In add_semantic_triples()
# Before adding new triples
for new_triple in triples:
    # Get existing edges for same subject
    existing_edges = await self.get_knowledge_graph(entity_id)
    
    # Check contradictions
    contradicted = await get_edge_contradictions(
        rag_service,
        new_triple,
        existing_edges,
    )
    
    # Invalidate contradicted edges
    if contradicted:
        await invalidate_contradicted_edges(
            self.session,
            contradicted,
            datetime.utcnow(),
        )
```

3. **Update SemanticTriple struct**:
```python
# In app/services/memori/structs.py

class SemanticTriple(BaseModel):
    subject_name: str
    subject_type: Optional[str] = None
    predicate: str
    object_name: str
    object_type: Optional[str] = None
    
    # Add temporal fields
    valid_at: Optional[datetime] = None
    invalid_at: Optional[datetime] = None
    confidence: float = 1.0
```

4. **Add tests**:
```python
# tests/memori/test_temporal_operations.py

async def test_extract_edge_dates():
    """Test temporal date extraction."""
    edge = SemanticTriple(
        subject_name="Tài Thế",
        predicate="lives_in",
        object_name="Hà Nội",
    )
    facts = ["Trước đây tôi sống ở Hà Nội, từ tháng 6 chuyển về Huế"]
    
    valid_at, invalid_at = await extract_edge_dates(
        rag_service,
        edge,
        facts,
        datetime(2024, 7, 1),
    )
    
    assert invalid_at is not None
    assert invalid_at.month == 6

async def test_get_edge_contradictions():
    """Test contradiction detection."""
    new_edge = SemanticTriple(
        subject_name="Tài Thế",
        predicate="lives_in",
        object_name="Huế",
    )
    existing = [
        SemanticTriple(
            subject_name="Tài Thế",
            predicate="lives_in",
            object_name="Hà Nội",
        )
    ]
    
    contradicted = await get_edge_contradictions(
        rag_service,
        new_edge,
        existing,
    )
    
    assert len(contradicted) == 1
    assert contradicted[0].object_name == "Hà Nội"
```

---

### Step 2: Implement Phase 1.2 (Coreference Resolution)

Follow the pattern from `temporal_operations.py`:
1. Create `coreference_resolver.py`
2. Implement LLM-based pronoun resolution
3. Integrate into entity extraction pipeline
4. Add tests

---

### Step 3: Continue with Phase 2 and 3

Follow the detailed plan in `IMPLEMENTATION_PLAN.md`.

---

## Testing the Implementation

### Manual Testing

```bash
cd RAG-Anything/server

# Test temporal extraction
python -c "
import asyncio
from app.services.memori.temporal_operations import extract_edge_dates
from app.services.memori.structs import SemanticTriple
from app.services.rag_service import RAGService
from app.db.session import AsyncSessionLocal
from datetime import datetime

async def test():
    async with AsyncSessionLocal() as session:
        rag = RAGService(session, workspace=None)
        edge = SemanticTriple(
            subject_name='Tài Thế',
            predicate='lives_in',
            object_name='Hà Nội',
        )
        facts = ['Trước đây tôi sống ở Hà Nội, từ tháng 6 chuyển về Huế']
        
        valid_at, invalid_at = await extract_edge_dates(
            rag,
            edge,
            facts,
            datetime.utcnow(),
        )
        
        print(f'valid_at: {valid_at}')
        print(f'invalid_at: {invalid_at}')

asyncio.run(test())
"
```

---

## Success Metrics

### Current Status (After Phase 1.1 Foundation)
- ✅ Temporal fields added to database
- ✅ Temporal operations module created
- ✅ Contradiction detection implemented
- ⏳ Integration pending
- ⏳ Migration pending
- ⏳ Tests pending

### After Complete Phase 1
- ✅ Temporal: 80% handled
- ✅ Coreference: 85% accuracy
- ⏳ Negation: 0% handled
- ⏳ Predicate normalization: 0%
- ⏳ Confidence gating: 0%

---

## Estimated Timeline

- **Week 1**: Complete Phase 1 (Temporal + Coreference)
  - Days 1-3: Finish temporal integration + tests
  - Days 4-6: Implement coreference resolution

- **Week 2**: Complete Phase 2 (Negation + Ontology)
  - Days 1-2: Negation handling
  - Days 3-4: Predicate ontology

- **Week 3**: Complete Phase 3 (Confidence + Location)
  - Days 1-3: Confidence gating
  - Day 4: Location hierarchy
  - Day 5: Final testing and documentation

---

## Next Immediate Steps

1. ✅ Database schema updated
2. ✅ Temporal operations module created
3. 🔄 Create database migration
4. 🔄 Update SemanticTriple struct
5. 🔄 Integrate into MemoriManager
6. ⏳ Add tests
7. ⏳ Test with real data
8. ⏳ Continue with coreference resolution

---

## Conclusion

Foundation for temporal support is complete. The core logic is implemented and ready for integration. 

**Next Priority**: 
1. Create database migration
2. Integrate temporal operations into MemoriManager
3. Add comprehensive tests

**Estimated Time to Complete Phase 1**: 3-4 more days

---

**Last Updated**: 2025-01-19
**Status**: Phase 1.1 foundation complete, integration pending
