# Graphiti Analysis & Improvements for Memori

## Executive Summary

Sau khi phân tích chi tiết dự án **Graphiti** (Zep's Temporal Knowledge Graph framework), tôi đã tìm ra nhiều tính năng và cách tiếp cận production-grade mà chúng ta có thể học hỏi và áp dụng vào Memori.

## 1. Temporal Knowledge Graph - Giải pháp cho Contradictions ⭐⭐⭐

### Vấn đề hiện tại của Memori
```
❌ "trước đây sống ở Hà Nội" vs "hiện tại sống ở Huế" → không biết cái nào đúng
❌ "thích Python" → "không thích Python nữa" → mâu thuẫn
❌ Không có timestamp → không biết fact nào mới hơn
```

### Giải pháp của Graphiti: Bi-Temporal Model

Graphiti sử dụng **bi-temporal data model** với 3 timestamps:

```python
class EntityEdge(Edge):
    created_at: datetime  # Khi edge được tạo trong hệ thống
    valid_at: datetime | None  # Khi fact BẮT ĐẦU đúng trong thực tế
    invalid_at: datetime | None  # Khi fact KHÔNG CÒN đúng trong thực tế
    expired_at: datetime | None  # Khi edge bị invalidate bởi contradiction
```

**Ví dụ thực tế**:
```python
# Edge 1: User sống ở Hà Nội
{
    "fact": "Tài Thế lives_in Hà Nội",
    "created_at": "2024-01-01",  # Khi add vào DB
    "valid_at": "2020-01-01",    # Bắt đầu sống từ 2020
    "invalid_at": "2024-06-01",  # Chuyển đi vào tháng 6/2024
    "expired_at": None
}

# Edge 2: User sống ở Huế (mới hơn)
{
    "fact": "Tài Thế lives_in Huế",
    "created_at": "2024-06-15",
    "valid_at": "2024-06-01",    # Bắt đầu sống từ tháng 6
    "invalid_at": None,          # Vẫn đang sống
    "expired_at": None
}
```

### Contradiction Detection với LLM

Graphiti sử dụng LLM để detect contradictions:

```python
async def get_edge_contradictions(
    llm_client: LLMClient,
    new_edge: EntityEdge,
    existing_edges: list[EntityEdge],
) -> list[EntityEdge]:
    """
    LLM phân tích xem new_edge có contradict với existing_edges không.
    Trả về list các edges bị contradict.
    """
    context = {
        'new_edge': {'fact': new_edge.fact},
        'existing_edges': [
            {'id': i, 'fact': edge.fact} 
            for i, edge in enumerate(existing_edges)
        ],
    }
    
    llm_response = await llm_client.generate_response(
        prompt_library.invalidate_edges.v2(context),
        response_model=InvalidatedEdges,
    )
    
    contradicted_facts: list[int] = llm_response.get('contradicted_facts', [])
    return [existing_edges[i] for i in contradicted_facts]
```

**Prompt template**:
```
Based on the provided EXISTING FACTS and a NEW FACT, determine which existing facts 
the new fact contradicts.

<EXISTING FACTS>
0. Tài Thế lives_in Hà Nội
1. Tài Thế likes Python
</EXISTING FACTS>

<NEW FACT>
Tài Thế lives_in Huế
</NEW FACT>

Return: {"contradicted_facts": [0]}  # Fact 0 bị contradict
```

### Temporal Edge Extraction

Graphiti extract timestamps từ conversation:

```python
async def extract_edge_dates(
    llm_client: LLMClient,
    edge: EntityEdge,
    current_episode: EpisodicNode,
    previous_episodes: list[EpisodicNode],
) -> tuple[datetime | None, datetime | None]:
    """
    Extract valid_at và invalid_at từ conversation context.
    """
    context = {
        'edge_fact': edge.fact,
        'current_episode': current_episode.content,
        'previous_episodes': [ep.content for ep in previous_episodes],
        'reference_timestamp': current_episode.valid_at.isoformat(),
    }
    
    llm_response = await llm_client.generate_response(
        prompt_library.extract_edge_dates.v1(context),
        response_model=EdgeDates,
    )
    
    return llm_response.get('valid_at'), llm_response.get('invalid_at')
```

**Ví dụ**:
```
User: "Trước đây tôi sống ở Hà Nội, nhưng từ tháng 6 năm nay tôi chuyển về Huế"

LLM extract:
- Edge 1: lives_in Hà Nội
  - valid_at: (inferred from "trước đây")
  - invalid_at: 2024-06-01
  
- Edge 2: lives_in Huế
  - valid_at: 2024-06-01
  - invalid_at: None
```

## 2. Entity Resolution - Giải pháp cho Coreference ⭐⭐⭐

### Vấn đề hiện tại
```
❌ "nó", "ảnh", "cậu ấy", "ông đó" → không biết map vào entity nào
❌ "tôi", "mình", "user" → 3 entities riêng biệt
```

### Giải pháp của Graphiti: Semantic Deduplication

Graphiti có **2-phase entity resolution**:

#### Phase 1: In-Memory Deduplication (Fast)

```python
async def dedupe_nodes_bulk(
    clients: GraphitiClients,
    extracted_nodes_bulk: list[list[EntityNode]],
    episode_context: list[tuple[EpisodicNode, list[EpisodicNode]]],
    entity_types: dict[str, type[BaseModel]] | None,
) -> tuple[dict[str, list[EntityNode]], dict[str, str]]:
    """
    Dedupe extracted nodes trong memory trước khi save vào DB.
    Sử dụng LLM để detect duplicates.
    """
    # Group nodes by episode
    nodes_by_episode: dict[str, list[EntityNode]] = {}
    uuid_map: dict[str, str] = {}  # old_uuid -> canonical_uuid
    
    for episode, _ in episode_context:
        nodes = extracted_nodes_bulk[episode.uuid]
        
        # LLM dedupe
        dedupe_results = await llm_client.generate_response(
            prompt_library.dedupe_nodes.nodes(context),
            response_model=NodeResolutions,
        )
        
        # Apply deduplication
        for resolution in dedupe_results.entity_resolutions:
            if resolution.duplicate_idx != -1:
                # Map to canonical entity
                canonical_uuid = nodes[resolution.duplicate_idx].uuid
                uuid_map[nodes[resolution.id].uuid] = canonical_uuid
    
    return nodes_by_episode, uuid_map
```

#### Phase 2: Graph-Based Resolution (Accurate)

```python
async def resolve_extracted_nodes(
    clients: GraphitiClients,
    extracted_nodes: list[EntityNode],
    episode: EpisodicNode,
    previous_episodes: list[EpisodicNode],
    entity_types: dict[str, type[BaseModel]] | None,
) -> tuple[list[EntityNode], dict[str, str], list[tuple[EntityNode, EntityNode]]]:
    """
    Resolve extracted nodes against existing graph.
    """
    # Search for similar nodes in graph
    existing_nodes = await search_similar_nodes(
        clients.driver,
        extracted_nodes,
        episode.group_id,
    )
    
    # LLM dedupe against existing
    for extracted_node in extracted_nodes:
        context = {
            'extracted_node': extracted_node,
            'existing_nodes': existing_nodes,
            'episode_content': episode.content,
            'previous_episodes': previous_episodes,
        }
        
        resolution = await llm_client.generate_response(
            prompt_library.dedupe_nodes.node(context),
            response_model=NodeResolutions,
        )
        
        if resolution.duplicate_idx != -1:
            # Merge with existing node
            canonical_node = existing_nodes[resolution.duplicate_idx]
            uuid_map[extracted_node.uuid] = canonical_node.uuid
    
    return resolved_nodes, uuid_map, duplicates
```

**Prompt template**:
```
<NEW ENTITY>
{
    "id": 0,
    "name": "nó",
    "entity_type": ["person"]
}
</NEW ENTITY>

<EXISTING ENTITIES>
[
    {"idx": 0, "name": "Tài Thế", "entity_types": ["person"]},
    {"idx": 1, "name": "Khanh", "entity_types": ["person"]}
]
</EXISTING ENTITIES>

<PREVIOUS MESSAGES>
User: "Tôi là Tài Thế"
User: "Nó rất thông minh"  # "nó" refers to Tài Thế
</PREVIOUS MESSAGES>

Determine if NEW ENTITY is a duplicate of any EXISTING ENTITIES.

Response: {
    "entity_resolutions": [{
        "id": 0,
        "name": "Tài Thế",
        "duplicate_idx": 0,  # Maps to "Tài Thế"
        "duplicates": [0]
    }]
}
```

## 3. Negation & Conditional Handling ⭐⭐

### Vấn đề hiện tại
```
❌ "không sống ở Huế" → lưu thành "lives_in Huế"
❌ "ước gì tôi giàu" → lưu thành "is rich"
```

### Giải pháp của Graphiti: Context-Aware Extraction

Graphiti có **explicit instructions** trong prompts:

```python
def extract_message(context: dict[str, Any]) -> list[Message]:
    user_prompt = f"""
    Instructions:
    
    1. Extract entities that are **explicitly or implicitly** mentioned.
    
    2. **Negation Handling**:
       - Do NOT extract facts that are negated (e.g., "không sống ở Huế")
       - Do NOT extract hypothetical or conditional statements (e.g., "ước gì...")
    
    3. **Temporal Information**:
       - Extract temporal context (e.g., "trước đây", "hiện tại")
       - These will be used to set valid_at/invalid_at timestamps
    
    4. **Sarcasm Detection**:
       - Use conversation context to detect sarcasm
       - Mark uncertain extractions with lower confidence
    
    <CURRENT MESSAGE>
    {context['episode_content']}
    </CURRENT MESSAGE>
    
    <PREVIOUS MESSAGES>
    {context['previous_episodes']}
    </PREVIOUS MESSAGES>
    """
```

**Ví dụ**:
```
User: "Tôi không sống ở Huế nữa"

Graphiti extract:
- Edge: lives_in Huế
  - valid_at: (previous date)
  - invalid_at: (current date)  # ← Negation được handle bằng invalid_at!
```

## 4. Predicate Ontology & Schema Validation ⭐⭐

### Vấn đề hiện tại
```
❌ "likes_to_watch", "is_kinda", "sorta_likes" → predicates lạ, không chuẩn
❌ Không có whitelist → graph loãng, khó query
```

### Giải pháp của Graphiti: Custom Entity & Edge Types

Graphiti cho phép define **custom schemas** với Pydantic:

```python
from pydantic import BaseModel, Field

# Custom Entity Type
class PersonEntity(BaseModel):
    age: int | None = Field(None, description="Person's age")
    occupation: str | None = Field(None, description="Person's occupation")
    location: str | None = Field(None, description="Current location")

# Custom Edge Type
class WorksAtEdge(BaseModel):
    position: str = Field(description="Job position")
    start_date: datetime | None = Field(None, description="Start date")
    end_date: datetime | None = Field(None, description="End date")

# Register types
entity_types = {
    "Person": PersonEntity,
    "Organization": OrganizationEntity,
}

edge_types = {
    "works_at": WorksAtEdge,
    "lives_in": LivesInEdge,
}

# Use in Graphiti
graphiti = Graphiti(...)
await graphiti.add_episode(
    content="Tài Thế works at Google as a Software Engineer",
    entity_types=entity_types,
    edge_types=edge_types,
)
```

**LLM sẽ extract theo schema**:
```json
{
    "entities": [
        {
            "name": "Tài Thế",
            "type": "Person",
            "attributes": {
                "occupation": "Software Engineer"
            }
        },
        {
            "name": "Google",
            "type": "Organization"
        }
    ],
    "edges": [
        {
            "source": "Tài Thế",
            "predicate": "works_at",
            "target": "Google",
            "attributes": {
                "position": "Software Engineer",
                "start_date": "2024-01-01"
            }
        }
    ]
}
```

### Predicate Normalization

Graphiti có **edge_type_map** để normalize predicates:

```python
edge_type_map = {
    ("Person", "Organization"): ["works_at", "worked_at", "employed_by"],
    ("Person", "Location"): ["lives_in", "resides_in", "located_in"],
}

# LLM sẽ chỉ extract predicates trong whitelist
# "likes_to_watch" → không có trong whitelist → ignore hoặc convert to attribute
```

## 5. Confidence Gating & Quarantine ⭐⭐

### Vấn đề hiện tại
```
❌ LLM extract sai → lưu luôn vào DB → khó fix
❌ Không có confidence score → không biết fact nào đáng tin
```

### Giải pháp của Graphiti: Structured Output với Confidence

Graphiti sử dụng **Pydantic models** cho structured output:

```python
class ExtractedEntity(BaseModel):
    name: str = Field(..., description='Name of the extracted entity')
    entity_type_id: int = Field(description='ID of the classified entity type')
    confidence: float = Field(ge=0.0, le=1.0, description='Confidence score')

class ExtractedEntities(BaseModel):
    extracted_entities: list[ExtractedEntity]

# LLM response
llm_response = await llm_client.generate_response(
    prompt,
    response_model=ExtractedEntities,  # ← Structured output
)

# Filter by confidence
high_confidence_entities = [
    e for e in llm_response.extracted_entities 
    if e.confidence >= 0.8
]

low_confidence_entities = [
    e for e in llm_response.extracted_entities 
    if e.confidence < 0.8
]

# Quarantine low confidence
await quarantine_entities(low_confidence_entities)
```

## 6. Saga System - Giải pháp cho Sequential Episodes ⭐

### Vấn đề hiện tại
```
❌ Không có cách group related episodes
❌ Không biết episode nào liên quan đến nhau
```

### Giải pháp của Graphiti: Saga Nodes

Graphiti có **Saga system** để group related episodes:

```python
class SagaNode(Node):
    """
    A saga groups related episodes together.
    Example: "User onboarding", "Project X development"
    """
    name: str  # Saga name
    
# Create saga
saga = await graphiti._get_or_create_saga(
    saga_name="User Onboarding",
    group_id="user_123",
    now=datetime.utcnow(),
)

# Add episodes to saga
await graphiti.add_episode(
    content="User signed up",
    saga=saga,  # ← Link to saga
)

await graphiti.add_episode(
    content="User completed profile",
    saga=saga,  # ← Same saga
)

# Query episodes in saga
episodes = await graphiti.retrieve_episodes(
    saga="User Onboarding",
    last_n=10,
)
```

**Graph structure**:
```
Saga: "User Onboarding"
  ├─ HAS_EPISODE → Episode 1: "User signed up"
  │                  └─ NEXT_EPISODE → Episode 2: "User completed profile"
  │                                      └─ NEXT_EPISODE → Episode 3: "User verified email"
  └─ ...
```

## 7. Hybrid Search với Cross-Encoder Reranking ⭐⭐⭐

### Vấn đề hiện tại
```
❌ Chỉ có vector search → miss exact matches
❌ Không có reranking → kết quả không chính xác
```

### Giải pháp của Graphiti: 3-Stage Retrieval

```python
# Stage 1: Hybrid Search (Vector + BM25 + Graph)
search_results = await search(
    graphiti,
    query="What does the user like?",
    config=SearchConfig(
        semantic_weight=0.4,  # Vector search
        bm25_weight=0.3,      # Keyword search
        graph_weight=0.3,     # Graph traversal
    ),
    limit=20,  # Get top 20 candidates
)

# Stage 2: Cross-Encoder Reranking
reranked_results = await cross_encoder.rerank(
    query="What does the user like?",
    candidates=search_results,
    top_k=5,  # Return top 5
)

# Stage 3: Graph Distance Filtering
final_results = await filter_by_graph_distance(
    reranked_results,
    max_hops=2,  # Only include nodes within 2 hops
)
```

## 8. Bulk Operations & Performance ⭐⭐

### Vấn đề hiện tại
```
❌ Add facts one-by-one → slow
❌ Không có batch processing
```

### Giải pháp của Graphiti: Bulk Ingestion

```python
# Bulk add episodes
episodes = [
    RawEpisode(content="Episode 1", ...),
    RawEpisode(content="Episode 2", ...),
    RawEpisode(content="Episode 3", ...),
]

results = await graphiti.add_episode_bulk(
    episodes=episodes,
    parallel=True,  # Process in parallel
)

# Bulk operations
await add_nodes_and_edges_bulk(
    driver,
    episodes,
    episodic_edges,
    nodes,
    entity_edges,
    embedder,
)
```

**Performance optimizations**:
- Parallel LLM calls với `semaphore_gather()`
- Batch database operations
- In-memory deduplication trước khi save DB
- Configurable concurrency limit

## Đề xuất Implementation cho Memori

### Phase 1: Temporal Support (High Priority) ⭐⭐⭐

**Files to create/modify**:
1. `app/db/models.py` - Add temporal fields
2. `app/services/memori/temporal_operations.py` - Contradiction detection
3. `app/services/memori/manager.py` - Integrate temporal logic

**Changes**:
```python
# 1. Add temporal fields to MemoriKnowledgeGraph
class MemoriKnowledgeGraph(Base):
    # ... existing fields ...
    valid_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    invalid_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    expired_at: datetime | None = Column(DateTime(timezone=True), nullable=True)

# 2. Extract timestamps from facts
async def extract_edge_dates(
    rag_service: RAGService,
    edge: SemanticTriple,
    facts: List[str],
) -> tuple[datetime | None, datetime | None]:
    """Extract valid_at and invalid_at from conversation context."""
    prompt = f"""
    Given the fact: "{edge.subject_name} {edge.predicate} {edge.object_name}"
    And conversation: {facts}
    
    Extract:
    - valid_at: When did this fact become true?
    - invalid_at: When did this fact stop being true?
    
    Return JSON: {{"valid_at": "ISO date or null", "invalid_at": "ISO date or null"}}
    """
    # ... LLM call ...

# 3. Detect contradictions
async def get_edge_contradictions(
    rag_service: RAGService,
    new_edge: SemanticTriple,
    existing_edges: List[SemanticTriple],
) -> List[SemanticTriple]:
    """Detect which existing edges contradict the new edge."""
    prompt = f"""
    NEW FACT: {new_edge.subject_name} {new_edge.predicate} {new_edge.object_name}
    
    EXISTING FACTS:
    {[f"{i}. {e.subject_name} {e.predicate} {e.object_name}" for i, e in enumerate(existing_edges)]}
    
    Which existing facts does the NEW FACT contradict?
    Return JSON: {{"contradicted_facts": [0, 2, ...]}}
    """
    # ... LLM call ...
```

### Phase 2: Enhanced Entity Resolution (High Priority) ⭐⭐⭐

**Files to create/modify**:
1. `app/services/memori/entity_resolver.py` - Enhance with LLM
2. `app/services/memori/manager.py` - Integrate resolution

**Changes**:
```python
# Enhanced entity resolution with LLM
async def resolve_entity_with_llm(
    rag_service: RAGService,
    extracted_entity: str,
    existing_entities: List[str],
    conversation_context: List[str],
) -> Optional[str]:
    """
    Use LLM to resolve entity against existing entities.
    Returns canonical entity name if duplicate found.
    """
    prompt = f"""
    NEW ENTITY: "{extracted_entity}"
    
    EXISTING ENTITIES: {existing_entities}
    
    CONVERSATION CONTEXT:
    {conversation_context}
    
    Is NEW ENTITY a duplicate of any EXISTING ENTITIES?
    Consider:
    - Pronouns (nó, ảnh, cậu ấy) referring to named entities
    - Aliases (tôi, mình, user)
    - Semantic equivalence
    
    Return JSON: {{
        "is_duplicate": true/false,
        "canonical_name": "entity name or null",
        "confidence": 0.0-1.0
    }}
    """
    # ... LLM call ...
```

### Phase 3: Negation & Conditional Handling (Medium Priority) ⭐⭐

**Files to modify**:
1. `app/services/memori/manager.py` - Update extraction prompts

**Changes**:
```python
# Update triple extraction prompt
extraction_prompt = f"""
Extract triples from facts. 

IMPORTANT RULES:
1. Do NOT extract negated facts (e.g., "không sống ở Huế")
   - Instead, mark them with invalid_at timestamp
2. Do NOT extract hypothetical/conditional statements (e.g., "ước gì...")
3. Do NOT extract sarcastic statements
4. Extract temporal context (e.g., "trước đây", "hiện tại")

Facts:
{facts_text}

Return JSON with temporal info:
[{{
    "s": "subject",
    "p": "predicate",
    "o": "object",
    "valid_at": "ISO date or null",
    "invalid_at": "ISO date or null",
    "confidence": 0.0-1.0
}}]
"""
```

### Phase 4: Predicate Ontology (Medium Priority) ⭐⭐

**Files to create**:
1. `app/services/memori/ontology.py` - Define schemas
2. `app/services/memori/config.py` - Predicate whitelist

**Changes**:
```python
# Define predicate whitelist
PREDICATE_WHITELIST = {
    ("person", "person"): ["knows", "friend_of", "colleague_of"],
    ("person", "location"): ["lives_in", "works_in", "from"],
    ("person", "concept"): ["likes", "dislikes", "interested_in"],
    ("person", "programming_language"): ["uses", "learning", "expert_in"],
}

# Normalize predicates
def normalize_predicate(
    subject_type: str,
    predicate: str,
    object_type: str,
) -> str:
    """Normalize predicate to canonical form."""
    key = (subject_type, object_type)
    if key in PREDICATE_WHITELIST:
        # Find closest match
        for canonical in PREDICATE_WHITELIST[key]:
            if predicate.lower() in canonical or canonical in predicate.lower():
                return canonical
    return predicate
```

### Phase 5: Confidence Gating (Low Priority) ⭐

**Files to create**:
1. `app/db/models.py` - Add quarantine table
2. `app/services/memori/quarantine.py` - Quarantine logic

**Changes**:
```python
# Quarantine low-confidence extractions
class MemoriQuarantine(Base):
    __tablename__ = "memori_quarantine"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("memori_entities.id"))
    content = Column(Text)
    confidence = Column(Float)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    reviewed = Column(Boolean, default=False)

# Add to quarantine if low confidence
if confidence < 0.7:
    await quarantine_triple(triple, confidence, "Low confidence extraction")
else:
    await add_triple_to_graph(triple)
```

## Tổng kết

### Những gì Graphiti làm tốt hơn Memori hiện tại:

1. ✅ **Temporal Support**: Bi-temporal model với valid_at/invalid_at/expired_at
2. ✅ **Contradiction Detection**: LLM-based contradiction detection
3. ✅ **Entity Resolution**: 2-phase resolution (in-memory + graph-based)
4. ✅ **Negation Handling**: Explicit instructions trong prompts
5. ✅ **Predicate Ontology**: Custom schemas với Pydantic
6. ✅ **Confidence Gating**: Structured output với confidence scores
7. ✅ **Saga System**: Group related episodes
8. ✅ **Hybrid Search**: Vector + BM25 + Graph + Cross-encoder
9. ✅ **Bulk Operations**: Parallel processing, batch operations
10. ✅ **Production-Ready**: Comprehensive testing, error handling

### Priority Implementation Order:

1. **Phase 1** (High): Temporal Support - Giải quyết contradictions
2. **Phase 2** (High): Enhanced Entity Resolution - Giải quyết coreference
3. **Phase 3** (Medium): Negation Handling - Giải quyết negation/sarcasm
4. **Phase 4** (Medium): Predicate Ontology - Chuẩn hóa predicates
5. **Phase 5** (Low): Confidence Gating - Quality control

### Estimated Effort:

- **Phase 1**: 2-3 days (temporal fields + contradiction detection)
- **Phase 2**: 2-3 days (LLM-based entity resolution)
- **Phase 3**: 1-2 days (prompt engineering)
- **Phase 4**: 1-2 days (ontology definition)
- **Phase 5**: 2-3 days (quarantine system)

**Total**: ~10-15 days for complete implementation

### Next Steps:

1. Review this analysis với team
2. Prioritize phases based on user needs
3. Start với Phase 1 (Temporal Support) - highest impact
4. Iterate và test với real data
5. Monitor performance và adjust

---

**References**:
- Graphiti GitHub: https://github.com/getzep/graphiti
- Graphiti Paper: https://arxiv.org/abs/2501.13956
- Zep Blog: https://blog.getzep.com/state-of-the-art-agent-memory/
