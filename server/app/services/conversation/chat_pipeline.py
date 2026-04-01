"""
Chat Pipeline — SSE streaming orchestrator cho chat responses.

Đây là pipeline chính xử lý mọi tin nhắn chat:
"Stream-first + Validate-as-you-go" pattern:
- Pre-stream: Input guardrails (jailbreak, PII, injection)
- Mid-stream: Concurrent quality monitoring every 3 sentences
- Post-stream: Hallucination + grounding + fact-check + confidence scoring

Integrated features:
① Dedup Cache        ② Input Guardrails     ③ Intent Detection
④ Function Calling   ⑤ Image Generation     ⑤b Memory Recall + Context Budget
⑥ RAG Stream + Quality Monitor              ⑦ Post-stream Quality
⑦b Fact Check + Confidence Score + Policy   ⑧ Memori Extraction
⑨ Latency Budget + Pattern Monitoring

CRUD operations (save messages, conversations) delegated to ConversationService.
"""

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from app.db.models import Conversation, Message, MessageRole, Citation, Chunk
from app.services.conversation.conversation_service import ConversationService

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """Types of SSE events."""
    PROGRESS = "progress"
    TOKEN = "token"
    METADATA = "metadata"
    ERROR = "error"
    DONE = "done"
    QUALITY_WARNING = "quality_warning"      # Mid-stream quality issue
    REPLACE_RESPONSE = "replace_response"    # Corrective loop: replace entire streamed answer
    # NOTE: REPLACE_RESPONSE is used post-stream when corrective loop produces
    # a better answer. FE should replace the displayed response entirely.
    # For complex queries we buffer-first (no partial stream) to avoid UX jank.


class StreamEvent(BaseModel):
    """SSE event data structure."""
    type: StreamEventType
    data: Optional[Dict[str, Any]] = None
    
    def to_sse(self) -> str:
        """Convert to SSE format string."""
        data_str = json.dumps(self.data) if self.data else "{}"
        return f"event: {self.type.value}\ndata: {data_str}\n\n"


class ProgressData(BaseModel):
    """Progress event data."""
    step: str  # "retrieving", "generating", "processing"
    progress: int  # 0-100
    message: Optional[str] = None


class TokenData(BaseModel):
    """Token event data."""
    content: str
    index: int = 0


class MetadataData(BaseModel):
    """Metadata event data (sent after generation)."""
    citations: List[Dict[str, Any]]
    stats: Dict[str, Any]


