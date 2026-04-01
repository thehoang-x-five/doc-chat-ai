"""
Function Calling Service — Production Ready.

Routing: keyword fast-pass → LLM-confirm (hybrid).
Permission: workspace policy allow_function_calling.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tools.tools_service_v2 import execute_tool

logger = logging.getLogger(__name__)

# ── Keywords that strongly suggest tool use ────────────────────────────────
_TOOL_KEYWORDS_VI = [
    "bao nhiêu", "đếm", "số lượng", "tổng số",
    "liệt kê", "danh sách", "có những", "có file nào",
    "thống kê", "báo cáo nhanh",
]
_TOOL_KEYWORDS_EN = [
    "how many", "count", "list", "total", "enumerate",
    "how much", "statistics",
]
_ALL_KEYWORDS = _TOOL_KEYWORDS_VI + _TOOL_KEYWORDS_EN


async def _llm_confirm_tool_use(question: str, model: str = "gpt-4o-mini") -> bool:
    """
    Ask LLM whether a tool call is needed for this question.
    Returns True = use tool, False = use RAG.
    Timeout: 1.5s. On failure → False (safe default).
    """
    try:
        from app.services.infrastructure.ai_providers.manager import AIProviderManager

        manager = AIProviderManager()
        prompt = (
            "You are a query router. Answer ONLY 'yes' or 'no'.\n"
            "Should the following query be answered by a metadata tool "
            "(count/list documents) rather than document search?\n\n"
            f"Query: {question}\n\nAnswer (yes/no):"
        )
        result = await asyncio.wait_for(
            manager.generate(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=3,
                temperature=0.0,
            ),
            timeout=1.5,
        )
        answer = (result.content or "").strip().lower()
        return answer.startswith("yes")
    except Exception as e:
        logger.debug(f"LLM tool-routing confirm failed: {e}")
        return False


async def _workspace_allows_tools(session: AsyncSession, workspace_id: UUID) -> bool:
    """
    Check workspace policy: allow_function_calling flag.
    Defaults to True if flag not set.
    """
    try:
        from sqlalchemy import select, text
        # If workspace has a settings JSON column with allow_function_calling
        result = await session.execute(
            text(
                "SELECT settings->>'allow_function_calling' "
                "FROM workspaces WHERE id = :wid"
            ),
            {"wid": str(workspace_id)},
        )
        row = result.scalar_one_or_none()
        if row is None:
            return True  # No policy → allow
        return str(row).lower() not in ("false", "0", "no")
    except Exception as e:
        logger.debug(f"Workspace tool policy check failed: {e}")
        return True  # Default allow on error


class FunctionCallingService:
    """
    Service xử lý function calling trong chat.

    Routing strategy:
    1. Keyword fast-pass  (0 ms)
    2. LLM confirm        (≤ 1.5s timeout, only when keyword matched)
    3. Workspace ACL      (DB check)
    """

    def __init__(self, session: AsyncSession, workspace_id: UUID):
        self.session = session
        self.workspace_id = workspace_id

    async def should_use_function_calling(self, question: str) -> bool:
        """
        Hybrid routing: keyword → LLM-confirm → workspace permission.
        Returns True only when all three gates pass.
        """
        question_lower = question.lower()

        # ── Gate 1: keyword fast-pass ──────────────────────────────────────
        keyword_hit = any(kw in question_lower for kw in _ALL_KEYWORDS)
        if not keyword_hit:
            return False  # Definitely not a tool query

        # ── Gate 2: LLM confirm (runs only on keyword match) ───────────────
        confirmed = await _llm_confirm_tool_use(question)
        if not confirmed:
            logger.debug("LLM declined tool routing despite keyword match")
            return False

        # ── Gate 3: workspace policy ───────────────────────────────────────
        allowed = await _workspace_allows_tools(self.session, self.workspace_id)
        if not allowed:
            logger.info(f"Workspace {self.workspace_id} disallows function calling")
            return False

        return True

    async def process_question(
        self,
        question: str,
        model: str = "gpt-4o-mini",
    ) -> Dict[str, Any]:
        """
        Execute the appropriate tool for the question.

        Returns:
            {
                "answer": str | None,
                "used_function_calling": bool,
                "tool_calls": list,
                "usage": dict | None,
            }
        """
        _no_op = {
            "answer": None,
            "used_function_calling": False,
            "tool_calls": [],
            "usage": None,
        }

        if not await self.should_use_function_calling(question):
            return _no_op

        question_lower = question.lower()

        try:
            # ── count_documents ───────────────────────────────────────────
            if any(kw in question_lower for kw in ["bao nhiêu", "count", "đếm", "how many", "số lượng"]):
                result = await execute_tool(
                    tool_name="count_documents",
                    arguments={"status": "READY"},
                    session=self.session,
                    workspace_id=self.workspace_id,
                )
                answer = (
                    f"📊 Có tổng cộng **{result['total']} tài liệu** trong kho.\n\n"
                    f"✅ Trạng thái: {result['status_filter']}\n"
                    f"📁 Workspace: {result['workspace_id']}"
                )
                return {
                    "answer": answer,
                    "used_function_calling": True,
                    "tool_calls": [{"tool": "count_documents", "result": result}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                }

            # ── list_documents ────────────────────────────────────────────
            if any(kw in question_lower for kw in ["liệt kê", "list", "danh sách", "có những", "có file"]):
                result = await execute_tool(
                    tool_name="list_documents",
                    arguments={"limit": 10},
                    session=self.session,
                    workspace_id=self.workspace_id,
                )
                answer = f"📚 Danh sách {result['total']} tài liệu:\n\n"
                for i, doc in enumerate(result["documents"], 1):
                    answer += (
                        f"{i}. **{doc['title']}**\n"
                        f"   - Trạng thái: {doc['status']}\n"
                        f"   - Chunks: {doc['chunk_count']}\n"
                        f"   - Tags: {', '.join(doc['tags']) if doc['tags'] else 'Không có'}\n\n"
                    )
                return {
                    "answer": answer,
                    "used_function_calling": True,
                    "tool_calls": [{"tool": "list_documents", "result": result}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                }

        except Exception as e:
            logger.error(f"Function calling execution failed: {e}")
            return _no_op

        return _no_op
