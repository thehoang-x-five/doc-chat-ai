# Memori Enterprise-Grade Implementation Plan

## Overview

This document tracks the implementation of all 3 phases to bring Memori to enterprise-grade quality.

**Total Estimated Effort**: 9-14 days
**Status**: IN PROGRESS

---

## Phase 1: Critical Issues (High Priority) ⭐⭐⭐

**Estimated**: 4-6 days
**Status**: IN PROGRESS

### 1.1 Temporal Support ✅ STARTED

**Files Modified**:
- ✅ `app/db/models.py` - Added temporal fields (valid_at, invalid_at, expired_at)

**Files to Create**:
- [ ] `app/services/memori/temporal_operations.py` - Temporal logic
- [ ] `app/services/memori/contradiction_detector.py` - Contradiction detection
- [ ] `alembic/versions/xxx_add_temporal_fields.py` - Migration script

**Tasks**:
- [x] Add temporal fields to MemoriKnowledgeGraph model
- [ ] Create temporal_operations module
- [ ] Implement extract_edge_dates() - Extract timestamps from conversation
- [ ] Implement get_edge_contradictions() - Detect contradictions
- [ ] Implement invalidate_contradicted_edges() - Mark edges as expired
- [ ] Create database migration
- [ ] Update MemoriManager to use temporal operations
- [ ] Add tests for temporal operations

**Estimated**: 2-3 days

---

### 1.2 Enhanced Coreference Resolution

**Files to Create**:
- [ ] `app/services/memori/coreference_resolver.py` - Pronoun resolution

**Files to Modify**:
- [ ] `app/services/memori/entity_resolver.py` - Add LLM-based resolution
- [ ] `app/services/memori/manager.py` - Integrate coreference resolution

**Tasks**:
- [ ] Create coreference_resolver module
- [ ] Implement resolve_pronoun() - Resolve pronouns to entities
- [ ] Implement resolve_entity_with_llm() - LLM-based entity resolution
- [ ] Update entity_resolver to use conversation context
- [ ] Integrate into triple extraction pipeline
- [ ] Add tests for coreference resolution

**Estimated**: 2-3 days

---

## Phase 2: Important Issues (Medium Priority) ⭐⭐

**Estimated**: 2-4 days
**Status**: NOT STARTED

### 2.1 Negation & Conditional Handling

**Files to Create**:
- [ ] `app/services/memori/negation_detector.py` - Negation detection

**Files to Modify**:
- [ ] `app/services/memori/manager.py` - Update extraction prompts

**Tasks**:
- [ ] Create negation_detector module
- [ ] Implement detect_negation() - Detect negated facts
- [ ] Implement detect_hypothetical() - Detect hypothetical statements
- [ ] Update triple extraction prompts with negation rules
- [ ] Handle negated facts with invalid_at timestamps
- [ ] Add tests for negation detection

**Estimated**: 1-2 days

---

### 2.2 Predicate Ontology & Normalization

**Files to Create**:
- [ ] `app/services/memori/ontology.py` - Predicate ontology
- [ ] `app/services/memori/predicate_normalizer.py` - Predicate normalization

**Files to Modify**:
- [ ] `app/services/memori/config.py` - Add predicate whitelist

**Tasks**:
- [ ] Define PREDICATE_WHITELIST
- [ ] Create ontology module
- [ ] Implement normalize_predicate() - Normalize predicates
- [ ] Implement validate_predicate() - Validate against whitelist
- [ ] Integrate into triple extraction pipeline
- [ ] Add tests for predicate normalization

**Estimated**: 1-2 days

---

## Phase 3: Nice-to-Have (Low Priority) ⭐

**Estimated**: 3-4 days
**Status**: NOT STARTED

### 3.1 Confidence Gating & Quarantine

**Files to Create**:
- [ ] `app/db/models.py` - Add MemoriQuarantine model
- [ ] `app/services/memori/quarantine.py` - Quarantine logic
- [ ] `alembic/versions/xxx_add_quarantine_table.py` - Migration

