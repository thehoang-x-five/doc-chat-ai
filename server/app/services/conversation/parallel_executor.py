"""
Parallel Memory Executor - Execute Memory, Memori, and Graph recall concurrently.

This module provides parallel execution of memory operations to reduce
total latency from 4-6s (sequential) to 2-3s (parallel).

Enhanced with Graph Search for richer knowledge retrieval.
"""

import asyncio
import hashlib
import logging
import time
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ParallelMemoryExecutor:
    """
    Executes Memory, Memori, and Graph recall operations in parallel.
    
    Benefits:
    - Reduces latency from 4-6s to 2-3s (50% reduction)
    - Handles partial failures gracefully
    - Logs individual task timings for debugging
    - Now includes Graph Search for knowledge graph context
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def execute_memory_recall(
        self,
        conversation_id: UUID,
        query: str,
        workspace_id: UUID,
        user_id: UUID,
        timeout: float = 5.0,
        include_graph_search: bool = True,
    ) -> Tuple[str, str, str]:
        """
        Execute memory, memori, and graph recall in parallel.
        
        Args:
            conversation_id: Conversation ID for memory lookup
            query: User query for memori semantic search
            workspace_id: Workspace ID
            user_id: User ID for memori context
            timeout: Maximum time to wait for all operations (seconds)
            include_graph_search: Whether to run graph search (default True)
            
        Returns:
            Tuple of (memory_context, memori_context, graph_context)
            Returns empty strings on failure
        """
        start_time = time.time()
        
        # Create tasks for parallel execution
        memory_task = asyncio.create_task(
            self._get_memory_context(conversation_id)
        )
        memori_task = asyncio.create_task(
            self._get_memori_context(query, conversation_id, workspace_id, user_id)
        )
        
        # Optional graph search task
        graph_task = None
        if include_graph_search:
            graph_task = asyncio.create_task(
                self._get_graph_context(query, workspace_id, user_id)
            )
        
        # Gather all tasks
        tasks = [memory_task, memori_task]
        if graph_task:
            tasks.append(graph_task)
        
        # Execute with timeout and return_exceptions=True
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Parallel memory recall timed out after {timeout}s")
            # Cancel any still-running tasks
            for task in tasks:
                task.cancel()
            return "", "", ""
        
        # Extract results, handling exceptions
        memory_context = ""
        memori_context = ""
        graph_context = ""
        
        if isinstance(results[0], Exception):
            logger.warning(f"Memory recall failed: {results[0]}")
        else:
            memory_context = results[0] or ""
        
        if isinstance(results[1], Exception):
            logger.warning(f"Memori recall failed: {results[1]}")
        else:
            memori_context = results[1] or ""
        
        if len(results) > 2:
            if isinstance(results[2], Exception):
                logger.warning(f"Graph recall failed: {results[2]}")
            else:
                graph_context = results[2] or ""
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"⏱️ Parallel memory recall completed in {total_time:.0f}ms (memory: {'✓' if memory_context else '✗'}, memori: {'✓' if memori_context else '✗'}, graph: {'✓' if graph_context else '✗'})")
        
        return memory_context, memori_context, graph_context
    
    async def _get_memory_context(self, conversation_id: UUID) -> str:
        """Get memory context from MemoryManager."""
        start_time = time.time()
        
        try:
            from app.services.conversation.memory_service import MemoryManager
            
            memory_manager = MemoryManager(self.session)
            memory = await memory_manager.get_memory(conversation_id)
            context = memory.to_context_string()
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"Memory recall: {elapsed:.0f}ms")
            
            return context
            
        except ImportError:
            logger.warning("MemoryManager not available")
            return ""
        except Exception as e:
            logger.warning(f"Memory recall error: {e}")
            return ""
    
    async def _get_memori_context(
        self,
        query: str,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
    ) -> str:
        """Get memori context from MemoriManager."""
        start_time = time.time()
        
        try:
            from app.services.memori import MemoriManager, MemoriConfig
            
            memori_config = MemoriConfig.from_conversation(
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            
            memori_manager = MemoriManager(self.session, memori_config)
            
            recalled_facts = await memori_manager.recall_for_query(
                query=query,
                conversation_id=conversation_id,
                limit=5,
            )
            
            context = ""
            if recalled_facts:
                context = memori_manager.format_recalled_facts(recalled_facts)
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"Memori recall: {elapsed:.0f}ms, facts: {len(recalled_facts) if recalled_facts else 0}")
            
            return context
            
        except ImportError:
            logger.debug("Memori not available")
            return ""
        except Exception as e:
            logger.warning(f"Memori recall error: {e}")
            return ""
    
    async def _get_graph_context(
        self,
        query: str,
        workspace_id: UUID,
        user_id: UUID,
    ) -> str:
        """
        Get graph context from GraphSearchService.
        Searches knowledge graph for related entities and relationships.
        """
        start_time = time.time()
        
        try:
            from app.services.memori.graph_search_service import GraphSearchService, SearchType
            
            graph_service = GraphSearchService(self.session)
            
            # Use combined search for best coverage
            results = await graph_service.search(
                query=query,
                entity_id=str(user_id),
                workspace_id=workspace_id,
                search_type=SearchType.COMBINED,
                limit=5,
            )
            
            context = ""
            if results:
                context = graph_service.format_results_for_prompt(results, max_chars=1500)
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"Graph recall: {elapsed:.0f}ms, results: {len(results) if results else 0}")
            
            return context
            
        except ImportError:
            logger.debug("GraphSearchService not available")
            return ""
        except Exception as e:
            logger.warning(f"Graph recall error: {e}")
            return ""