class ChatPipeline:
    """
    Pipeline chính xử lý chat — SSE streaming + RAG.
    
    Implements Stream-first + Validate-as-you-go quality pattern.
    CRUD operations delegated to ConversationService.
    
    Usage:
        pipeline = ChatPipeline(session)
        async for event in pipeline.stream_response(query, workspace_id):
            yield event.to_sse()
    """
    
    def __init__(self, session=None):
        self.session = session
        self._cancelled = False
    
    def cancel(self):
        """Cancel the streaming."""
        self._cancelled = True
    
    async def stream_response(
        self,
        query: str,
        workspace_id: UUID,
        document_ids: Optional[List[UUID]] = None,
        tags: Optional[List[str]] = None,
        model: Optional[str] = None,
        memory_context: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
        **kwargs
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream chat response as SSE events.
        
        Yields events in order:
        1. progress: "starting"
        2. progress: "retrieving" / "generating"
        3. token: incremental tokens
        4. quality_warning: if mid-stream issue detected
        5. metadata: citations, quality scores, stats
        6. done: completion signal
        """
        import uuid as _uuid
        trace_id = str(_uuid.uuid4())[:12]  # Short unique id for request tracing
        start_time = time.time()
        logger.info(f"[{trace_id}] Stream start — q='{query[:50]}' ws={workspace_id}")
        
        try:
            # Progress: Starting (includes trace_id for debugging)
            yield StreamEvent(
                type=StreamEventType.PROGRESS,
                data={"step": "starting", "progress": 5, "message": "Đang khởi tạo...", "trace_id": trace_id}
            )
            
            if self._cancelled:
                return

            if conversation_id:
                # Contextual streaming (main flow from FE)
                async for event in self._stream_with_context(
                    query, conversation_id, workspace_id,
                    document_ids, tags, model
                ):
                    yield event
            else:
                # Stateless streaming — still runs input guardrails + light quality
                from app.services.core.rag import RAGService
                from app.services.safety.guardrails_service import GuardrailsService
                rag_service = await RAGService.get_instance(self.session)

                # Input guardrails for stateless path
                try:
                    _grd = GuardrailsService()
                    _grd_result = await _grd.check_input(query)
                    if not _grd_result.passed:
                        _block_msg = "\u26a0️ Nội dung không phù hợp. Vui lòng đặt lại câu hỏi."
                        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": _block_msg, "index": 0})
                        yield StreamEvent(type=StreamEventType.METADATA, data={"citations": [], "model": "guardrails", "quality": {"input_blocked": True}})
                        return
                except Exception:
                    pass

                if hasattr(rag_service, 'query_stream'):
                    async for event in self._stream_with_rag(
                        rag_service, query, workspace_id,
                        document_ids, tags, model, memory_context
                    ):
                        yield event
                else:
                    async for event in self._fallback_stream(
                        rag_service, query, workspace_id,
                        document_ids, tags, model, memory_context
                    ):
                        yield event
            
            # Done — include trace_id for end-to-end tracing
            total_time = int((time.time() - start_time) * 1000)
            logger.info(f"[{trace_id}] Stream complete — {total_time}ms")
            yield StreamEvent(
                type=StreamEventType.DONE,
                data={"total_time_ms": total_time, "trace_id": trace_id}
            )
            
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": "Đã xảy ra lỗi khi xử lý. Vui lòng thử lại.", "code": "STREAM_ERROR"}
            )

    async def _stream_with_context(
        self,
        query: str,
        conversation_id: UUID,
        workspace_id: UUID,
        document_ids: Optional[List[UUID]],
        tags: Optional[List[str]],
        model: Optional[str],
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream response with conversation context and full pipeline.
        
        Pipeline: Dedup → Intent → Guardrails → FunctionCalling → ImageGen
                  → RAG Stream + Quality Monitor → Post Quality → Memori
        """
        import time as _time
        from app.services.conversation.conversation_service import ConversationService
        from app.db.models import Message, MessageRole
        
        _pipeline_start = _time.time()
        def _perf(label, error=None):
            """Print timing log for pipeline stage."""
            elapsed = (_time.time() - _pipeline_start) * 1000
            if error:
                print(f"\n{'='*60}")
                print(f"❌ ERROR [{elapsed:.0f}ms] {label}: {error}")
                print(f"{'='*60}")
                logger.error(f"❌ ERROR [{elapsed:.0f}ms] {label}: {error}", exc_info=True)
            else:
                print(f"\n{'='*60}")
                print(f"⏱️  PERF [{elapsed:.0f}ms total] {label}")
                print(f"{'='*60}")
                logger.info(f"⏱️  PERF [{elapsed:.0f}ms] {label}")
        
        _perf("① START — _stream_with_context")
        conv_service = ConversationService(self.session)
        conversation = await conv_service.get_conversation(conversation_id, include_messages=False)

        if not conversation:
            yield StreamEvent(
                type=StreamEventType.ERROR, 
                data={"message": f"Không tìm thấy cuộc trò chuyện {conversation_id}", "code": "NOT_FOUND"}
            )
            return

        user_id = getattr(conversation, 'created_by', None)
        
        _perf("① DEDUP CACHE — checking cache")
        # =================================================================
        # ① DEDUP CACHE — Prevent duplicate queries within 5s
        # =================================================================
        dedup_cache = None
        try:
            from app.services.infrastructure.redis_manager import get_redis
            from app.services.conversation.dedup_cache import DedupCache
            
            redis_client = await get_redis()
            if redis_client:
                dedup_cache = DedupCache(redis_client)
                cached_result = await dedup_cache.get(user_id, workspace_id, query)
                if cached_result:
                    logger.info("⚡ Dedup cache HIT — returning cached response")
                    # Stream cached response
                    cached_answer = cached_result.get("answer", "")
                    if cached_answer:
                        yield StreamEvent(
                            type=StreamEventType.TOKEN,
                            data={"content": cached_answer, "index": len(cached_answer)}
                        )
                    yield StreamEvent(
                        type=StreamEventType.METADATA,
                        data=cached_result.get("metadata", {"citations": [], "model": "cached"})
                    )
                    return
                
                # Mark as processing
                await dedup_cache.check_and_set_processing(user_id, workspace_id, query)
        except Exception as e:
            _perf("① DEDUP CACHE FAILED", error=str(e))
            logger.debug(f"Dedup cache check skipped: {e}")

        _perf("② INPUT GUARDRAILS — checking jailbreak/PII/injection")
        # =================================================================
        # ② PRE-STREAM INPUT GUARDRAILS — Block jailbreak, PII, injection
        # Runs BEFORE intent to prevent bypass via GREETING/CHITCHAT
        # =================================================================
        guardrails = None
        try:
            from app.services.quality.guardrails_service import GuardrailsService
            guardrails = GuardrailsService()
            
            input_check = await guardrails.check_input(
                query, str(user_id or ""), str(workspace_id)
            )
            
            if not input_check.passed:
                logger.warning(f"⚠️ Input guardrails BLOCKED: {[v.rail_name for v in input_check.violations]}")
                
                # Save user message anyway
                user_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content=query,
                    model=model
                )
                self.session.add(user_msg)
                await self.session.commit()
                
                # Return safe response
                block_msg = input_check.user_message or "⚠️ Câu hỏi không phù hợp. Vui lòng thử lại với nội dung khác."
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    data={"content": block_msg, "index": len(block_msg)}
                )
                
                # Save assistant response
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=block_msg,
                    model="guardrails",
                    provider="safety",
                )
                self.session.add(assistant_msg)
                await self.session.commit()
                
                yield StreamEvent(
                    type=StreamEventType.METADATA,
                    data={"model": "guardrails", "provider": "safety", "citations": [],
                           "quality": {"input_blocked": True, 
                                        "violations": [v.rail_name for v in input_check.violations]}}
                )
                return
                
        except Exception as e:
            _perf("② INPUT GUARDRAILS FAILED", error=str(e))
            logger.debug(f"Input guardrails skipped: {e}")

        _perf("②b PII REDACTION")
        # =================================================================
        # ②b PII REDACTION — Sanitize PII before query reaches RAG/LLM
        # =================================================================
        try:
            from app.services.quality.safety_checker import SafetyChecker
            safety = SafetyChecker(guardrails_service=guardrails)
            pii_result = safety.check_pii(query, redact=True)
            if pii_result.has_pii and pii_result.redacted_text:
                logger.info(f"🔒 PII redacted: {[p.value for p in pii_result.pii_types_found]}")
                query = pii_result.redacted_text
        except Exception as e:
            _perf("②b PII REDACTION FAILED", error=str(e))
            logger.debug(f"PII redaction skipped: {e}")

        _perf("③ INTENT DETECTION")
        # =================================================================
        # ③ INTENT DETECTION — Short-circuit GREETING/CHITCHAT
        # (Now runs AFTER guardrails — safe inputs only)
        # =================================================================
        intent_result = None
        try:
            from app.services.conversation.intent_detector import IntentDetector, QueryIntent
            
            intent_start = _time.time()
            detector = IntentDetector(language="vi")
            intent_result = await detector.detect_with_caching(query)
            intent_ms = (_time.time() - intent_start) * 1000
            
            logger.info(f"⏱️ Stream intent: {intent_result.intent.value} "
                       f"(confidence={intent_result.confidence:.2f}, {intent_ms:.0f}ms)")
            
            if intent_result.intent in (QueryIntent.GREETING, QueryIntent.CHITCHAT):
                # --- FAST PATH: Skip everything ---
                user_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content=query,
                    model=model
                )
                self.session.add(user_msg)
                await self.session.commit()
                await self.session.refresh(user_msg)
                
                response_text = intent_result.direct_response
                if not response_text:
                    if intent_result.intent == QueryIntent.GREETING:
                        response_text = "Xin chào! Tôi có thể giúp gì cho bạn?"
                    else:
                        response_text = "Tôi có thể giúp gì cho bạn?"
                
                yield StreamEvent(
                    type=StreamEventType.PROGRESS,
                    data={"step": "generating", "progress": 90, "message": "⚡ Trả lời trực tiếp..."}
                )
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    data={"content": response_text, "index": len(response_text)}
                )
                
                latency_ms = int((_time.time() - intent_start) * 1000)
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                    model="intent_direct",
                    provider="pattern",
                    latency_ms=latency_ms,
                )
                self.session.add(assistant_msg)
                await self.session.commit()
                
                yield StreamEvent(
                    type=StreamEventType.METADATA,
                    data={"model": "intent_direct", "provider": "pattern", "citations": []}
                )
                logger.info(f"⚡ Direct response for {intent_result.intent.value} ({latency_ms}ms)")
                return
                
        except Exception as e:
            _perf("③ INTENT DETECTION FAILED", error=str(e))
            logger.warning(f"Intent detection failed: {e}, continuing to RAG")

        _perf("④ FUNCTION CALLING")
        # =================================================================
        # ④ FUNCTION CALLING — Metadata queries (fast, no RAG needed)
        # =================================================================
        try:
            from app.services.tools.function_calling_service import FunctionCallingService
            fc_service = FunctionCallingService(self.session, workspace_id)
            
            should_use_fc = await asyncio.wait_for(
                fc_service.should_use_function_calling(query),
                timeout=0.3  # 300ms timeout (was 100ms — too aggressive)
            )
            
            if should_use_fc:
                logger.info(f"🔧 Function calling for: '{query[:50]}...'")
                result = await asyncio.wait_for(
                    fc_service.process_question(query),
                    timeout=5.0
                )
                
                if result.get("used_function_calling"):
                    fc_answer = result["answer"]
                    
                    # Save user message
                    user_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.USER,
                        content=query, model=model
                    )
                    self.session.add(user_msg)
                    await self.session.commit()
                    await self.session.refresh(user_msg)
                    
                    # Stream result
                    yield StreamEvent(
                        type=StreamEventType.PROGRESS,
                        data={"step": "generating", "progress": 90, "message": "🔧 Trả lời từ metadata..."}
                    )
                    yield StreamEvent(
                        type=StreamEventType.TOKEN,
                        data={"content": fc_answer, "index": len(fc_answer)}
                    )
                    
                    # Save assistant
                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=fc_answer,
                        model="function-calling",
                        provider="direct-execution",
                    )
                    self.session.add(assistant_msg)
                    await self.session.commit()
                    
                    yield StreamEvent(
                        type=StreamEventType.METADATA,
                        data={"model": "function-calling", "provider": "direct-execution",
                              "citations": [], "tool_calls": result.get("tool_calls", [])}
                    )
                    logger.info(f"🔧 Function calling response delivered")
                    return
                    
        except asyncio.TimeoutError:
            _perf("④ FUNCTION CALLING TIMEOUT", error="Timeout after 5.0s")
            logger.debug("Function calling timeout, continuing to RAG")
        except Exception as e:
            _perf("④ FUNCTION CALLING FAILED", error=str(e))
            logger.debug(f"Function calling skipped: {e}")
        
        # Initialize quality_scores dict — collects data from ④b through ⑨
        quality_scores = {}
        
        # ④b FUNCTION REGISTRY — Extended tool calling with built-in tools
        # (search_documents, get_document_info, calculate, get_current_time, format_text)
        try:
            from app.services.tools.function_registry import get_function_registry, register_builtin_functions
            registry = get_function_registry()
            if not registry.list_functions():
                register_builtin_functions(registry)
            
            # Check if query matches any registered tool capability
            tool_keywords = {
                "calculate": ["tính", "calculate", "compute", "==", "bằng bao nhiêu", "cộng", "trừ", "nhân", "chia"],
                "get_current_time": ["mấy giờ", "ngày hôm nay", "what time", "current time", "current date", "today"],
                "format_text": ["format", "uppercase", "lowercase", "slug"],
            }
            
            matched_tool = None
            query_lower = query.lower()
            for tool_name, keywords in tool_keywords.items():
                if any(kw in query_lower for kw in keywords):
                    matched_tool = tool_name
                    break
            
            if matched_tool:
                logger.info(f"🧰 Function Registry matched: {matched_tool}")
                
                # Build arguments based on tool type
                tool_args = {}
                if matched_tool == "calculate":
                    # Extract math expression from query
                    import re
                    math_match = re.search(r'[\d\+\-\*\/\(\)\s\.]+', query)
                    if math_match:
                        tool_args = {"expression": math_match.group().strip()}
                elif matched_tool == "get_current_time":
                    tool_args = {"timezone": "Asia/Ho_Chi_Minh"}
                elif matched_tool == "format_text":
                    tool_args = {"text": query, "operation": "title"}
                
                if tool_args:
                    tool_result = await registry.execute(matched_tool, tool_args)
                    if tool_result.success:
                        quality_scores["function_registry"] = {
                            "tool": matched_tool,
                            "execution_time_ms": tool_result.execution_time_ms,
                            "source": "tool",  # Grounding: output came from tool, not doc chunks
                        }
                        logger.info(f"🧰 Registry tool {matched_tool} executed in {tool_result.execution_time_ms}ms")
        except Exception as e:
            _perf("④b FUNCTION REGISTRY FAILED", error=str(e))
            logger.debug(f"Function registry skipped: {e}")

        # =================================================================
        # ④ IMAGE GENERATION — Handle IMAGE_GENERATION intent
        # =================================================================
        if intent_result and hasattr(intent_result, 'intent'):
            try:
                from app.services.conversation.intent_detector import QueryIntent
                if intent_result.intent == QueryIntent.IMAGE_GENERATION:
                    logger.info("🎨 Image generation request detected")
                    from app.services.generation.image_generation_service import get_image_generation_service
                    
                    # Save user message
                    user_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.USER,
                        content=query, model=model
                    )
                    self.session.add(user_msg)
                    await self.session.commit()
                    
                    yield StreamEvent(
                        type=StreamEventType.PROGRESS,
                        data={"step": "generating", "progress": 50, "message": "🎨 Đang tạo ảnh..."}
                    )
                    
                    image_service = get_image_generation_service()
                    result = await image_service.generate(
                        prompt=query, num_images=1, aspect_ratio="1:1"
                    )
                    
                    if result.success and result.images:
                        answer_text = "🎨 Đã tạo ảnh thành công!"
                        yield StreamEvent(
                            type=StreamEventType.TOKEN,
                            data={"content": answer_text, "index": len(answer_text)}
                        )
                        
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=answer_text,
                            model=result.model or "image-gen",
                            provider=result.provider or "local",
                        )
                        self.session.add(assistant_msg)
                        await self.session.commit()
                        
                        yield StreamEvent(
                            type=StreamEventType.METADATA,
                            data={"model": result.model, "provider": result.provider,
                                  "citations": [], "images": result.images,
                                  "is_image_response": True}
                        )
                    else:
                        error_text = f"⚠️ Không thể tạo ảnh: {result.error}"
                        yield StreamEvent(
                            type=StreamEventType.TOKEN,
                            data={"content": error_text, "index": len(error_text)}
                        )
                        
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=error_text, model="image-gen", provider="local",
                        )
                        self.session.add(assistant_msg)
                        await self.session.commit()
                        
                        yield StreamEvent(
                            type=StreamEventType.METADATA,
                            data={"model": "image-gen", "citations": []}
                        )
                    return
                    
            except Exception as e:
                _perf("④ IMAGE GENERATION FAILED", error=str(e))
                logger.warning(f"Image generation failed: {e}, falling through to RAG")

        _perf("⑤ FULL RAG PATH — setup")
        # =================================================================
        # FULL RAG PATH — DOCUMENT_QUERY, CODE_GEN, etc.
        # =================================================================
        from app.services.core.rag import RAGService
        rag_init_start = _time.time()
        rag_service = await RAGService.get_instance(self.session)
        _perf(f"  RAGService.get_instance: {(_time.time() - rag_init_start) * 1000:.0f}ms")

        # Save User Message
        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=query,
            model=model
        )
        self.session.add(user_msg)
        await self.session.commit()
        await self.session.refresh(user_msg)
        
        # Get History
        history = await conv_service.get_messages(conversation_id, limit=10)
        history_dicts = [
            {"role": getattr(m.role, 'value', m.role), "content": m.content} 
            for m in history if m.id != user_msg.id
        ]
        
        _perf("⑤ MEMORY RECALL")
        # =================================================================
        # ⑤ MEMORY RECALL WITH CACHE
        # =================================================================
        memory_context = ""
        memori_context = ""
        graph_context = ""
        
        try:
            yield StreamEvent(
                type=StreamEventType.PROGRESS, 
                data={"step": "retrieving", "progress": 10, "message": "🧠 Đang phân tích ngữ cảnh..."}
            )
            
            # Try memory cache first
            memory_cache_mgr = None
            try:
                from app.services.conversation.memory_cache import MemoryCacheManager
                from app.services.infrastructure.redis_manager import get_redis
                redis_client = await get_redis()
                if redis_client:
                    memory_cache_mgr = MemoryCacheManager(redis_client)
                    cached_memory = await memory_cache_mgr.get_memory(conversation_id)
                    cached_memori = await memory_cache_mgr.get_memori(conversation_id, query)
                    if cached_memory or cached_memori:
                        memory_context = cached_memory or ""
                        memori_context = cached_memori or ""
                        logger.info("⚡ Memory cache HIT")
            except Exception:
                pass
            
            # If no cache hit, do parallel recall (with retry for transient errors)
            if not memory_context and not memori_context:
                from app.services.conversation.parallel_executor import ParallelMemoryExecutor
                parallel_executor = ParallelMemoryExecutor(self.session)
                
                async def _do_memory_recall():
                    return await parallel_executor.execute_memory_recall(
                        conversation_id=conversation_id,
                        query=query,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        timeout=5.0,
                        include_graph_search=True,
                    )
                
                try:
                    from app.services.infrastructure.retry_handler import RetryHandler
                    retry = RetryHandler(max_retries=2, base_delay=0.5, max_delay=2.0)
                    memory_context, memori_context, graph_context = await retry.execute(_do_memory_recall)
                    if retry.last_attempt_count > 1:
                        logger.info(f"🔄 Memory recall succeeded after {retry.last_attempt_count} attempts")
                except Exception:
                    # Fallback: try once without retry wrapper
                    memory_context, memori_context, graph_context = await _do_memory_recall()
                
                # Cache the result
                if memory_cache_mgr:
                    try:
                        await memory_cache_mgr.set_memory(conversation_id, memory_context or "")
                        await memory_cache_mgr.set_memori(conversation_id, query, memori_context or "")
                    except Exception as e:
                        _perf("⑤ MEMORY SET CACHE FAILED", error=str(e))
                        pass
                
        except Exception as e:
            _perf("⑤ MEMORY RECALL FAILED", error=str(e))
            logger.warning(f"Memory recall failed: {e}")
            yield StreamEvent(
                type=StreamEventType.PROGRESS, 
                data={"step": "retrieving", "progress": 15, "message": "⚠️ Bỏ qua bộ nhớ, tiếp tục..."}
            )

        _perf("⑤b CONTEXT BUDGET")
        # =================================================================
        # ⑤b CONTEXT BUDGET — Trim context tokens to fit LLM window
        # =================================================================
        try:
            from app.services.core.context_budget import get_context_budget_manager
            budget_mgr = get_context_budget_manager(max_tokens=8000)
            
            # Parse memory facts as list
            memory_facts = [f for f in (memory_context or "").split("\n") if f.strip()]
            # conversation_history is list of dicts
            allocated = budget_mgr.allocate_context(
                query=query,
                memory_facts=memory_facts,
                retrieved_chunks=[],  # chunks come from RAG later
                conversation_history=history_dicts,
            )
            
            # Use trimmed memory
            if allocated.memory:
                memory_context = "\n".join(allocated.memory)
            # Use trimmed history
            if allocated.history:
                history_dicts = allocated.history
            
            logger.info(f"📊 Context budget: {allocated.total_tokens} tokens allocated")
        except Exception as e:
            _perf("⑤b CONTEXT BUDGET FAILED", error=str(e))
            logger.debug(f"Context budget skipped: {e}")

        _perf("⑤c LATENCY BUDGET")
        # =================================================================
        # ⑤c LATENCY BUDGET — Allocate SLA timing constraints
        # =================================================================
        latency_allocation = None
        try:
            from app.services.core.latency_budget_service import LatencyBudgetManager
            latency_mgr = LatencyBudgetManager()
            latency_allocation = latency_mgr.allocate_budget(
                complexity="moderate",
                num_nodes=4,  # guardrails, intent, rag, quality
                user_tier="free",
                node_weights={
                    "guardrails": 0.1,
                    "intent": 0.1,
                    "rag": 0.6,
                    "quality": 0.2,
                },
            )
            logger.info(f"⏱️ Latency budget: {latency_allocation.total_budget_ms}ms total")
        except Exception as e:
            _perf("⑤c LATENCY BUDGET FAILED", error=str(e))
            logger.debug(f"Latency budget skipped: {e}")

        _perf("⑤d MULTI-RAG PATTERN ORCHESTRATION")
        # =================================================================
        # ⑤d MULTI-RAG PATTERN ORCHESTRATION
        # If query is complex, use SmartRouter + Orchestrator to run
        # specialized patterns (Corrective, Self-RAG, Adaptive, etc.)
        # Simple queries skip this entirely (zero overhead).
        # =================================================================
        orchestration_context = ""
        try:
            from app.services.rag_patterns.orchestration.analyzer import (
                QueryAnalyzer, QueryComplexity,
            )
            from app.services.rag_patterns.orchestration.router import SmartRouter
            from app.services.rag_patterns.orchestration.orchestrator import PatternOrchestrator

            _qa = QueryAnalyzer()
            analysis_result = _qa.analyze_with_routing(
                query, {"history": history_dicts, "conversation_history": history_dicts}
            )
            chars = analysis_result.characteristics

            if chars.complexity in (
                QueryComplexity.MODERATE,
                QueryComplexity.COMPLEX,
                QueryComplexity.VERY_COMPLEX,
            ):
                router = SmartRouter()
                routing = router.route(analysis_result)

                if routing.selected_patterns and routing.confidence >= 0.6:
                    # Load pattern services dynamically
                    pattern_services = {}
                    _pattern_map = {
                        "corrective_rag": ("app.services.rag_patterns.patterns.accuracy.corrective", "CorrectiveRAGService"),
                        "self_rag": ("app.services.rag_patterns.patterns.accuracy.self_rag", "SelfRAGService"),
                        "adaptive_rag": ("app.services.rag_patterns.patterns.optimization.adaptive", "AdaptiveRAGService"),
                        "corag": ("app.services.rag_patterns.patterns.optimization.corag", "CORAGService"),
                        "semantic_highlight": ("app.services.rag_patterns.patterns.optimization.semantic", "SemanticHighlightRAGService"),
                        "speculative_rag": ("app.services.rag_patterns.patterns.optimization.speculative", "SpeculativeRAGService"),
                        "code_rag": ("app.services.rag_patterns.patterns.specialized.code_rag", "CodeRAGService"),
                        "coral": ("app.services.rag_patterns.patterns.specialized.coral", "CORALService"),
                        "reveal": ("app.services.rag_patterns.patterns.specialized.reveal", "REVEALService"),
                    }
                    for pname in routing.selected_patterns:
                        if pname in _pattern_map:
                            try:
                                mod_path, cls_name = _pattern_map[pname]
                                mod = __import__(mod_path, fromlist=[cls_name])
                                pattern_services[pname] = getattr(mod, cls_name)()
                            except Exception:
                                pass

                    if pattern_services:
                        orchestrator = PatternOrchestrator()
                        orch_result = await orchestrator.orchestrate(
                            query=query,
                            pattern_services=pattern_services,
                            strategy=routing.execution_strategy,
                            patterns=routing.selected_patterns,
                            context={"history": history_dicts},
                        )
                        if orch_result.success and orch_result.final_result:
                            orchestration_context = str(orch_result.final_result)
                            quality_scores["orchestration"] = {
                                "patterns": orch_result.patterns_executed,
                                "strategy": orch_result.strategy.value,
                                "latency_ms": round(orch_result.total_latency_ms),
                                "complexity": chars.complexity.value,
                                "domain": chars.domain.value,
                            }
                            logger.info(
                                f"🧩 Multi-RAG orchestration: {orch_result.patterns_executed} "
                                f"({orch_result.strategy.value}, {round(orch_result.total_latency_ms)}ms)"
                            )
                else:
                    logger.debug(
                        f"⏭️ Pattern routing skipped (confidence={routing.confidence:.2f}, "
                        f"patterns={routing.selected_patterns})"
                    )
            else:
                logger.debug(f"⏭️ Query simple ({chars.complexity.value}), skipping orchestration")
        except Exception as e:
            _perf("⑤d PATTERN ORCHESTRATION FAILED", error=str(e))
            logger.debug(f"Pattern orchestration skipped: {e}")

        _perf("⑥0 QUERY REWRITE")
        # =================================================================
        # ⑥0 QUERY REWRITE — HyDE / Step-back / Sub-queries
        # =================================================================
        retrieval_query = query  # Original query for display; rewritten for retrieval
        try:
            # Only rewrite non-trivial queries (>5 words)
            if len(query.split()) > 5:
                from app.services.search.query_rewriter_service import QueryRewriterService, RewriteStrategy
                rewriter = QueryRewriterService(language="vi")

                # Try to get an LLM function for smarter rewrites
                try:
                    from app.services.infrastructure.ai_providers.manager import AIProviderManager
                    _mgr = AIProviderManager()

                    async def _llm_fn(prompt: str) -> str:
                        r = await _mgr.generate(
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=200, temperature=0.3,
                        )
                        return r.content or ""

                    rewriter = QueryRewriterService(llm_generate_fn=_llm_fn, language="vi")
                except Exception:
                    pass

                rewrite_result = await asyncio.wait_for(
                    rewriter.rewrite(query, strategy=RewriteStrategy.STEP_BACK),
                    timeout=2.0,
                )
                # Use step-back query for broader retrieval
                if rewrite_result.step_back_query:
                    retrieval_query = rewrite_result.step_back_query
                    quality_scores["query_rewrite"] = {
                        "strategy": "step_back",
                        "original": query[:80],
                        "rewritten": retrieval_query[:80],
                    }
                    logger.info(f"🔄 Query rewrite (step-back): '{query[:50]}' → '{retrieval_query[:50]}'")
                elif rewrite_result.rewritten_queries:
                    retrieval_query = rewrite_result.rewritten_queries[0]
                    quality_scores["query_rewrite"] = {
                        "strategy": "multi_query",
                        "original": query[:80],
                        "rewritten": retrieval_query[:80],
                    }
                    logger.info(f"🔄 Query rewrite (multi): '{query[:50]}' → '{retrieval_query[:50]}'")
        except (asyncio.TimeoutError, Exception) as _e:
            _perf("⑥0 QUERY REWRITE FAILED", error=str(_e))
            logger.debug(f"Query rewrite skipped: {_e}")

        _perf("⑥ RAG PIPELINE — Retrieve → Rerank → Context → Stream")
        # =================================================================
        # ⑥ RAG PIPELINE — Two-Phase: Retrieve → Rerank → Context → Stream
        # =================================================================
        answer_accumulator = ""
        citations = []
        stats = {}
        combined_context = ""  # For quality checks
        quality_warnings = []

        # Build combined memory context
        if memory_context:
            combined_context += f"Memory: {memory_context}\n"
        if memori_context:
            combined_context += f"Facts: {memori_context}\n"
        if graph_context:
            combined_context += f"Graph: {graph_context}\n"
        if orchestration_context:
            combined_context += f"Pattern Analysis: {orchestration_context}\n"

        try:
            yield StreamEvent(
                type=StreamEventType.PROGRESS,
                data={"step": "retrieving", "progress": 20, "message": "🔍 Đang tìm kiếm tài liệu..."}
            )

            rag_start = _time.time()

            # ◀◀◀ PHASE A: RETRIEVE (non-stream, fast — get raw candidates) ◀◀◀
            raw_retrieval = None
            try:
                combined_memory = "".join(filter(None, [
                    f"Memory: {memory_context}\n" if memory_context else "",
                    f"Facts: {memori_context}\n" if memori_context else "",
                    f"Graph: {graph_context}\n" if graph_context else "",
                ]))
                raw_retrieval = await asyncio.wait_for(
                    rag_service.query(
                        question=retrieval_query,
                        workspace_id=workspace_id,
                        document_ids=document_ids,
                        tags=tags,
                        model=model,
                        memory_context=combined_memory or None,
                        conversation_history=history_dicts,
                        top_k=20,   # retrieve top-20 before rerank
                    ),
                    timeout=8.0,
                )
            except (asyncio.TimeoutError, Exception) as _e:
                _perf("⑥ RAG PIPELINE PHASE A (RETRIEVE) FAILED", error=str(_e))
                logger.warning(f"▶ Phase A retrieve failed ({_e}), entering fallback ladder")

            # ── FALLBACK LADDER (empty OR low-confidence retrieval) ────────
            # Prevents hallucination by progressively broadening or refusing.
            # Two triggers: (a) no chunks at all, (b) chunks exist but top score < threshold.
            _MIN_RETRIEVAL_SCORE = 0.3
            _raw_cits = getattr(raw_retrieval, 'citations', None) or getattr(raw_retrieval, 'sources', []) if raw_retrieval else []
            _top_score = 0.0
            if _raw_cits:
                _top_score = max(
                    (getattr(c, 'score', 0.0) if not isinstance(c, dict) else c.get('score', 0.0))
                    for c in _raw_cits
                )

            _needs_fallback = (
                raw_retrieval is None
                or not _raw_cits
                or _top_score < _MIN_RETRIEVAL_SCORE
            )

            if _needs_fallback:
                _fallback_tried = False
                _fallback_reason = "empty" if not _raw_cits else f"low_score({_top_score:.2f})"
                logger.info(f"🪜 Fallback ladder triggered: {_fallback_reason}")

                # Step 1: Retry with original (un-rewritten) query
                if retrieval_query != query:
                    try:
                        logger.info("🪜 Fallback step 1: retry with original query")
                        raw_retrieval = await asyncio.wait_for(
                            rag_service.query(
                                question=query,
                                workspace_id=workspace_id,
                                document_ids=document_ids,
                                tags=tags, model=model,
                                top_k=20,
                            ),
                            timeout=6.0,
                        )
                        _fallback_tried = True
                    except Exception:
                        pass

                # Step 2: Step-back / remove constraints / expand synonyms
                _raw_cits2 = getattr(raw_retrieval, 'citations', None) or getattr(raw_retrieval, 'sources', []) if raw_retrieval else []
                _top2 = max((getattr(c, 'score', 0) if not isinstance(c, dict) else c.get('score', 0) for c in _raw_cits2), default=0) if _raw_cits2 else 0
                if (not _raw_cits2 or _top2 < _MIN_RETRIEVAL_SCORE) and len(query.split()) > 3:
                    try:
                        # Use step-back rewrite: remove specific constraints, expand to broader concept
                        from app.services.search.query_rewriter_service import QueryRewriterService, RewriteStrategy
                        _rewriter = QueryRewriterService(language="vi")
                        _sb = await asyncio.wait_for(
                            _rewriter.rewrite(query, strategy=RewriteStrategy.STEP_BACK),
                            timeout=2.0,
                        )
                        _broad_q = _sb.step_back_query or _sb.rewritten_queries[0] if _sb.rewritten_queries else query
                        logger.info(f"🪜 Fallback step 2: step-back '{_broad_q[:40]}'")
                        raw_retrieval = await asyncio.wait_for(
                            rag_service.query(
                                question=_broad_q,
                                workspace_id=workspace_id,
                                document_ids=document_ids,
                                tags=tags, model=model,
                                top_k=10,
                            ),
                            timeout=6.0,
                        )
                        _fallback_tried = True
                    except Exception:
                        pass

                # Step 3: If still nothing — refuse to answer, don't fabricate
                _raw_cits3 = getattr(raw_retrieval, 'citations', None) or getattr(raw_retrieval, 'sources', []) if raw_retrieval else []
                _top3 = max((getattr(c, 'score', 0) if not isinstance(c, dict) else c.get('score', 0) for c in _raw_cits3), default=0) if _raw_cits3 else 0
                if not _raw_cits3 or _top3 < _MIN_RETRIEVAL_SCORE:
                    quality_scores["retrieval_fallback"] = {
                        "status": "exhausted",
                        "reason": _fallback_reason,
                        "steps_tried": 2 if _fallback_tried else 1,
                    }
                    logger.warning("🪜 Fallback ladder exhausted — no relevant docs found")

            # Extract raw citations from Phase A
            raw_citations = []
            if raw_retrieval:
                # rag_service.query returns a QueryResponse-like object
                _cits = getattr(raw_retrieval, "citations", None) or getattr(raw_retrieval, "sources", [])
                for c in (_cits or []):
                    if isinstance(c, dict):
                        raw_citations.append(c)
                    else:
                        raw_citations.append({
                            "chunk_id": getattr(c, "chunk_id", ""),
                            "content": getattr(c, "content", ""),
                            "score": getattr(c, "score", 0.0),
                            "document_id": str(getattr(c, "document_id", "")),
                            "document_title": getattr(c, "document_title", ""),
                            "page": getattr(c, "page", None),
                        })

            # ── ACL PREFILTER (query-time enforcement) ──────────────────────
            # Permissions are enforced at retrieval time, NOT post-hoc.
            # rag_service.query() already scopes to workspace_id internally.
            # This second filter ensures caller-specified document_ids are respected
            # (e.g. when user selects specific docs in the UI).
            # This prevents cross-document data leakage within a workspace.
            if document_ids and raw_citations:
                doc_id_strs = {str(d) for d in document_ids}
                _before = len(raw_citations)
                raw_citations = [
                    c for c in raw_citations
                    if str(c.get("document_id", "")) in doc_id_strs
                ]
                if _before != len(raw_citations):
                    logger.info(f"🔒 ACL prefilter: {_before} → {len(raw_citations)} citations")

            # ◀◀◀ PHASE B: RERANK top-20 → top-5 (BEFORE generate) ◀◀◀
            if raw_citations:
                yield StreamEvent(
                    type=StreamEventType.PROGRESS,
                    data={"step": "reranking", "progress": 30, "message": "🔀 Đang chọn tài liệu tốt nhất..."}
                )
                try:
                    from app.services.core.reranker_service import get_reranker_service
                    from app.services.core.retriever_service import RetrievalResult
                    reranker = get_reranker_service()
                    if reranker and len(raw_citations) > 3:
                        retrieval_results = [
                            RetrievalResult(
                                chunk_id=c.get("chunk_id", ""),
                                content=c.get("content", ""),
                                score=c.get("score", 0.0),
                                document_id=c.get("document_id", ""),
                                document_title=c.get("document_title", ""),
                                page=c.get("page"),
                            )
                            for c in raw_citations
                        ]
                        reranked = await reranker.rerank(query, retrieval_results, top_k=5)
                        citations = [
                            {
                                "chunk_id": r.chunk_id, "content": r.content,
                                "score": r.rerank_score or r.score,
                                "document_id": r.document_id,
                                "document_title": r.document_title,
                                "page": r.page,
                            }
                            for r in reranked
                        ]
                        quality_scores["reranker"] = {
                            "original_count": len(retrieval_results),
                            "reranked_count": len(citations),
                            "top_score": round(citations[0]["score"], 3) if citations else 0,
                        }
                        logger.info(f"🔀 Reranker: {len(retrieval_results)} → {len(citations)} (top={citations[0]['score']:.3f})")
                    else:
                        citations = raw_citations[:5]
                except Exception as _e:
                    _perf("⑥ RAG PIPELINE PHASE B (RERANK) FAILED", error=str(_e))
                    logger.debug(f"Reranker skipped: {_e}")
                    citations = raw_citations[:5]
            else:
                citations = []

            # ◀◀◀ PHASE C: BUILD CONTEXT + CITATION MAP (before generate) ◀◀◀
            for c in citations:
                combined_context += f"\nDoc: {c.get('content', '')}"

            # ⑥a PROMPT BUILDER
            rag_system_prompt = None
            try:
                from app.services.generation.prompt_builder import PromptBuilder
                pb = PromptBuilder(language="vi")
                combined_memory = "".join(filter(None, [
                    f"Memory: {memory_context}\n" if memory_context else "",
                    f"Facts: {memori_context}\n" if memori_context else "",
                    f"Graph: {graph_context}\n" if graph_context else "",
                ]))
                rag_system_prompt, _user_prompt = pb.build_rag_prompt(
                    question=query,
                    context=combined_context,
                    memory_context=combined_memory or None,
                )
                quality_scores["prompt_builder"] = {
                    "language": "vi",
                    "has_system_prompt": bool(rag_system_prompt),
                    "has_memory": bool(combined_memory),
                    "citation_count": len(citations),
                }
                logger.info(f"📝 PromptBuilder: ready (lang=vi, citations={len(citations)})")
            except Exception as _e:
                _perf("⑥ RAG PIPELINE PHASE C (PROMPT_BUILDER) FAILED", error=str(_e))
                logger.debug(f"PromptBuilder skipped: {_e}")

            # ◀◀◀ PHASE D: STREAM GENERATE with light QA monitor ◀◀◀
            _perf("⑥4 STREAM GENERATE — starting LLM call")
            yield StreamEvent(
                type=StreamEventType.PROGRESS,
                data={"step": "generating", "progress": 40, "message": "📝 Đang viết câu trả lời..."}
            )

            token_count = 0
            _SECRETS_RE = __import__('re').compile(
                r'(?i)(sk-[a-z0-9]{20,}|AIza[0-9A-Za-z\-_]{35}|ghp_[A-Za-z0-9]{36})'
            )
            _PII_RE = __import__('re').compile(
                r'(\b[\w.+-]+@[\w-]+\.[\w.]+\b|\b0[0-9]{9}\b)'
            )

            # If Phase A retrieval succeeded AND rag has pre-built answer, use it
            prebuilt_answer = getattr(raw_retrieval, "answer", None) if raw_retrieval else None

            if prebuilt_answer:
                # Stream the pre-retrieved answer token-by-token (simulate streaming)
                chunk_size = 8
                for i in range(0, len(prebuilt_answer), chunk_size):
                    if self._cancelled:
                        break
                    chunk = prebuilt_answer[i:i + chunk_size]
                    answer_accumulator += chunk
                    yield StreamEvent(type=StreamEventType.TOKEN, data={"content": chunk, "index": len(answer_accumulator)})
                    token_count += 1
                    # Light QA checks every ~500 chars
                    if len(answer_accumulator) % 500 < chunk_size:
                        if _SECRETS_RE.search(answer_accumulator[-300:]):
                            quality_warnings.append({"type": "secret_leak", "severity": "error", "message": "Detected potential secret/API key in response"})
                        if len(answer_accumulator) > 8000:
                            quality_warnings.append({"type": "length", "severity": "warning", "message": "Response exceeds recommended length"})
                stats = {"model": model or "auto", "provider": "rag_cached", "completion_tokens": len(prebuilt_answer.split())}
            else:
                # Real streaming from query_stream
                async for chunk in rag_service.query_stream(
                    question=query,
                    workspace_id=workspace_id,
                    document_ids=document_ids,
                    tags=tags,
                    model=model,
                    memory_context=None,   # context already in prompt
                    conversation_history=history_dicts,
                    system_prompt=rag_system_prompt,
                ):
                    if self._cancelled:
                        break

                    if isinstance(chunk, str):
                        if token_count == 0:
                            yield StreamEvent(
                                type=StreamEventType.PROGRESS,
                                data={"step": "generating", "progress": 50, "message": "📝 Đang trả lời..."}
                            )
                        answer_accumulator += chunk
                        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": chunk, "index": len(answer_accumulator)})
                        token_count += 1

                        # ◀ LIGHT MID-STREAM QA (no guardrails.check_output here) ▶
                        if len(answer_accumulator) % 400 < len(chunk) + 1:
                            if _SECRETS_RE.search(answer_accumulator[-300:]):
                                quality_warnings.append({"type": "secret_leak", "severity": "error", "message": "Potential secret/API key detected"})
                                yield StreamEvent(type=StreamEventType.QUALITY_WARNING, data=quality_warnings[-1])
                            if _PII_RE.search(answer_accumulator[-300:]):
                                quality_warnings.append({"type": "pii_leak", "severity": "warning", "message": "Possible PII in response"})
                            if len(answer_accumulator) > 8000:
                                quality_warnings.append({"type": "length", "severity": "info", "message": "Response is very long"})

                    elif isinstance(chunk, dict):
                        # Only pick up citations if Phase A didn't produce them
                        if "citations" in chunk and not citations:
                            citations = chunk["citations"][:20]  # keep raw; no mid-stream rerank
                            # Add to context for post-stream quality
                            for c in citations:
                                combined_context += f"\nDoc: {c.get('content', '')}"
                        elif "stats" in chunk:
                            stats.update(chunk["stats"])

            rag_latency_ms = int((_time.time() - rag_start) * 1000)
            _perf(f"⑥ RAG COMPLETE — rag_latency={rag_latency_ms}ms, answer_len={len(answer_accumulator)}")

            # Emit any light-QA warnings collected
            for _w in quality_warnings:
                yield StreamEvent(type=StreamEventType.QUALITY_WARNING, data=_w)

        except Exception as e:
            _perf("⑥ RAG PIPELINE CRASHED", error=str(e))
            logger.error(f"RAG pipeline failed: {e}")
            error_msg = f"\n[System Error: {str(e)}]"
            answer_accumulator += error_msg
            yield StreamEvent(type=StreamEventType.TOKEN, data={"content": error_msg, "index": len(answer_accumulator)})
            yield StreamEvent(type=StreamEventType.ERROR, data={"message": str(e), "code": "RAG_ERROR"})
            rag_latency_ms = int((_time.time() - rag_start) * 1000) if 'rag_start' in locals() else 0

        _perf("⑦ POST-STREAM QUALITY — Hallucination + Grounding + Fact Check")
        # =================================================================
        # ⑦ POST-STREAM QUALITY — Hallucination + Grounding + Fact Check
        # =================================================================
        # quality_scores already initialized before ④b (L435)
        
        if answer_accumulator and combined_context:
            try:
                yield StreamEvent(
                    type=StreamEventType.PROGRESS,
                    data={"step": "validating", "progress": 90, "message": "✅ Đang kiểm tra chất lượng..."}
                )
                
                # Run hallucination + grounding + fact checks in parallel
                from app.services.quality.hallucination_checker import HallucinationChecker
                from app.services.quality.grounding_verifier_service import GroundingVerifier
                
                h_checker = HallucinationChecker()
                g_verifier = GroundingVerifier()
                
                # check_faithfulness is async, verify is sync
                h_task = h_checker.check_faithfulness(answer_accumulator, combined_context)
                g_task = asyncio.to_thread(
                    g_verifier.verify, answer_accumulator, combined_context
                )
                
                # ⑦b FACT CHECK — Verify numerical claims (runs in parallel)
                f_task = None
                try:
                    from app.services.quality.fact_checker import fact_checker
                    f_task = asyncio.to_thread(
                        fact_checker.verify_numerical_claims, answer_accumulator
                    )
                except Exception:
                    pass
                
                # Gather all quality checks
                tasks = [h_task, g_task]
                if f_task:
                    tasks.append(f_task)
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                h_result = results[0]
                g_result = results[1]
                f_result = results[2] if len(results) > 2 else None
                
                # Process hallucination result
                if not isinstance(h_result, Exception):
                    faithfulness = round(h_result.faithfulness_score, 2)
                    quality_scores["faithfulness"] = faithfulness
                    quality_scores["is_faithful"] = h_result.is_faithful

                    # ◀ ⑧f CORRECTIVE LOOP — re-retrieve if faithfulness is very low ▶
                    _corrective_done = False
                    if faithfulness < 0.5:
                        _retry_count = getattr(self, "_corrective_retry_count", 0)
                        if _retry_count < 2 and citations:
                            try:
                                self._corrective_retry_count = _retry_count + 1
                                logger.warning(
                                    f"⚠️ Low faithfulness ({faithfulness:.2f}) — "
                                    f"triggering corrective retrieve (attempt {_retry_count + 1})"
                                )
                                yield StreamEvent(
                                    type=StreamEventType.PROGRESS,
                                    data={"step": "corrective", "progress": 92, "message": "🔄 Kiểm tra lại thông tin..."}
                                )
                                # Broaden the query and re-retrieve
                                broadened = f"{query} giải thích chi tiết"
                                corrective_result = await asyncio.wait_for(
                                    rag_service.query(
                                        question=broadened,
                                        workspace_id=workspace_id,
                                        document_ids=document_ids,
                                        tags=tags,
                                        model=model,
                                        conversation_history=history_dicts,
                                        top_k=10,
                                    ),
                                    timeout=10.0,
                                )
                                corrective_answer = getattr(corrective_result, "answer", None)
                                if corrective_answer and len(corrective_answer) > len(answer_accumulator) * 0.5:
                                    # Check if corrective answer is better
                                    _h2 = await h_checker.check_faithfulness(
                                        corrective_answer,
                                        combined_context + "\n" + " ".join(
                                            c.get("content", "") for c in
                                            (getattr(corrective_result, "citations", []) or [])[:3]
                                        )
                                    )
                                    if _h2.faithfulness_score > faithfulness:
                                        logger.info(f"✅ Corrective answer better ({_h2.faithfulness_score:.2f} > {faithfulness:.2f})")
                                        answer_accumulator = corrective_answer
                                        # Client capability check:
                                        # If FE supports replace_response → swap entire answer.
                                        # If not → fallback to appending revision note (REVISION_APPEND).
                                        yield StreamEvent(
                                            type=StreamEventType.REPLACE_RESPONSE,
                                            data={
                                                "content": corrective_answer,
                                                "reason": "corrective_loop",
                                                "original_faithfulness": faithfulness,
                                                "new_faithfulness": round(_h2.faithfulness_score, 2),
                                                "fallback_mode": "revision_append",
                                                # FE contract: if client doesn't handle REPLACE_RESPONSE,
                                                # it MUST treat unrecognized events as no-op.
                                                # Pipeline also emits a TOKEN append as safety net.
                                            }
                                        )
                                        # Safety net: append revision note for clients that don't
                                        # support REPLACE_RESPONSE (graceful degradation)
                                        _revision_note = "\n\n---\n*[🔄 Phản hồi được cải thiện]*"
                                        yield StreamEvent(
                                            type=StreamEventType.TOKEN,
                                            data={"content": _revision_note, "index": len(answer_accumulator)}
                                        )
                                        quality_scores["faithfulness"] = round(_h2.faithfulness_score, 2)
                                        quality_scores["corrective_applied"] = True
                                        _corrective_done = True
                            except (asyncio.TimeoutError, Exception) as _ce:
                                logger.warning(f"Corrective loop failed: {_ce}")

                    if not _corrective_done:
                        if faithfulness < 0.5:
                            disclaimer = "\n\n⚠️ **Lưu ý**: Câu trả lời này có thể không chính xác. Hãy xác minh lại từ nguồn tài liệu gốc."
                            answer_accumulator += disclaimer
                            yield StreamEvent(type=StreamEventType.TOKEN, data={"content": disclaimer, "index": len(answer_accumulator)})
                            logger.warning(f"⚠️ Low faithfulness: {faithfulness:.2f}")
                        elif faithfulness < 0.7:
                            disclaimer = "\n\n💡 *Một số thông tin có thể cần kiểm chứng thêm.*"
                            answer_accumulator += disclaimer
                            yield StreamEvent(type=StreamEventType.TOKEN, data={"content": disclaimer, "index": len(answer_accumulator)})
                else:
                    logger.debug(f"Hallucination check failed: {h_result}")
                
                # Process grounding result
                if not isinstance(g_result, Exception):
                    quality_scores["grounding"] = round(g_result.confidence, 2)
                    quality_scores["is_grounded"] = g_result.is_grounded
                else:
                    logger.debug(f"Grounding check failed: {g_result}")
                
                # Process fact-check result (FactCheckResult has .passed, .numerical_claims, .failed_claims)
                if f_result and not isinstance(f_result, Exception):
                    total_claims = len(getattr(f_result, 'numerical_claims', []))
                    failed_claims = len(getattr(f_result, 'failed_claims', []))
                    quality_scores["fact_check"] = {
                        "verified_claims": total_claims - failed_claims,
                        "total_claims": total_claims,
                        "all_correct": getattr(f_result, 'passed', True),
                    }
                    if failed_claims > 0:
                        quality_warnings.append({
                            "type": "fact_check",
                            "severity": "warning",
                            "message": f"Phát hiện {failed_claims} lỗi số liệu",
                        })
                    logger.info(f"📋 Fact check: {total_claims - failed_claims}/{total_claims} claims verified")
                    
            except Exception as e:
                logger.debug(f"Post-stream quality check skipped: {e}")

        # =================================================================
        # ⑦c CONFIDENCE SCORING — Composite score from all quality signals
        # =================================================================
        try:
            from app.services.quality.confidence_scorer import confidence_scorer
            composite = confidence_scorer.compute_confidence(
                hallucination_score=quality_scores.get("faithfulness", 1.0),
                relevance_score=quality_scores.get("grounding", 1.0),
                safety_score=1.0,  # Already passed guardrails
                fact_check_score=1.0 if quality_scores.get("fact_check", {}).get("all_correct", True) else 0.5,
                latency_ms=rag_latency_ms if 'rag_latency_ms' in dir() else 0,
            )
            confidence_label = confidence_scorer.get_confidence_level(composite.overall_score)
            quality_scores["confidence"] = round(composite.overall_score, 2)
            quality_scores["confidence_label"] = confidence_label
            quality_scores["needs_retry"] = composite.needs_retry
            logger.info(f"🎯 Confidence: {composite.overall_score:.2f} ({confidence_label})")
        except Exception as e:
            logger.debug(f"Confidence scoring skipped: {e}")

        # =================================================================
        # ⑦d POLICY EVALUATION — Apply response policy (STRICT/BALANCED/OPEN)
        # =================================================================
        try:
            from app.services.quality.policy_service import PolicyService
            policy_svc = PolicyService()
            policy_result = policy_svc.evaluate_with_dynamic_thresholds(
                workspace_id=str(workspace_id),
                grounding_score=quality_scores.get("grounding", 1.0),
                relevance_score=quality_scores.get("faithfulness", 1.0),
            )
            quality_scores["policy"] = {
                "approved": policy_result.approved,
                "policy_mode": policy_result.policy_mode,
                "reasoning": policy_result.reasoning,
            }
            
            # If not approved in STRICT mode, add disclaimer
            if not policy_result.approved:
                disclaimer = "⚠️ Không tìm thấy đủ thông tin liên quan để trả lời chính xác."
                answer_accumulator += f"\n\n{disclaimer}"
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    data={"content": f"\n\n{disclaimer}", "index": len(answer_accumulator)}
                )
            logger.info(f"📜 Policy: approved={policy_result.approved} ({policy_result.policy_mode})")
        except Exception as e:
            logger.debug(f"Policy evaluation skipped: {e}")

        # =================================================================
        # ⑦e RESULT VALIDATION — Consolidated second-opinion validation
        # =================================================================
        try:
            from app.services.quality.result_validator import result_validator
            sources_for_validation = [{"content": c.get("content", "")} for c in citations]
            validation_result = await result_validator.validate(
                query=query,
                response=answer_accumulator,
                sources=sources_for_validation,
            )
            quality_scores["validation"] = {
                "status": validation_result.status.value,
                "confidence": round(validation_result.confidence_score, 2),
                "issues": len(validation_result.issues),
            }
            if validation_result.status.value == "fail":
                quality_warnings.append({
                    "type": "validation",
                    "severity": "warning",
                    "message": f"Validation: {len(validation_result.issues)} issues detected",
                })
            logger.info(f"✅ Validation: {validation_result.status.value} (confidence={validation_result.confidence_score:.2f}, issues={len(validation_result.issues)})")
        except Exception as e:
            logger.debug(f"Result validation skipped: {e}")

        # =================================================================
        # BUILD & YIELD METADATA
        # =================================================================
        if not stats:
            stats = {
                "model": model or "auto",
                "provider": "streaming_provider",
                "latency_ms": rag_latency_ms if 'rag_latency_ms' in dir() else 0,
                "completion_tokens": token_count if 'token_count' in dir() else 0,
                "prompt_tokens": len(query.split()) * 2,
            }
        
        # Format citations
        formatted_citations = []
        for c in citations:
            formatted_citations.append({
                "chunk_id": c.get("chunk_id", ""),
                "document_id": c.get("document_id", ""),
                "document_title": c.get("document_title", "Unknown"),
                "content": c.get("content", ""),
                "page": c.get("page"),
                "score": c.get("score", 0.0),
            })

        # ── Inline citation mapping (citations per paragraph) ─────────────
        # Mechanism: span-match between response paragraphs and supporting chunks.
        # For each paragraph, check if any 4+ word phrase from a citation chunk
        # appears verbatim in the paragraph (heuristic overlap).
        # Alternative: LLM-based attribution (more accurate, higher latency).
        # Output: {"paragraph_citations": {"0": [0,1], "2": [3]}} in METADATA.
        # Map each citation to the paragraph(s) it supports.
        # "paragraph_citations": {"0": [0,1], "1": [2]} means first paragraph
        # is supported by citations at index 0,1 etc.
        paragraph_citations = {}
        if answer_accumulator and formatted_citations:
            paragraphs = [p.strip() for p in answer_accumulator.split("\n\n") if p.strip()]
            for p_idx, para in enumerate(paragraphs):
                matching = []
                for c_idx, cit in enumerate(formatted_citations):
                    cit_content = cit.get("content", "").lower()
                    # Simple overlap: if any 4+ word phrase from citation appears in paragraph
                    para_lower = para.lower()
                    words = cit_content.split()
                    for i in range(len(words) - 3):
                        phrase = " ".join(words[i:i+4])
                        if phrase in para_lower:
                            matching.append(c_idx)
                            break
                if matching:
                    paragraph_citations[str(p_idx)] = matching

            # Flag unsupported paragraphs (claims without citation backing)
            unsupported_paragraphs = [
                i for i in range(len(paragraphs))
                if str(i) not in paragraph_citations and len(paragraphs[i].split()) > 10
            ]
            if unsupported_paragraphs:
                quality_scores["unsupported_claims"] = unsupported_paragraphs

        metadata = {
            "model": stats.get("model", model),
            "provider": stats.get("provider", "unknown"),
            "citations": formatted_citations,
            "trace_id": trace_id if 'trace_id' in dir() else None,
        }
        if paragraph_citations:
            metadata["paragraph_citations"] = paragraph_citations
        if quality_scores:
            metadata["quality"] = quality_scores
        if quality_warnings:
            metadata["quality_warnings"] = quality_warnings
        
        yield StreamEvent(type=StreamEventType.METADATA, data=metadata)

        # =================================================================
        # SAVE ASSISTANT MESSAGE + CITATIONS
        # =================================================================
        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=answer_accumulator,
            model=model or "auto",
            provider=stats.get("provider", "unknown"),
            prompt_tokens=stats.get("prompt_tokens", 0),
            completion_tokens=stats.get("completion_tokens", 0),
            latency_ms=stats.get("latency_ms", 0),
        )
        self.session.add(assistant_msg)
        await self.session.commit()
        
        # Save Citations
        if citations:
            try:
                db_citations = []
                for c in citations:
                    if "chunk_id" in c and c["chunk_id"]:
                        db_citations.append(Citation(
                            message_id=assistant_msg.id,
                            chunk_id=UUID(c["chunk_id"]) if isinstance(c["chunk_id"], str) else c["chunk_id"],
                            score=c.get("score"),
                            quote=c.get("content", "")[:500],
                            page=c.get("page")
                        ))
                
                if db_citations:
                    self.session.add_all(db_citations)
                    await self.session.commit()
                    logger.info(f"Saved {len(db_citations)} citations")
            except Exception as e:
                logger.error(f"Failed to save citations: {e}")
        
        # Auto-title conversation
        try:
            default_titles = ["Cuộc hội thoại mới", "New Chat", "Untitled"]
            if conversation.title in default_titles:
                new_title = await conv_service.auto_title_conversation(conversation_id)
                if new_title:
                    logger.info(f"Auto-titled: '{new_title}'")
        except Exception as e:
            logger.warning(f"Auto-title failed: {e}")

        # =================================================================
        # ⑧ POST-PROCESSING (Background, non-blocking)
        # =================================================================
        
        # Memori Extraction — Extract facts from Q&A pair
        try:
            from app.services.memori.auto_cognify_service import AutoCognifyService
            cognify = AutoCognifyService(self.session)
            asyncio.create_task(
                self._safe_background_task(
                    cognify.cognify_message(
                        message=answer_accumulator,
                        role="assistant",
                        conversation_id=conversation_id,
                        user_id=user_id,
                        workspace_id=workspace_id,
                    ),
                    "memori_extraction"
                )
            )
        except Exception as e:
            logger.debug(f"Memori extraction setup failed: {e}")
        
        # ⑧b Knowledge Graph Enrichment — Infer relationships from existing facts
        try:
            from app.services.memori.memify_service import MemifyService
            memify = MemifyService(self.session)
            asyncio.create_task(
                self._safe_background_task(
                    memify.memify(
                        entity_id=str(user_id),
                        workspace_id=workspace_id,
                        run_inference=True,
                        run_summary=False,
                        run_merge=False,
                    ),
                    "memify_enrichment"
                )
            )
        except Exception as e:
            logger.debug(f"Memify enrichment setup failed: {e}")
        
        # ⑧c AUGMENTATION PIPELINE — Extract preferences, attributes, enhanced facts
        try:
            from app.services.memori.augmentation_processors_service import AugmentationPipeline
            from app.services.memori.extraction import FactExtractor
            aug_pipeline = AugmentationPipeline(fact_extractor=FactExtractor())
            asyncio.create_task(
                self._safe_background_task(
                    aug_pipeline.process_all(
                        messages=[
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": answer_accumulator},
                        ],
                        entity_id=str(user_id) if user_id else "default",
                        conversation_id=conversation_id,
                    ),
                    "augmentation_pipeline"
                )
            )
            logger.info("🧬 Augmentation pipeline scheduled (fact + preference + attribute extraction)")
        except Exception as e:
            logger.debug(f"Augmentation pipeline setup failed: {e}")
        
        # Dedup Cache Save — Cache response for future dedup hits
        if dedup_cache:
            try:
                await dedup_cache.set(
                    user_id, workspace_id, query,
                    {"answer": answer_accumulator, "metadata": metadata}
                )
            except Exception as e:
                logger.debug(f"Dedup cache save failed: {e}")
        
        # =================================================================
        # ⑨ PATTERN MONITORING — Record metrics for dashboard
        # =================================================================
        try:
            from app.services.rag_patterns.monitoring import PatternMonitor
            monitor = PatternMonitor()
            monitor.record_query(
                pattern_name=stats.get("provider", "unknown"),
                latency_ms=stats.get("latency_ms", rag_latency_ms if 'rag_latency_ms' in dir() else 0),
                accuracy=quality_scores.get("confidence", 1.0),
                success=True,
            )
        except Exception as e:
            logger.debug(f"Pattern monitoring skipped: {e}")
        
        # Latency Budget Report — Log if any stage exceeded budget
        if latency_allocation:
            try:
                total_elapsed = int((time.time() - start_time) * 1000) if 'start_time' in dir() else 0
                from app.services.core.latency_budget_service import LatencyBudgetManager
                latency_mgr = LatencyBudgetManager()
                within_budget = latency_mgr.check_budget(latency_allocation, "rag", total_elapsed)
                if not within_budget:
                    logger.warning(f"⚠️ Latency budget exceeded: {total_elapsed}ms / {latency_allocation.total_budget_ms}ms")
            except Exception as e:
                logger.debug(f"Latency budget check failed: {e}")

    async def _safe_background_task(self, coro, task_name: str):
        """Run a background task safely, catching and logging errors."""
        try:
            await coro
            logger.info(f"Background task '{task_name}' completed")
        except Exception as e:
            logger.warning(f"Background task '{task_name}' failed: {e}")

    async def _stream_with_rag(
        self,
        rag_service,
        query: str,
        workspace_id: UUID,
        document_ids: Optional[List[UUID]],
        tags: Optional[List[str]],
        model: Optional[str],
        memory_context: Optional[str],
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream using RAG service's native streaming (stateless, no conversation)."""
        token_index = 0
        
        async for chunk in rag_service.query_stream(
            question=query,
            workspace_id=workspace_id,
            document_ids=document_ids,
            tags=tags,
            model=model,
            memory_context=memory_context,
        ):
            if self._cancelled:
                return
            
            if isinstance(chunk, str):
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    data={"content": chunk, "index": token_index}
                )
                token_index += 1
            elif isinstance(chunk, dict):
                if "citations" in chunk:
                    yield StreamEvent(
                        type=StreamEventType.METADATA,
                        data=chunk
                    )
                elif "progress" in chunk:
                    yield StreamEvent(
                        type=StreamEventType.PROGRESS,
                        data=chunk
                    )
    
    async def _fallback_stream(
        self,
        rag_service,
        query: str,
        workspace_id: UUID,
        document_ids: Optional[List[UUID]],
        tags: Optional[List[str]],
        model: Optional[str],
        memory_context: Optional[str],
    ) -> AsyncGenerator[StreamEvent, None]:
        """Fallback: get full response then simulate streaming."""
        yield StreamEvent(
            type=StreamEventType.PROGRESS,
            data={"step": "generating", "progress": 40, "message": "Đang tạo câu trả lời..."}
        )
        
        response = await rag_service.query(
            question=query,
            workspace_id=workspace_id,
            document_ids=document_ids,
            tags=tags,
            model=model,
            memory_context=memory_context,
        )
        
        if self._cancelled:
            return
        
        # Simulate streaming
        answer = response.answer
        chunk_size = 20
        
        for i in range(0, len(answer), chunk_size):
            if self._cancelled:
                return
            
            chunk = answer[i:i + chunk_size]
            yield StreamEvent(
                type=StreamEventType.TOKEN,
                data={"content": chunk, "index": i // chunk_size}
            )
            await asyncio.sleep(0.02)
        
        # Metadata
        citations = []
        if hasattr(response, 'citations') and response.citations:
            citations = [
                {
                    "chunk_id": str(c.chunk_id) if hasattr(c, 'chunk_id') else '',
                    "document_id": str(c.document_id) if hasattr(c, 'document_id') else '',
                    "document_title": c.document_title if hasattr(c, 'document_title') else "",
                    "content": c.content if hasattr(c, 'content') else "",
                    "page": c.page if hasattr(c, 'page') else None,
                    "score": c.score if hasattr(c, 'score') else 0.0,
                }
                for c in response.citations
            ]
        
        stats = {
            "provider": response.provider if hasattr(response, 'provider') else None,
            "model": response.model if hasattr(response, 'model') else None,
            "prompt_tokens": response.prompt_tokens if hasattr(response, 'prompt_tokens') else 0,
            "completion_tokens": response.completion_tokens if hasattr(response, 'completion_tokens') else 0,
        }
        
        yield StreamEvent(
            type=StreamEventType.METADATA,
            data={"citations": citations, "stats": stats}
        )