**Tasks**:
- [ ] Create MemoriQuarantine model
- [ ] Create quarantine module
- [ ] Implement quarantine_triple() - Add to quarantine
- [ ] Implement review_quarantine() - Review quarantined items
- [ ] Add confidence thresholds
- [ ] Create database migration
- [ ] Add tests for quarantine

**Estimated**: 2-3 days

---

### 3.2 Location Hierarchy

**Files to Create**:
- [ ] `app/services/memori/location_hierarchy.py` - Location hierarchy

**Files to Modify**:
- [ ] `app/services/memori/config.py` - Add location hierarchy data

**Tasks**:
- [ ] Define LOCATION_HIERARCHY
- [ ] Create location_hierarchy module
- [ ] Implement merge_location_hierarchy() - Merge redundant locations
- [ ] Integrate into triple validation
- [ ] Add tests for location hierarchy

**Estimated**: 1 day

---

## Testing Strategy

### Golden Test Suite

**File to Create**:
- [ ] `tests/memori/test_golden_suite.py` - Comprehensive test cases

**Test Categories**:
1. Temporal cases (50 tests)
2. Coreference cases (50 tests)
3. Negation cases (50 tests)
4. Predicate cases (50 tests)
5. Confidence cases (50 tests)
6. Integration cases (50 tests)

**Total**: 300 test cases

---

## Migration Scripts

### Migration 1: Add Temporal Fields
```sql
ALTER TABLE memori_knowledge_graph 
ADD COLUMN valid_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN invalid_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN expired_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_memori_kg_valid_at ON memori_knowledge_graph(valid_at);
CREATE INDEX idx_memori_kg_invalid_at ON memori_knowledge_graph(invalid_at);
CREATE INDEX idx_memori_kg_expired_at ON memori_knowledge_graph(expired_at);
```

### Migration 2: Add Quarantine Table
```sql
CREATE TABLE memori_quarantine (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER REFERENCES memori_entities(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_memori_quarantine_entity ON memori_quarantine(entity_id);
CREATE INDEX idx_memori_quarantine_reviewed ON memori_quarantine(reviewed);
```

---

## Progress Tracking

### Completed ✅
- [x] Database model updates (temporal fields)
- [x] Analysis and planning documents

### In Progress 🔄
- [ ] Temporal operations implementation
- [ ] Coreference resolution implementation

### Not Started ⏳
- [ ] Negation handling
- [ ] Predicate ontology
- [ ] Confidence gating
- [ ] Location hierarchy
- [ ] Golden test suite
- [ ] Database migrations

---

## Success Metrics

### Current Baseline
- Temporal: 0% handled
- Coreference: 30% accuracy (basic aliases only)
- Negation: 0% handled
- Predicate normalization: 0%
- Confidence gating: 0%

### Target After Phase 1
- Temporal: 80% handled ✅
- Coreference: 85% accuracy ✅
- Negation: 0% handled
- Predicate normalization: 0%
- Confidence gating: 0%

### Target After Phase 2
- Temporal: 80% handled ✅
- Coreference: 85% accuracy ✅
- Negation: 75% handled ✅
- Predicate normalization: 90% ✅
- Confidence gating: 0%

### Target After Phase 3 (Complete)
- Temporal: 80% handled ✅
- Coreference: 85% accuracy ✅
- Negation: 75% handled ✅
- Predicate normalization: 90% ✅
- Confidence gating: 95% ✅

---

## Next Steps

1. ✅ Add temporal fields to database model
2. 🔄 Create temporal_operations module
3. ⏳ Implement contradiction detection
4. ⏳ Create coreference_resolver module
5. ⏳ Update entity_resolver with LLM
6. ⏳ Create database migrations
7. ⏳ Implement negation detection
8. ⏳ Create predicate ontology
9. ⏳ Implement confidence gating
10. ⏳ Create golden test suite

---

## Notes

- All implementations follow Graphiti's best practices
- Code is production-ready with proper error handling
- Comprehensive tests for each feature
- Database migrations for schema changes
- Documentation for each module

---

**Last Updated**: 2025-01-19
**Status**: Phase 1 in progress (temporal fields added)
