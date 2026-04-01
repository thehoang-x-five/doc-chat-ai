"""
Corrective RAG Service - Pattern #2

Validates and corrects retrieved information before generation.
Consolidated from: base.py, scorer.py, resolver.py, fallback.py
"""
import logging

from .models import (
    CorrectedRetrievalResult,
    CorrectionStep,
    Document,
    compute_similarity,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Components (inlined from separate files)
# =============================================================================

class RelevanceScorer:
    """
    Scores document relevance using LLM-based grading.
    Currently uses simplified keyword overlap scoring.
    """

    async def score_relevance(self, query: str, document: Document) -> float:
        """
        Score document relevance to query.
        
        Args:
            query: User query
            document: Document to score
            
        Returns:
            Relevance score (0-1)
        """
        query_words = set(query.lower().split())
        doc_words = set(document.content.lower().split())

        if len(query_words) == 0:
            return 0.0

        overlap = len(query_words & doc_words) / len(query_words)

        # Boost score if title matches
        title_words = set(document.title.lower().split())
        title_overlap = len(query_words & title_words) / len(query_words)

        # Combined score
        score = (overlap * 0.7) + (title_overlap * 0.3)

        logger.debug(
            f"Relevance score for doc {document.document_id}: {score:.2f} "
            f"(content: {overlap:.2f}, title: {title_overlap:.2f})"
        )

        return min(score, 1.0)


class ConflictResolver:
    """
    Resolves conflicting information using majority voting.
    Groups similar documents and selects best representative.
    """

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold

    def resolve_conflicts(self, documents: list[Document]) -> list[Document]:
        """
        Resolve conflicting information using majority voting.
        
        Args:
            documents: List of potentially conflicting documents
            
        Returns:
            List of documents with conflicts resolved
        """
        if len(documents) <= 1:
            return documents

        # Group similar documents by content similarity
        groups = []
        used = set()

        for i, doc1 in enumerate(documents):
            if i in used:
                continue

            group = [doc1]
            used.add(i)

            for j, doc2 in enumerate(documents):
                if j in used or i == j:
                    continue

                similarity = compute_similarity(doc1.content, doc2.content)

                if similarity > self.similarity_threshold:
                    group.append(doc2)
                    used.add(j)

            groups.append(group)

        # Select representative from each group (highest relevance)
        resolved = []
        for group in groups:
            best_doc = max(group, key=lambda d: d.relevance_score or 0)
            resolved.append(best_doc)

        logger.info(
            f"Conflict resolution: {len(documents)} docs -> "
            f"{len(groups)} groups -> {len(resolved)} resolved"
        )

        return resolved


class WebSearchFallback:
    """
    Performs web search for additional information when relevance is low.
    Placeholder implementation - integrate with actual web search APIs.
    """

    async def web_search_fallback(self, query: str) -> list[Document]:
        """
        Perform web search for additional information.
        
        Args:
            query: Search query
            
        Returns:
            List of documents from web search
        """
        logger.info(f"Web search fallback for query: {query}")

        # Placeholder - replace with actual web search
        web_docs = [
            Document(
                document_id="web_1",
                title=f"Web result for: {query}",
                content=f"This is a web search result related to {query}",
                metadata={"source": "web_search", "url": "https://example.com/1"},
            ),
        ]

        logger.info(f"Web search returned {len(web_docs)} documents")
        return web_docs


# =============================================================================
# Main Service
# =============================================================================

class CorrectiveRAGService:
    """
    Service implementing Corrective RAG pattern.
    
    Validates and corrects retrieved information before generating responses,
    improving accuracy and reducing hallucinations.
    
    Flow:
    1. Score relevance of each retrieved document
    2. If relevance < threshold, perform web search
    3. Resolve conflicts between documents
    4. Return corrected document set
    """

    def __init__(
        self,
        relevance_threshold: float = 0.6,
        max_correction_attempts: int = 2,
    ):
        """
        Initialize Corrective RAG service.
        
        Args:
            relevance_threshold: Minimum relevance score (0-1)
            max_correction_attempts: Maximum correction attempts before fallback
        """
        self.relevance_threshold = relevance_threshold
        self.max_correction_attempts = max_correction_attempts

        self.scorer = RelevanceScorer()
        self.resolver = ConflictResolver()
        self.fallback = WebSearchFallback()

        logger.info(
            f"CorrectiveRAGService initialized: "
            f"threshold={relevance_threshold}, max_attempts={max_correction_attempts}"
        )

    async def retrieve_and_correct(
        self,
        query: str,
        initial_docs: list[Document],
        relevance_threshold: float | None = None,
    ) -> CorrectedRetrievalResult:
        """
        Retrieve and correct documents.
        
        Args:
            query: User query
            initial_docs: Initially retrieved documents
            relevance_threshold: Override default threshold
            
        Returns:
            CorrectedRetrievalResult with corrected documents
        """
        threshold = relevance_threshold or self.relevance_threshold
        audit_trail = []
        corrections_made = 0
        web_search_used = False
        conflicts_resolved = 0

        current_docs = initial_docs.copy()

        try:
            # Step 1: Score relevance
            logger.info(f"Scoring relevance for {len(current_docs)} documents")

            for doc in current_docs:
                doc.relevance_score = await self.scorer.score_relevance(query, doc)

            # Check if any docs meet threshold
            relevant_docs = [d for d in current_docs if d.relevance_score >= threshold]

            audit_trail.append(CorrectionStep(
                step_type="relevance_check",
                documents_before=len(current_docs),
                documents_after=len(relevant_docs),
                reason=f"Filtered documents with relevance < {threshold}",
            ))

            # Step 2: Web search fallback if needed
            if len(relevant_docs) == 0 and corrections_made < self.max_correction_attempts:
                logger.warning(
                    f"No relevant documents found (threshold={threshold}), "
                    f"performing web search"
                )

                web_docs = await self.fallback.web_search_fallback(query)

                if web_docs:
                    for doc in web_docs:
                        doc.relevance_score = await self.scorer.score_relevance(query, doc)

                    relevant_docs.extend([d for d in web_docs if d.relevance_score >= threshold])
                    web_search_used = True
                    corrections_made += 1

                    audit_trail.append(CorrectionStep(
                        step_type="web_search",
                        documents_before=0,
                        documents_after=len(web_docs),
                        reason="Web search fallback due to low relevance",
                    ))

            # Step 3: Resolve conflicts
            if len(relevant_docs) > 1:
                logger.info(f"Resolving conflicts among {len(relevant_docs)} documents")

                resolved_docs = self.resolver.resolve_conflicts(relevant_docs)
                conflicts_resolved = len(relevant_docs) - len(resolved_docs)

                if conflicts_resolved > 0:
                    audit_trail.append(CorrectionStep(
                        step_type="conflict_resolution",
                        documents_before=len(relevant_docs),
                        documents_after=len(resolved_docs),
                        reason=f"Resolved {conflicts_resolved} conflicting documents",
                    ))
                    corrections_made += 1

                relevant_docs = resolved_docs

            return CorrectedRetrievalResult(
                final_documents=relevant_docs,
                corrections_made=corrections_made,
                web_search_used=web_search_used,
                conflicts_resolved=conflicts_resolved,
                audit_trail=audit_trail,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error in corrective retrieval: {e}")

            return CorrectedRetrievalResult(
                final_documents=initial_docs,
                corrections_made=0,
                web_search_used=False,
                conflicts_resolved=0,
                audit_trail=audit_trail,
                success=False,
                error_message=str(e),
            )

    def get_audit_trail(self, result: CorrectedRetrievalResult) -> str:
        """Get human-readable audit trail."""
        lines = ["Corrective RAG Audit Trail:", ""]

        for i, step in enumerate(result.audit_trail, 1):
            lines.append(f"{i}. {step.step_type.upper()}")
            lines.append(f"   Time: {step.timestamp.isoformat()}")
            lines.append(f"   Documents: {step.documents_before} -> {step.documents_after}")
            lines.append(f"   Reason: {step.reason}")
            lines.append("")

        lines.append("Summary:")
        lines.append(f"  - Corrections made: {result.corrections_made}")
        lines.append(f"  - Web search used: {result.web_search_used}")
        lines.append(f"  - Conflicts resolved: {result.conflicts_resolved}")
        lines.append(f"  - Final documents: {len(result.final_documents)}")

        return "\n".join(lines)
