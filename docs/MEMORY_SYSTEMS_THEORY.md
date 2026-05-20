# Memory Systems Theory - Comprehensive Guide

## Table of Contents
1. [Introduction to Memory in AI Systems](#introduction)
2. [Types of Memory Systems](#types-of-memory)
3. [Memory Architectures](#memory-architectures)
4. [Implementation Patterns](#implementation-patterns)
5. [Advanced Memory Techniques](#advanced-techniques)
6. [Memory in TheDocAI Project](#memory-in-thedocai)
7. [Best Practices & Optimization](#best-practices)

---

## 1. Introduction to Memory in AI Systems {#introduction}

### What is Memory in AI Context?

Memory trong hệ thống AI là khả năng lưu trữ, truy xuất và sử dụng thông tin từ các tương tác trước đó để cải thiện chất lượng phản hồi và duy trì ngữ cảnh (context) qua nhiều lượt hội thoại.

### Why Memory Matters?

- **Context Continuity**: Duy trì ngữ cảnh qua nhiều lượt hội thoại
- **Personalization**: Cá nhân hóa trải nghiệm người dùng
- **Efficiency**: Giảm chi phí token bằng cách tóm tắt thông tin
- **Knowledge Accumulation**: Tích lũy kiến thức theo thời gian
- **Better Reasoning**: Cải thiện khả năng suy luận với thông tin lịch sử

---

## 2. Types of Memory Systems {#types-of-memory}

### 2.1 Short-Term Memory (Working Memory)

**Định nghĩa**: Bộ nhớ tạm thời lưu trữ thông tin trong phiên làm việc hiện tại.

**Đặc điểm**:
- Dung lượng giới hạn (thường 4-10 tin nhắn gần nhất)
- Thời gian tồn tại ngắn (trong phiên làm việc)
- Truy xuất nhanh
- Không cần xử lý phức tạp

**Use Cases**:
- Chat conversations
- Form filling wizards
- Multi-step workflows

**Implementation Example**:
```python
class ShortTermMemory:
    def __init__(self, max_messages: int = 10):
        self.messages: List[Message] = []
        self.max_messages = max_messages
    
    def add(self, message: Message):
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)  # FIFO
    
    def get_context(self) -> List[Message]:
        return self.messages
```

### 2.2 Long-Term Memory (Persistent Memory)

**Định nghĩa**: Bộ nhớ lâu dài lưu trữ thông tin qua nhiều phiên làm việc.

**Đặc điểm**:
- Dung lượng lớn (có thể vô hạn)
- Thời gian tồn tại dài (vĩnh viễn)
- Cần indexing và retrieval mechanism
- Thường sử dụng vector databases

**Types of Long-Term Memory**:

#### a) Episodic Memory
Lưu trữ các sự kiện cụ thể theo thời gian.

```python
class EpisodicMemory:
    """Store specific events with temporal context"""
    def __init__(self):
        self.episodes: List[Episode] = []
    
    def store_episode(self, content: str, timestamp: datetime, metadata: dict):
        episode = Episode(
            content=content,
            timestamp=timestamp,
            metadata=metadata
        )
        self.episodes.append(episode)
    
    def retrieve_by_timerange(self, start: datetime, end: datetime):
        return [e for e in self.episodes 
                if start <= e.timestamp <= end]
```

#### b) Semantic Memory
Lưu trữ kiến thức tổng quát, facts, concepts.

```python
class SemanticMemory:
    """Store general knowledge and facts"""
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.knowledge_graph = {}
    
    def store_fact(self, fact: str, embedding: np.ndarray):
        self.vector_store.add(embedding, metadata={"fact": fact})
    
    def retrieve_related_facts(self, query: str, top_k: int = 5):
        query_embedding = self.embed(query)
        return self.vector_store.search(query_embedding, k=top_k)
```

#### c) Procedural Memory
Lưu trữ cách thực hiện các tác vụ (how-to knowledge).

```python
class ProceduralMemory:
    """Store procedures and workflows"""
    def __init__(self):
        self.procedures: Dict[str, Procedure] = {}
    
    def store_procedure(self, name: str, steps: List[str]):
        self.procedures[name] = Procedure(name=name, steps=steps)
    
    def execute_procedure(self, name: str, context: dict):
        procedure = self.procedures.get(name)
        if procedure:
            return procedure.execute(context)
```

### 2.3 Rolling Summary Memory

**Định nghĩa**: Kỹ thuật tóm tắt liên tục các cuộc hội thoại để giữ context trong giới hạn token.

**Đặc điểm**:
- Tự động tóm tắt khi đạt ngưỡng token
- Giữ lại thông tin quan trọng nhất
- Giảm chi phí API calls
- Duy trì context coherence

**Implementation Pattern**:
```python
class RollingSummaryMemory:
    """
    Inspired by chatbot/BE/app/services pattern
    Automatically summarizes conversation when token limit is reached
    """
    def __init__(
        self, 
        llm_client,
        max_tokens: int = 2000,
        summary_trigger_ratio: float = 0.8
    ):
        self.llm_client = llm_client
        self.max_tokens = max_tokens
        self.summary_trigger_ratio = summary_trigger_ratio
        self.messages: List[Message] = []
        self.summary: Optional[str] = None
        self.current_token_count: int = 0
    
    def add_message(self, message: Message):
        """Add message and trigger summary if needed"""
        self.messages.append(message)
        self.current_token_count += self._count_tokens(message)
        
        if self._should_summarize():
            self._create_summary()
    
    def _should_summarize(self) -> bool:
        """Check if we should create a summary"""
        threshold = self.max_tokens * self.summary_trigger_ratio
        return self.current_token_count >= threshold

    def _create_summary(self):
        """Create summary of conversation so far"""
        # Keep recent messages (last 3-5)
        recent_messages = self.messages[-5:]
        messages_to_summarize = self.messages[:-5]
        
        if not messages_to_summarize:
            return
        
        # Create summary prompt
        conversation_text = "\n".join([
            f"{m.role}: {m.content}" 
            for m in messages_to_summarize
        ])
        
        summary_prompt = f"""
        Summarize the following conversation, keeping key information:
        
        {conversation_text}
        
        Previous summary: {self.summary or "None"}
        
        Provide a concise summary that captures:
        - Main topics discussed
        - Important decisions or conclusions
        - Key facts or data mentioned
        """
        
        # Generate summary
        new_summary = self.llm_client.generate(summary_prompt)
        
        # Update state
        self.summary = new_summary
        self.messages = recent_messages
        self.current_token_count = sum(
            self._count_tokens(m) for m in recent_messages
        )
    
    def get_context_for_llm(self) -> List[Message]:
        """Get context to send to LLM"""
        context = []
        
        # Add summary as system message if exists
        if self.summary:
            context.append(Message(
                role="system",
                content=f"Conversation summary: {self.summary}"
            ))
        
        # Add recent messages
        context.extend(self.messages)
        
        return context
```

### 2.4 Entity Memory

**Định nghĩa**: Lưu trữ thông tin về các thực thể (người, địa điểm, tổ chức) được đề cập trong hội thoại.

**Implementation**:
```python
class EntityMemory:
    """Track entities mentioned in conversation"""
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
    
    def extract_and_store(self, text: str):
        """Extract entities using NER and store them"""
        entities = self.ner_model.extract(text)
        
        for entity in entities:
            entity_id = entity.name.lower()
            
            if entity_id in self.entities:
                # Update existing entity
                self.entities[entity_id].mentions += 1
                self.entities[entity_id].contexts.append(text)
            else:
                # Create new entity
                self.entities[entity_id] = Entity(
                    name=entity.name,
                    type=entity.type,
                    mentions=1,
                    contexts=[text]
                )
    
    def get_entity_info(self, entity_name: str) -> Optional[Entity]:
        """Retrieve information about an entity"""
        return self.entities.get(entity_name.lower())
```

### 2.5 Graph Memory (Knowledge Graph)

**Định nghĩa**: Lưu trữ thông tin dưới dạng đồ thị với nodes (entities) và edges (relationships).

**Đặc điểm**:
- Biểu diễn quan hệ phức tạp giữa các entities
- Hỗ trợ reasoning và inference
- Truy vấn linh hoạt (graph traversal)
- Phù hợp cho domain knowledge

**Implementation với Neo4j**:
```python
from neo4j import GraphDatabase

class GraphMemory:
    """
    Knowledge Graph Memory using Neo4j
    Similar to Memori system in TheDocAI
    """
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def add_entity(self, entity_name: str, entity_type: str, properties: dict):
        """Add an entity node to the graph"""
        with self.driver.session() as session:
            session.run(
                f"""
                MERGE (e:{entity_type} {{name: $name}})
                SET e += $properties
                """,
                name=entity_name,
                properties=properties
            )
    
    def add_relationship(
        self, 
        entity1: str, 
        entity2: str, 
        relationship_type: str,
        properties: dict = None
    ):
        """Add a relationship between two entities"""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (e1 {name: $entity1})
                MATCH (e2 {name: $entity2})
                MERGE (e1)-[r:$rel_type]->(e2)
                SET r += $properties
                """,
                entity1=entity1,
                entity2=entity2,
                rel_type=relationship_type,
                properties=properties or {}
            )

    def query_related_entities(
        self, 
        entity_name: str, 
        relationship_type: str = None,
        max_depth: int = 2
    ):
        """Query entities related to a given entity"""
        with self.driver.session() as session:
            if relationship_type:
                query = f"""
                MATCH (e {{name: $name}})-[r:{relationship_type}*1..{max_depth}]-(related)
                RETURN related, r
                """
            else:
                query = f"""
                MATCH (e {{name: $name}})-[r*1..{max_depth}]-(related)
                RETURN related, r
                """
            
            result = session.run(query, name=entity_name)
            return [record for record in result]
```

---

## 3. Memory Architectures {#memory-architectures}

### 3.1 Hierarchical Memory Architecture

Kết hợp nhiều loại memory theo tầng:

```
┌─────────────────────────────────────┐
│   Working Memory (Short-term)       │  ← Current conversation
├─────────────────────────────────────┤
│   Summary Memory (Rolling)          │  ← Compressed history
├─────────────────────────────────────┤
│   Entity Memory                     │  ← Extracted entities
├─────────────────────────────────────┤
│   Episodic Memory (Long-term)       │  ← Past conversations
├─────────────────────────────────────┤
│   Semantic Memory (Knowledge Base)  │  ← Facts & documents
├─────────────────────────────────────┤
│   Graph Memory (Knowledge Graph)    │  ← Relationships
└─────────────────────────────────────┘
```

**Implementation**:
```python
class HierarchicalMemory:
    """Multi-layer memory system"""
    def __init__(self, config: MemoryConfig):
        self.working_memory = ShortTermMemory(max_messages=10)
        self.summary_memory = RollingSummaryMemory(
            llm_client=config.llm_client,
            max_tokens=2000
        )
        self.entity_memory = EntityMemory()
        self.episodic_memory = EpisodicMemory()
        self.semantic_memory = SemanticMemory(config.vector_store)
        self.graph_memory = GraphMemory(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password
        )
    
    async def process_message(self, message: Message):
        """Process message through all memory layers"""
        # 1. Add to working memory
        self.working_memory.add(message)
        
        # 2. Update rolling summary
        self.summary_memory.add_message(message)
        
        # 3. Extract and store entities
        self.entity_memory.extract_and_store(message.content)
        
        # 4. Store as episode
        self.episodic_memory.store_episode(
            content=message.content,
            timestamp=datetime.now(),
            metadata={"user_id": message.user_id}
        )
        
        # 5. Update graph if entities found
        entities = self.entity_memory.extract(message.content)
        for entity in entities:
            self.graph_memory.add_entity(
                entity.name, 
                entity.type, 
                {"source": "conversation"}
            )

    async def retrieve_context(self, query: str) -> MemoryContext:
        """Retrieve relevant context from all memory layers"""
        context = MemoryContext()
        
        # Get working memory (always included)
        context.working_memory = self.working_memory.get_context()
        
        # Get summary if exists
        context.summary = self.summary_memory.summary
        
        # Search semantic memory (RAG)
        context.semantic_results = await self.semantic_memory.retrieve_related_facts(
            query, top_k=5
        )
        
        # Extract entities from query and get their info
        query_entities = self.entity_memory.extract(query)
        context.entities = [
            self.entity_memory.get_entity_info(e.name) 
            for e in query_entities
        ]
        
        # Query graph for relationships
        for entity in query_entities:
            related = self.graph_memory.query_related_entities(
                entity.name, max_depth=2
            )
            context.graph_context.extend(related)
        
        return context
```

### 3.2 Hybrid Memory Architecture (RAG + Memory)

Kết hợp Retrieval-Augmented Generation với Memory Systems:

```
User Query
    │
    ├─→ Memory Retrieval
    │   ├─→ Conversation History
    │   ├─→ Entity Memory
    │   └─→ Summary Memory
    │
    ├─→ Document Retrieval (RAG)
    │   ├─→ Vector Search
    │   ├─→ Keyword Search
    │   └─→ Hybrid Search
    │
    └─→ Context Fusion
        └─→ LLM Generation
```

---

## 4. Implementation Patterns {#implementation-patterns}

### 4.1 Buffer Memory Pattern

Đơn giản nhất - lưu trữ N tin nhắn gần nhất:

```python
from collections import deque

class BufferMemory:
    """Simple FIFO buffer for recent messages"""
    def __init__(self, buffer_size: int = 10):
        self.buffer = deque(maxlen=buffer_size)
    
    def add(self, message: dict):
        self.buffer.append(message)
    
    def get_all(self) -> list:
        return list(self.buffer)
    
    def clear(self):
        self.buffer.clear()
```

### 4.2 Token-Based Memory Pattern

Quản lý memory dựa trên token count:

```python
class TokenBasedMemory:
    """Manage memory based on token limits"""
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.messages: List[Message] = []
        self.token_count = 0
    
    def add(self, message: Message):
        message_tokens = self._count_tokens(message.content)
        
        # Remove old messages if exceeding limit
        while (self.token_count + message_tokens > self.max_tokens 
               and len(self.messages) > 0):
            removed = self.messages.pop(0)
            self.token_count -= self._count_tokens(removed.content)
        
        self.messages.append(message)
        self.token_count += message_tokens
    
    def _count_tokens(self, text: str) -> int:
        # Use tiktoken or approximation
        return len(text) // 4  # Rough approximation
```

### 4.3 Sliding Window with Summary Pattern

Kết hợp sliding window và summary (như chatbot project):

```python
class SlidingWindowSummaryMemory:
    """
    Maintains a sliding window of recent messages
    and creates summaries of older messages
    """
    def __init__(
        self,
        llm_client,
        window_size: int = 10,
        summary_threshold: int = 20
    ):
        self.llm_client = llm_client
        self.window_size = window_size
        self.summary_threshold = summary_threshold
        self.messages: List[Message] = []
        self.summaries: List[str] = []
    
    def add(self, message: Message):
        self.messages.append(message)
        
        # Check if we need to create a summary
        if len(self.messages) > self.summary_threshold:
            self._create_and_compress()
    
    def _create_and_compress(self):
        """Create summary of old messages and keep recent ones"""
        # Messages to summarize (all except recent window)
        to_summarize = self.messages[:-self.window_size]
        
        if not to_summarize:
            return
        
        # Create summary
        summary_text = self._generate_summary(to_summarize)
        self.summaries.append(summary_text)
        
        # Keep only recent messages
        self.messages = self.messages[-self.window_size:]
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """Generate summary using LLM"""
        conversation = "\n".join([
            f"{m.role}: {m.content}" for m in messages
        ])
        
        prompt = f"""
        Create a concise summary of this conversation segment:
        
        {conversation}
        
        Focus on:
        - Key topics and decisions
        - Important facts mentioned
        - User preferences or requirements
        """
        
        return self.llm_client.generate(prompt)

    def get_context(self) -> dict:
        """Get full context including summaries and recent messages"""
        return {
            "summaries": self.summaries,
            "recent_messages": self.messages
        }
```

### 4.4 Vector-Based Memory Pattern

Sử dụng embeddings để retrieve relevant memories:

```python
class VectorMemory:
    """Store and retrieve memories using vector similarity"""
    def __init__(self, embedding_model, vector_store):
        self.embedding_model = embedding_model
        self.vector_store = vector_store
        self.memories: List[Memory] = []
    
    async def add(self, content: str, metadata: dict = None):
        """Add memory with embedding"""
        # Generate embedding
        embedding = await self.embedding_model.embed(content)
        
        # Store in vector database
        memory_id = self.vector_store.add(
            embedding=embedding,
            content=content,
            metadata=metadata or {}
        )
        
        # Keep reference
        self.memories.append(Memory(
            id=memory_id,
            content=content,
            metadata=metadata
        ))
    
    async def retrieve(self, query: str, top_k: int = 5) -> List[Memory]:
        """Retrieve most relevant memories"""
        # Generate query embedding
        query_embedding = await self.embedding_model.embed(query)
        
        # Search vector store
        results = self.vector_store.search(
            query_embedding, 
            k=top_k
        )
        
        return [
            Memory(
                id=r.id,
                content=r.content,
                metadata=r.metadata,
                score=r.score
            )
            for r in results
        ]
```

---

## 5. Advanced Memory Techniques {#advanced-techniques}

### 5.1 Memory Consolidation

Định kỳ hợp nhất và tối ưu memories:

```python
class MemoryConsolidation:
    """Consolidate and optimize memories over time"""
    def __init__(self, memory_store, llm_client):
        self.memory_store = memory_store
        self.llm_client = llm_client
    
    async def consolidate(self):
        """Consolidate similar or redundant memories"""
        # 1. Find similar memories
        similar_groups = await self._find_similar_memories()
        
        # 2. Merge each group
        for group in similar_groups:
            merged = await self._merge_memories(group)
            
            # 3. Replace old memories with merged one
            for old_memory in group:
                await self.memory_store.delete(old_memory.id)
            
            await self.memory_store.add(merged)
    
    async def _find_similar_memories(self, threshold: float = 0.85):
        """Find groups of similar memories"""
        memories = await self.memory_store.get_all()
        groups = []
        
        for i, mem1 in enumerate(memories):
            group = [mem1]
            for mem2 in memories[i+1:]:
                similarity = self._compute_similarity(mem1, mem2)
                if similarity > threshold:
                    group.append(mem2)
            
            if len(group) > 1:
                groups.append(group)
        
        return groups
    
    async def _merge_memories(self, memories: List[Memory]) -> Memory:
        """Merge multiple memories into one"""
        contents = [m.content for m in memories]
        
        prompt = f"""
        Merge these related memories into a single, comprehensive memory:
        
        {chr(10).join(f"- {c}" for c in contents)}
        
        Create a consolidated version that captures all important information.
        """
        
        merged_content = await self.llm_client.generate(prompt)
        
        return Memory(
            content=merged_content,
            metadata={"consolidated_from": len(memories)}
        )
```

### 5.2 Memory Importance Scoring

Đánh giá và ưu tiên memories quan trọng:

```python
class MemoryImportanceScorer:
    """Score memories by importance for retention decisions"""
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def score_memory(self, memory: Memory) -> float:
        """Score memory importance (0-1)"""
        # Factors to consider:
        factors = {
            "recency": self._score_recency(memory),
            "frequency": self._score_frequency(memory),
            "relevance": await self._score_relevance(memory),
            "emotional_weight": await self._score_emotional_weight(memory)
        }
        
        # Weighted combination
        weights = {
            "recency": 0.2,
            "frequency": 0.3,
            "relevance": 0.3,
            "emotional_weight": 0.2
        }
        
        score = sum(factors[k] * weights[k] for k in factors)
        return score
    
    def _score_recency(self, memory: Memory) -> float:
        """Score based on how recent the memory is"""
        age_days = (datetime.now() - memory.timestamp).days
        # Exponential decay
        return math.exp(-age_days / 30)  # Half-life of 30 days
    
    def _score_frequency(self, memory: Memory) -> float:
        """Score based on access frequency"""
        access_count = memory.metadata.get("access_count", 0)
        # Logarithmic scaling
        return min(1.0, math.log(access_count + 1) / math.log(100))
    
    async def _score_relevance(self, memory: Memory) -> float:
        """Score based on relevance to user's interests"""
        # Use LLM to assess relevance
        prompt = f"""
        Rate the importance of this memory on a scale of 0-1:
        
        Memory: {memory.content}
        
        Consider:
        - Is this factual information?
        - Is this a user preference?
        - Is this a critical decision?
        
        Return only a number between 0 and 1.
        """
        
        response = await self.llm_client.generate(prompt)
        try:
            return float(response.strip())
        except:
            return 0.5  # Default

    async def _score_emotional_weight(self, memory: Memory) -> float:
        """Score based on emotional significance"""
        # Detect emotional content
        emotional_keywords = [
            "important", "critical", "love", "hate", 
            "urgent", "remember", "never forget"
        ]
        
        content_lower = memory.content.lower()
        matches = sum(1 for kw in emotional_keywords if kw in content_lower)
        
        return min(1.0, matches / 3)
```

### 5.3 Forgetting Mechanism

Cơ chế quên thông tin ít quan trọng:

```python
class ForgettingMechanism:
    """Implement forgetting to manage memory size"""
    def __init__(
        self, 
        memory_store,
        importance_scorer: MemoryImportanceScorer,
        max_memories: int = 1000
    ):
        self.memory_store = memory_store
        self.importance_scorer = importance_scorer
        self.max_memories = max_memories
    
    async def prune_memories(self):
        """Remove least important memories when limit is reached"""
        memories = await self.memory_store.get_all()
        
        if len(memories) <= self.max_memories:
            return
        
        # Score all memories
        scored_memories = []
        for memory in memories:
            score = await self.importance_scorer.score_memory(memory)
            scored_memories.append((memory, score))
        
        # Sort by score (ascending)
        scored_memories.sort(key=lambda x: x[1])
        
        # Remove lowest scoring memories
        to_remove = len(memories) - self.max_memories
        for memory, score in scored_memories[:to_remove]:
            await self.memory_store.delete(memory.id)
            print(f"Forgot memory (score={score:.2f}): {memory.content[:50]}...")
```

### 5.4 Memory Reflection

LLM tự phân tích và tạo insights từ memories:

```python
class MemoryReflection:
    """Generate high-level insights from memories"""
    def __init__(self, memory_store, llm_client):
        self.memory_store = memory_store
        self.llm_client = llm_client
        self.reflections: List[Reflection] = []
    
    async def generate_reflections(self, time_window: timedelta = None):
        """Generate reflections from recent memories"""
        # Get memories from time window
        if time_window:
            cutoff = datetime.now() - time_window
            memories = await self.memory_store.get_since(cutoff)
        else:
            memories = await self.memory_store.get_all()
        
        # Group memories by topic
        topics = await self._cluster_memories(memories)
        
        # Generate reflection for each topic
        for topic, topic_memories in topics.items():
            reflection = await self._reflect_on_topic(topic, topic_memories)
            self.reflections.append(reflection)
    
    async def _reflect_on_topic(
        self, 
        topic: str, 
        memories: List[Memory]
    ) -> Reflection:
        """Generate insight about a topic"""
        memory_texts = "\n".join([m.content for m in memories])
        
        prompt = f"""
        Analyze these memories about "{topic}" and generate insights:
        
        {memory_texts}
        
        Provide:
        1. Key patterns or trends
        2. Important conclusions
        3. Actionable insights
        4. Questions that remain unanswered
        """
        
        insight = await self.llm_client.generate(prompt)
        
        return Reflection(
            topic=topic,
            insight=insight,
            based_on_memories=len(memories),
            timestamp=datetime.now()
        )
```

### 5.5 Temporal Memory Decay

Mô phỏng quá trình quên tự nhiên:

```python
class TemporalMemoryDecay:
    """Implement time-based memory decay"""
    def __init__(self, half_life_days: float = 30):
        self.half_life_days = half_life_days
    
    def calculate_strength(self, memory: Memory) -> float:
        """Calculate current memory strength based on age and access"""
        # Base decay from age
        age_days = (datetime.now() - memory.timestamp).days
        age_decay = math.exp(-age_days * math.log(2) / self.half_life_days)
        
        # Boost from recent access
        if memory.last_accessed:
            access_age_days = (datetime.now() - memory.last_accessed).days
            access_boost = math.exp(-access_age_days * math.log(2) / 7)  # 7-day half-life
        else:
            access_boost = 0
        
        # Combine factors
        strength = age_decay + (access_boost * 0.3)
        return min(1.0, strength)
    
    def should_retain(self, memory: Memory, threshold: float = 0.1) -> bool:
        """Decide if memory should be retained"""
        strength = self.calculate_strength(memory)
        return strength >= threshold
```

### 5.6 Multi-Modal Memory

Lưu trữ và truy xuất nhiều loại dữ liệu:

```python
class MultiModalMemory:
    """Store and retrieve text, images, audio, etc."""
    def __init__(self, vector_store, embedding_models: dict):
        self.vector_store = vector_store
        self.embedding_models = embedding_models  # {modality: model}
        self.memories: Dict[str, List[Memory]] = {
            "text": [],
            "image": [],
            "audio": [],
            "video": []
        }
    
    async def add_text(self, content: str, metadata: dict = None):
        """Add text memory"""
        embedding = await self.embedding_models["text"].embed(content)
        memory = Memory(
            modality="text",
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        self.memories["text"].append(memory)
        await self.vector_store.add(embedding, memory)

    async def add_image(self, image_path: str, caption: str = None, metadata: dict = None):
        """Add image memory"""
        # Generate image embedding
        embedding = await self.embedding_models["image"].embed_image(image_path)
        
        memory = Memory(
            modality="image",
            content=image_path,
            caption=caption,
            embedding=embedding,
            metadata=metadata
        )
        self.memories["image"].append(memory)
        await self.vector_store.add(embedding, memory)
    
    async def retrieve_cross_modal(
        self, 
        query: str, 
        query_modality: str = "text",
        target_modalities: List[str] = None,
        top_k: int = 5
    ):
        """Retrieve memories across different modalities"""
        # Generate query embedding
        query_embedding = await self.embedding_models[query_modality].embed(query)
        
        # Search across specified modalities
        if target_modalities is None:
            target_modalities = ["text", "image", "audio"]
        
        results = []
        for modality in target_modalities:
            modality_results = await self.vector_store.search(
                query_embedding,
                filter={"modality": modality},
                k=top_k
            )
            results.extend(modality_results)
        
        # Re-rank and return top-k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
```

---

## 6. Memory in TheDocAI Project {#memory-in-thedocai}

### 6.1 Current Memory Implementation

TheDocAI sử dụng **Memori** - một Graph Memory System với Neo4j:

**Architecture**:
```
User Query
    │
    ├─→ Conversation Memory (PostgreSQL)
    │   └─→ Recent messages in session
    │
    ├─→ Memori Graph (Neo4j)
    │   ├─→ Entity Extraction
    │   ├─→ Relationship Mapping
    │   └─→ Graph Traversal
    │
    └─→ Document Memory (pgvector)
        └─→ RAG Retrieval
```

**Key Components**:

1. **Conversation Storage** (`server/app/db/models.py`):
   - Stores chat messages in PostgreSQL
   - Links to user sessions
   - Maintains conversation history

2. **Memori Graph** (`server/app/services/memori/`):
   - Extracts entities from conversations
   - Builds knowledge graph in Neo4j
   - Enables relationship-based retrieval

3. **Document Chunks** (`server/app/services/documents/`):
   - Chunks documents using LlamaIndex SentenceSplitter
   - Stores embeddings in pgvector
   - Enables semantic search

### 6.2 Comparison with Chatbot Rolling Summary

**Chatbot Project** (`C:\Users\THINKPAD\Documents\GitHub\chatbot\BE\app\services`):

Sử dụng **Rolling Summary Pattern**:

```python
# Simplified version of chatbot's approach
class ChatbotMemory:
    """
    Rolling summary approach from chatbot project
    """
    def __init__(self, max_messages: int = 20):
        self.messages = []
        self.summary = None
        self.max_messages = max_messages
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        
        # Trigger summary when threshold reached
        if len(self.messages) > self.max_messages:
            self._create_summary()
    
    def _create_summary(self):
        # Keep last 5 messages
        recent = self.messages[-5:]
        to_summarize = self.messages[:-5]
        
        # Create summary (pseudo-code)
        new_summary = llm.summarize(to_summarize, self.summary)
        
        # Update state
        self.summary = new_summary
        self.messages = recent
    
    def get_context(self):
        context = []
        if self.summary:
            context.append({"role": "system", "content": f"Summary: {self.summary}"})
        context.extend(self.messages)
        return context
```

**Advantages of Rolling Summary**:
- ✅ Low token cost
- ✅ Simple implementation
- ✅ Maintains conversation flow
- ✅ No external database needed

**Disadvantages**:
- ❌ Loses fine-grained details
- ❌ Cannot retrieve specific past information
- ❌ Summary quality depends on LLM
- ❌ No structured knowledge representation

### 6.3 Hybrid Approach Recommendation

Kết hợp cả hai approaches:

```python
class HybridMemorySystem:
    """
    Combines TheDocAI's Graph Memory with Rolling Summary
    Best of both worlds
    """
    def __init__(self, config):
        # Short-term: Rolling summary for recent context
        self.rolling_memory = RollingSummaryMemory(
            llm_client=config.llm_client,
            max_tokens=2000
        )
        
        # Long-term: Graph memory for structured knowledge
        self.graph_memory = GraphMemory(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password
        )
        
        # Document memory: RAG for factual retrieval
        self.document_memory = VectorMemory(
            embedding_model=config.embedding_model,
            vector_store=config.vector_store
        )
        
        # Entity tracking
        self.entity_memory = EntityMemory()
    
    async def process_message(self, message: Message):
        """Process through all memory systems"""
        # 1. Add to rolling summary (for immediate context)
        self.rolling_memory.add_message(message)
        
        # 2. Extract entities
        entities = await self.entity_memory.extract_and_store(message.content)
        
        # 3. Update graph with entities and relationships
        for entity in entities:
            await self.graph_memory.add_entity(
                entity.name,
                entity.type,
                {"last_mentioned": datetime.now()}
            )
        
        # 4. Store important facts in document memory
        if self._is_important_fact(message):
            await self.document_memory.add(
                content=message.content,
                metadata={"type": "conversation_fact", "timestamp": datetime.now()}
            )

    async def retrieve_context(self, query: str) -> dict:
        """Retrieve context from all memory layers"""
        # 1. Get rolling summary context (always included)
        rolling_context = self.rolling_memory.get_context_for_llm()
        
        # 2. Search document memory (RAG)
        doc_results = await self.document_memory.retrieve(query, top_k=5)
        
        # 3. Extract entities from query and get graph context
        query_entities = await self.entity_memory.extract(query)
        graph_context = []
        for entity in query_entities:
            related = await self.graph_memory.query_related_entities(
                entity.name,
                max_depth=2
            )
            graph_context.extend(related)
        
        return {
            "rolling_summary": rolling_context,
            "documents": doc_results,
            "graph_knowledge": graph_context,
            "entities": query_entities
        }
    
    def _is_important_fact(self, message: Message) -> bool:
        """Determine if message contains important fact"""
        # Heuristics: contains numbers, dates, names, etc.
        indicators = [
            r'\d+',  # numbers
            r'\b(is|are|was|were)\b',  # factual statements
            r'\b(always|never|must|should)\b',  # rules
        ]
        
        import re
        for pattern in indicators:
            if re.search(pattern, message.content, re.IGNORECASE):
                return True
        return False
```

---

## 7. Best Practices & Optimization {#best-practices}

### 7.1 Memory Management Best Practices

**1. Layered Approach**
- Use short-term memory for immediate context
- Use long-term memory for persistent knowledge
- Use summaries to bridge the gap

**2. Selective Storage**
- Not everything needs to be remembered
- Filter noise and redundant information
- Prioritize important facts and decisions

**3. Efficient Retrieval**
- Index memories properly (vector, keyword, graph)
- Use hybrid search for better recall
- Cache frequently accessed memories

**4. Regular Maintenance**
- Consolidate similar memories
- Prune low-importance memories
- Update outdated information

**5. Privacy & Security**
- Encrypt sensitive memories
- Implement access controls
- Allow users to delete their data

### 7.2 Performance Optimization

**Token Optimization**:
```python
class TokenOptimizedMemory:
    """Optimize token usage in memory retrieval"""
    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens
    
    def build_context(
        self, 
        summary: str,
        recent_messages: List[Message],
        retrieved_docs: List[Document],
        graph_facts: List[str]
    ) -> str:
        """Build context within token budget"""
        context_parts = []
        remaining_tokens = self.max_context_tokens
        
        # 1. Always include summary (highest priority)
        if summary:
            summary_tokens = self._count_tokens(summary)
            if summary_tokens < remaining_tokens:
                context_parts.append(f"Summary: {summary}")
                remaining_tokens -= summary_tokens
        
        # 2. Include recent messages (high priority)
        for msg in reversed(recent_messages):
            msg_tokens = self._count_tokens(msg.content)
            if msg_tokens < remaining_tokens:
                context_parts.insert(1, f"{msg.role}: {msg.content}")
                remaining_tokens -= msg_tokens
            else:
                break
        
        # 3. Include retrieved documents (medium priority)
        for doc in retrieved_docs:
            doc_tokens = self._count_tokens(doc.content)
            if doc_tokens < remaining_tokens:
                context_parts.append(f"Document: {doc.content}")
                remaining_tokens -= doc_tokens
            else:
                # Truncate document to fit
                truncated = self._truncate_to_tokens(doc.content, remaining_tokens)
                context_parts.append(f"Document: {truncated}")
                break
        
        return "\n\n".join(context_parts)
```

**Caching Strategy**:
```python
from functools import lru_cache
import hashlib

class CachedMemoryRetrieval:
    """Cache memory retrieval results"""
    def __init__(self, memory_system, cache_ttl: int = 300):
        self.memory_system = memory_system
        self.cache_ttl = cache_ttl
        self.cache = {}
    
    async def retrieve_with_cache(self, query: str) -> dict:
        """Retrieve with caching"""
        # Generate cache key
        cache_key = hashlib.md5(query.encode()).hexdigest()
        
        # Check cache
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_ttl:
                return cached_result
        
        # Retrieve from memory system
        result = await self.memory_system.retrieve_context(query)
        
        # Store in cache
        self.cache[cache_key] = (result, datetime.now())
        
        return result
```

### 7.3 Monitoring & Debugging

**Memory Metrics**:
```python
class MemoryMetrics:
    """Track memory system performance"""
    def __init__(self):
        self.metrics = {
            "total_memories": 0,
            "retrieval_latency": [],
            "cache_hit_rate": 0,
            "storage_size_mb": 0,
            "avg_relevance_score": 0
        }
    
    def track_retrieval(self, latency_ms: float, cache_hit: bool, relevance: float):
        """Track a retrieval operation"""
        self.metrics["retrieval_latency"].append(latency_ms)
        
        if cache_hit:
            self.metrics["cache_hit_rate"] += 1
        
        self.metrics["avg_relevance_score"] = (
            (self.metrics["avg_relevance_score"] + relevance) / 2
        )
    
    def get_summary(self) -> dict:
        """Get metrics summary"""
        return {
            "total_memories": self.metrics["total_memories"],
            "avg_retrieval_latency_ms": sum(self.metrics["retrieval_latency"]) / len(self.metrics["retrieval_latency"]) if self.metrics["retrieval_latency"] else 0,
            "cache_hit_rate": self.metrics["cache_hit_rate"],
            "storage_size_mb": self.metrics["storage_size_mb"],
            "avg_relevance_score": self.metrics["avg_relevance_score"]
        }
```

### 7.4 Common Pitfalls & Solutions

**Pitfall 1: Memory Explosion**
- Problem: Storing too much data
- Solution: Implement forgetting mechanism and importance scoring

**Pitfall 2: Irrelevant Retrieval**
- Problem: Retrieved memories not relevant to query
- Solution: Use hybrid search, reranking, and better embeddings

**Pitfall 3: Stale Information**
- Problem: Outdated information in memory
- Solution: Implement temporal decay and update mechanisms

**Pitfall 4: Context Overflow**
- Problem: Exceeding token limits
- Solution: Use rolling summaries and token budgeting

**Pitfall 5: Privacy Leaks**
- Problem: Exposing sensitive information
- Solution: Implement access controls and data anonymization

---

## 8. Advanced Topics & Research Directions

### 8.1 Episodic Memory with Temporal Reasoning

```python
class TemporalEpisodicMemory:
    """Episodic memory with temporal reasoning capabilities"""
    def __init__(self):
        self.episodes = []
    
    def query_temporal(
        self, 
        query: str, 
        time_constraint: str = None
    ) -> List[Episode]:
        """
        Query with temporal constraints
        Examples:
        - "What happened before X?"
        - "What was discussed last week?"
        - "Show me the sequence of events"
        """
        # Parse temporal constraint
        if "before" in time_constraint:
            # Filter episodes before a certain event
            pass
        elif "after" in time_constraint:
            # Filter episodes after a certain event
            pass
        elif "between" in time_constraint:
            # Filter episodes in a time range
            pass
        
        return filtered_episodes
```

### 8.2 Associative Memory Networks

Mô phỏng cách não bộ liên kết thông tin:

```python
class AssociativeMemory:
    """Memory system based on associations"""
    def __init__(self):
        self.associations = {}  # {memory_id: [related_memory_ids]}
    
    def add_association(self, memory1_id: str, memory2_id: str, strength: float):
        """Create association between two memories"""
        if memory1_id not in self.associations:
            self.associations[memory1_id] = []
        
        self.associations[memory1_id].append({
            "memory_id": memory2_id,
            "strength": strength
        })
    
    def retrieve_by_association(
        self, 
        seed_memory_id: str, 
        max_depth: int = 3
    ) -> List[Memory]:
        """Retrieve memories through associative links"""
        visited = set()
        to_visit = [(seed_memory_id, 0)]
        results = []
        
        while to_visit:
            current_id, depth = to_visit.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            
            visited.add(current_id)
            results.append(current_id)
            
            # Add associated memories
            if current_id in self.associations:
                for assoc in self.associations[current_id]:
                    if assoc["strength"] > 0.5:  # Threshold
                        to_visit.append((assoc["memory_id"], depth + 1))
        
        return results
```

### 8.3 Meta-Memory (Memory about Memory)

Hệ thống nhớ về chính bản thân nó:

```python
class MetaMemory:
    """Track what the system knows and doesn't know"""
    def __init__(self):
        self.knowledge_map = {}  # {topic: confidence_score}
        self.gaps = []  # Known knowledge gaps
    
    def assess_knowledge(self, topic: str) -> float:
        """Assess confidence in knowledge about a topic"""
        if topic in self.knowledge_map:
            return self.knowledge_map[topic]
        return 0.0
    
    def identify_gap(self, topic: str, context: str):
        """Identify a knowledge gap"""
        self.gaps.append({
            "topic": topic,
            "context": context,
            "identified_at": datetime.now()
        })
    
    def should_ask_clarification(self, query: str) -> bool:
        """Decide if system should ask for clarification"""
        # Extract topic from query
        topic = self._extract_topic(query)
        
        # Check confidence
        confidence = self.assess_knowledge(topic)
        
        return confidence < 0.3  # Low confidence threshold
```

### 8.4 Distributed Memory Systems

Cho hệ thống multi-agent hoặc distributed:

```python
class DistributedMemory:
    """Shared memory across multiple agents/services"""
    def __init__(self, redis_client, namespace: str):
        self.redis = redis_client
        self.namespace = namespace
    
    async def share_memory(self, memory: Memory, agents: List[str]):
        """Share memory with specific agents"""
        memory_key = f"{self.namespace}:memory:{memory.id}"
        
        # Store memory
        await self.redis.set(
            memory_key,
            json.dumps(memory.to_dict()),
            ex=3600  # 1 hour TTL
        )
        
        # Notify agents
        for agent_id in agents:
            channel = f"{self.namespace}:agent:{agent_id}:notifications"
            await self.redis.publish(
                channel,
                json.dumps({"type": "new_memory", "memory_id": memory.id})
            )
    
    async def subscribe_to_shared_memories(self, agent_id: str):
        """Subscribe to memory updates"""
        channel = f"{self.namespace}:agent:{agent_id}:notifications"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                if data["type"] == "new_memory":
                    # Fetch and process new memory
                    memory = await self.fetch_memory(data["memory_id"])
                    yield memory
```

---

## 9. Comparison Table: Memory Approaches

| Feature | Buffer Memory | Rolling Summary | Vector Memory | Graph Memory | Hybrid |
|---------|--------------|-----------------|---------------|--------------|--------|
| **Complexity** | Low | Medium | Medium | High | High |
| **Token Cost** | High | Low | Medium | Medium | Medium |
| **Retrieval Quality** | Poor | Medium | Good | Excellent | Excellent |
| **Setup Effort** | Minimal | Low | Medium | High | High |
| **Scalability** | Poor | Good | Excellent | Good | Excellent |
| **Context Preservation** | Excellent | Good | Medium | Good | Excellent |
| **Structured Knowledge** | No | No | No | Yes | Yes |
| **Best For** | Simple chat | Long conversations | RAG systems | Knowledge bases | Production systems |

---

## 10. Implementation Roadmap

### Phase 1: Basic Memory (Week 1-2)
- [ ] Implement BufferMemory for short-term storage
- [ ] Add token counting utilities
- [ ] Create simple retrieval mechanism
- [ ] Test with basic chat scenarios

### Phase 2: Rolling Summary (Week 3-4)
- [ ] Implement RollingSummaryMemory
- [ ] Add LLM-based summarization
- [ ] Optimize token usage
- [ ] Test with long conversations

### Phase 3: Vector Memory (Week 5-6)
- [ ] Integrate embedding model
- [ ] Set up vector database (pgvector/Qdrant)
- [ ] Implement semantic search
- [ ] Add hybrid search (vector + keyword)

### Phase 4: Graph Memory (Week 7-8)
- [ ] Set up Neo4j
- [ ] Implement entity extraction
- [ ] Build relationship mapping
- [ ] Create graph traversal queries

### Phase 5: Integration & Optimization (Week 9-10)
- [ ] Combine all memory types
- [ ] Implement memory consolidation
- [ ] Add forgetting mechanism
- [ ] Performance optimization
- [ ] Monitoring and metrics

---

## 11. Code Examples from Real Projects

### Example 1: Chatbot Rolling Summary (Simplified)

```python
# From: chatbot/BE/app/services/conversation_service.py
class ConversationMemoryManager:
    """Real-world rolling summary implementation"""
    def __init__(self, llm_service, max_history: int = 20):
        self.llm = llm_service
        self.max_history = max_history
        self.conversation_summary = None
    
    async def add_message(self, role: str, content: str, messages: list):
        """Add message and manage memory"""
        messages.append({"role": role, "content": content})
        
        # Check if we need to summarize
        if len(messages) > self.max_history:
            await self._compress_history(messages)
        
        return messages
    
    async def _compress_history(self, messages: list):
        """Compress old messages into summary"""
        # Keep recent messages
        recent_count = 5
        recent_messages = messages[-recent_count:]
        old_messages = messages[:-recent_count]
        
        # Create summary of old messages
        if old_messages:
            summary_prompt = self._build_summary_prompt(
                old_messages, 
                self.conversation_summary
            )
            
            new_summary = await self.llm.generate(summary_prompt)
            self.conversation_summary = new_summary
            
            # Replace messages with summary + recent
            messages.clear()
            messages.extend(recent_messages)
    
    def _build_summary_prompt(self, messages: list, existing_summary: str = None):
        """Build prompt for summarization"""
        conversation = "\n".join([
            f"{m['role']}: {m['content']}" for m in messages
        ])
        
        if existing_summary:
            return f"""
            Previous summary: {existing_summary}
            
            New messages to add:
            {conversation}
            
            Create an updated summary that includes both the previous summary 
            and the new information. Keep it concise but comprehensive.
            """
        else:
            return f"""
            Summarize this conversation:
            {conversation}
            
            Focus on key points, decisions, and important information.
            """
```

### Example 2: TheDocAI Memori Integration

```python
# From: doc-chat-ai/server/app/services/memori/memory_service.py
class MemoriGraphService:
    """Graph-based memory with Neo4j"""
    def __init__(self, neo4j_driver, entity_extractor):
        self.driver = neo4j_driver
        self.entity_extractor = entity_extractor
    
    async def process_conversation(
        self, 
        user_message: str, 
        assistant_response: str,
        conversation_id: str
    ):
        """Extract entities and build knowledge graph"""
        # Extract entities from both messages
        user_entities = await self.entity_extractor.extract(user_message)
        assistant_entities = await self.entity_extractor.extract(assistant_response)
        
        # Store entities in graph
        with self.driver.session() as session:
            for entity in user_entities + assistant_entities:
                session.run("""
                    MERGE (e:Entity {name: $name, type: $type})
                    ON CREATE SET e.first_seen = datetime()
                    ON MATCH SET e.last_seen = datetime()
                    SET e.mention_count = coalesce(e.mention_count, 0) + 1
                """, name=entity.name, type=entity.type)
            
            # Create relationships between co-occurring entities
            for i, e1 in enumerate(user_entities):
                for e2 in user_entities[i+1:]:
                    session.run("""
                        MATCH (e1:Entity {name: $name1})
                        MATCH (e2:Entity {name: $name2})
                        MERGE (e1)-[r:CO_OCCURS_WITH]-(e2)
                        ON CREATE SET r.count = 1
                        ON MATCH SET r.count = r.count + 1
                    """, name1=e1.name, name2=e2.name)
    
    async def retrieve_context(self, query: str, max_depth: int = 2):
        """Retrieve relevant context from graph"""
        # Extract entities from query
        query_entities = await self.entity_extractor.extract(query)
        
        if not query_entities:
            return []
        
        # Query graph for related entities
        with self.driver.session() as session:
            results = []
            for entity in query_entities:
                result = session.run(f"""
                    MATCH path = (e:Entity {{name: $name}})-[*1..{max_depth}]-(related)
                    RETURN related, relationships(path) as rels
                    ORDER BY related.mention_count DESC
                    LIMIT 10
                """, name=entity.name)
                
                results.extend([record for record in result])
            
            return results
```

---

## 12. References & Further Reading

### Academic Papers
1. **"Memory Networks"** - Weston et al., 2014
   - Foundational work on neural memory systems

2. **"Neural Turing Machines"** - Graves et al., 2014
   - Differentiable memory for neural networks

3. **"Generative Agents: Interactive Simulacra of Human Behavior"** - Park et al., 2023
   - Memory and reflection in AI agents

4. **"MemGPT: Towards LLMs as Operating Systems"** - Packer et al., 2023
   - Hierarchical memory management for LLMs

### Industry Implementations
- **LangChain Memory**: https://python.langchain.com/docs/modules/memory/
- **Mem0**: https://github.com/mem0ai/mem0
- **Cognee**: https://github.com/topoteretes/cognee
- **Graphiti**: https://github.com/getzep/graphiti

### Related Concepts
- **RAG (Retrieval-Augmented Generation)**: Combining retrieval with generation
- **Vector Databases**: Efficient similarity search (Pinecone, Qdrant, Weaviate)
- **Knowledge Graphs**: Structured knowledge representation (Neo4j, Amazon Neptune)
- **Prompt Engineering**: Optimizing context for LLMs

---

## 13. Glossary

**Buffer Memory**: Simple FIFO storage of recent messages

**Consolidation**: Process of merging similar memories

**Context Window**: Maximum tokens an LLM can process

**Embedding**: Vector representation of text for similarity search

**Entity**: Named object (person, place, thing) extracted from text

**Episodic Memory**: Memory of specific events with temporal context

**Forgetting**: Mechanism to remove low-importance memories

**Graph Memory**: Knowledge stored as nodes and relationships

**Hybrid Search**: Combining vector and keyword search

**Importance Scoring**: Assessing memory value for retention

**Long-term Memory**: Persistent storage across sessions

**Meta-Memory**: Knowledge about what the system knows

**Procedural Memory**: Memory of how to perform tasks

**RAG**: Retrieval-Augmented Generation

**Reflection**: High-level insights generated from memories

**Rolling Summary**: Continuous summarization to manage context

**Semantic Memory**: General knowledge and facts

**Short-term Memory**: Temporary storage for current session

**Temporal Decay**: Time-based reduction in memory strength

**Vector Store**: Database optimized for similarity search

---

## 14. Conclusion

Memory systems là thành phần quan trọng để xây dựng AI applications thông minh và có khả năng duy trì ngữ cảnh. Việc lựa chọn loại memory phù hợp phụ thuộc vào:

- **Use case**: Chat bot, knowledge base, agent system?
- **Scale**: Số lượng users và conversations
- **Budget**: Token costs và infrastructure
- **Complexity**: Development và maintenance effort

**Recommendations**:
- Start simple với Buffer hoặc Rolling Summary
- Add Vector Memory khi cần RAG
- Consider Graph Memory cho complex knowledge domains
- Implement Hybrid approach cho production systems

TheDocAI đã implement một hybrid system mạnh mẽ kết hợp:
- PostgreSQL cho conversation storage
- Neo4j (Memori) cho graph memory
- pgvector cho document retrieval

Bạn có thể học hỏi và mở rộng từ architecture này!

---

**Document Version**: 1.0  
**Last Updated**: 2026-04-10  
**Author**: AI Assistant  
**Project**: TheDocAI (doc-chat-ai)
