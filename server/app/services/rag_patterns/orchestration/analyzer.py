"""
Query Analyzer - Analyzes queries to determine optimal RAG patterns.

This module provides:
1. Query classification (complexity, domain, requirements)
2. Query characteristics extraction
3. Pattern recommendation based on query analysis
4. Routing mode determination (Direct vs Workflow Planning)
5. SLA budget assignment

Migrated from raganything/patterns/query_analyzer.py
"""
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class RoutingMode(Enum):
    """Routing modes for query processing."""
    
    DIRECT = "direct"                      # Direct routing to single/simple patterns
    WORKFLOW_PLANNING = "workflow_planning"  # Complex workflow with DAG planning


class QueryComplexity(Enum):
    """Query complexity levels."""
    
    SIMPLE = "simple"          # Simple factual queries
    MODERATE = "moderate"      # Queries requiring some reasoning
    COMPLEX = "complex"        # Complex multi-step queries
    VERY_COMPLEX = "very_complex"  # Highly complex research queries


class ExecutionStrategy(Enum):
    """Pattern execution strategies."""
    
    SEQUENTIAL = "sequential"      # Execute patterns one after another
    PARALLEL = "parallel"          # Execute patterns in parallel
    CONDITIONAL = "conditional"    # Execute based on conditions
    LAYERED = "layered"           # Execute in layers (pipeline)
    FALLBACK = "fallback"         # Execute fallback on failure
    LOOP = "loop"                 # Execute repeatedly until threshold met


class QueryDomain(Enum):
    """Query domain classification."""
    
    GENERAL = "general"
    CODE = "code"
    SCIENTIFIC = "scientific"
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    CONVERSATIONAL = "conversational"
    MULTIMODAL = "multimodal"


class QueryIntent(Enum):
    """Query intent classification."""
    
    FACTUAL = "factual"              # Seeking facts
    ANALYTICAL = "analytical"        # Seeking analysis
    PROCEDURAL = "procedural"        # Seeking how-to
    COMPARATIVE = "comparative"      # Comparing options
    CREATIVE = "creative"            # Creative generation
    CONVERSATIONAL = "conversational"  # Conversational interaction


@dataclass
class QueryCharacteristics:
    """
    Characteristics extracted from a query.
    
    Attributes:
        query: Original query text
        complexity: Query complexity level
        domain: Query domain
        intent: Query intent
        
        # Query features
        length: Query length in words
        has_code: Whether query contains code
        has_technical_terms: Whether query has technical terminology
        has_numbers: Whether query contains numbers
        has_questions: Whether query has question marks
        
        # Requirements
        requires_accuracy: High accuracy required
        requires_speed: Fast response required
        requires_cost_optimization: Cost optimization required
        requires_multimodal: Multimodal understanding required
        requires_conversation_context: Conversation context required
        
        # Confidence
        confidence: Confidence in classification (0-1)
        reasoning: Reasoning for classification
    """
    
    query: str
    complexity: QueryComplexity = QueryComplexity.MODERATE
    domain: QueryDomain = QueryDomain.GENERAL
    intent: QueryIntent = QueryIntent.FACTUAL
    
    # Query features
    length: int = 0
    has_code: bool = False
    has_technical_terms: bool = False
    has_numbers: bool = False
    has_questions: bool = False
    
    # Requirements
    requires_accuracy: bool = False
    requires_speed: bool = False
    requires_cost_optimization: bool = False
    requires_multimodal: bool = False
    requires_conversation_context: bool = False
    
    # Confidence
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class QueryAnalysisResult:
    """
    Complete query analysis result with routing information.
    
    This extends QueryCharacteristics with routing-specific fields
    for production orchestration.
    
    Attributes:
        characteristics: Base query characteristics
        routing_mode: Routing mode (DIRECT or WORKFLOW_PLANNING)
        requires_composition: Whether query needs composite patterns
        sla_budget_ms: SLA budget in milliseconds
        recommended_strategy: Recommended execution strategy
    """
    
    characteristics: QueryCharacteristics
    routing_mode: RoutingMode
    requires_composition: bool
    sla_budget_ms: int
    recommended_strategy: ExecutionStrategy
    rewritten_queries: List[str] = field(default_factory=list)


class QueryAnalyzer:
    """
    Analyzes queries to determine optimal RAG patterns.
    
    Features:
    - Query complexity classification
    - Domain detection
    - Intent classification
    - Feature extraction
    - Requirement identification
    
    Usage:
        analyzer = QueryAnalyzer()
        
        # Analyze a query
        characteristics = analyzer.analyze("How do I implement binary search in Python?")
        
        # Get recommended patterns
        patterns = analyzer.recommend_patterns(characteristics)
    """
    
    # Domain keywords
    CODE_KEYWORDS = {
        "code", "function", "class", "method", "variable", "algorithm",
        "implement", "debug", "error", "exception", "syntax", "compile",
        "python", "java", "javascript", "c++", "rust", "go",
        "api", "library", "framework", "package", "module",
    }
    
    SCIENTIFIC_KEYWORDS = {
        "research", "study", "paper", "experiment", "hypothesis", "theory",
        "analysis", "data", "results", "conclusion", "methodology",
        "scientific", "academic", "journal", "publication", "citation",
    }
    
    MEDICAL_KEYWORDS = {
        "patient", "diagnosis", "treatment", "symptom", "disease", "medicine",
        "doctor", "hospital", "clinical", "medical", "health", "therapy",
        "drug", "prescription", "surgery", "condition",
    }
    
    LEGAL_KEYWORDS = {
        "law", "legal", "court", "case", "statute", "regulation", "contract",
        "attorney", "lawyer", "judge", "trial", "lawsuit", "liability",
        "rights", "obligation", "compliance", "precedent",
    }
    
    FINANCIAL_KEYWORDS = {
        "finance", "financial", "investment", "stock", "bond", "portfolio",
        "market", "trading", "profit", "loss", "revenue", "expense",
        "accounting", "tax", "budget", "forecast", "valuation",
    }
    
    # Technical terms
    TECHNICAL_TERMS = {
        "algorithm", "optimization", "performance", "scalability", "architecture",
        "infrastructure", "deployment", "configuration", "integration",
        "authentication", "authorization", "encryption", "security",
    }
    
    # Complexity indicators
    COMPLEX_INDICATORS = {
        "compare", "analyze", "evaluate", "explain", "describe",
        "why", "how", "what if", "pros and cons", "advantages and disadvantages",
        "step by step", "in detail", "comprehensive", "thorough",
    }
    
    # Accuracy indicators
    ACCURACY_INDICATORS = {
        "accurate", "precise", "exact", "correct", "verified", "validated",
        "reliable", "trustworthy", "authoritative", "official",
        "research", "scientific", "medical", "legal", "financial",
    }
    
    # Speed indicators
    SPEED_INDICATORS = {
        "quick", "fast", "rapid", "immediate", "instant", "brief",
        "summary", "overview", "tldr", "short", "concise",
    }
    
    def __init__(self):
        """Initialize the query analyzer."""
        pass
    
    def analyze(self, query: str, context: Optional[Dict] = None) -> QueryCharacteristics:
        """
        Analyze a query and extract characteristics.
        
        Args:
            query: Query text
            context: Optional context (conversation history, user preferences, etc.)
            
        Returns:
            QueryCharacteristics: Extracted characteristics
        """
        # Extract basic features
        length = len(query.split())
        has_code = self._detect_code(query)
        has_technical_terms = self._detect_technical_terms(query)
        has_numbers = self._detect_numbers(query)
        has_questions = "?" in query
        
        # Classify domain
        domain = self._classify_domain(query)
        
        # Classify complexity
        complexity = self._classify_complexity(query, length)
        
        # Classify intent
        intent = self._classify_intent(query)
        
        # Identify requirements
        requires_accuracy = self._requires_accuracy(query, domain)
        requires_speed = self._requires_speed(query)
        requires_cost_optimization = self._requires_cost_optimization(query, length)
        requires_multimodal = self._requires_multimodal(query, context)
        requires_conversation_context = self._requires_conversation_context(context)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            query, domain, complexity, intent
        )
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            query, domain, complexity, intent, length
        )
        
        return QueryCharacteristics(
            query=query,
            complexity=complexity,
            domain=domain,
            intent=intent,
            length=length,
            has_code=has_code,
            has_technical_terms=has_technical_terms,
            has_numbers=has_numbers,
            has_questions=has_questions,
            requires_accuracy=requires_accuracy,
            requires_speed=requires_speed,
            requires_cost_optimization=requires_cost_optimization,
            requires_multimodal=requires_multimodal,
            requires_conversation_context=requires_conversation_context,
            confidence=confidence,
            reasoning=reasoning,
        )
    
    def _detect_code(self, query: str) -> bool:
        """Detect if query contains code."""
        code_patterns = [
            r'```',  # Code blocks
            r'`[^`]+`',  # Inline code
            r'def\s+\w+\(',  # Python function
            r'function\s+\w+\(',  # JavaScript function
            r'class\s+\w+',  # Class definition
            r'\w+\.\w+\(',  # Method call
            r'import\s+\w+',  # Import statement
        ]
        
        for pattern in code_patterns:
            if re.search(pattern, query):
                return True
        
        return False
    
    def _detect_technical_terms(self, query: str) -> bool:
        """Detect if query contains technical terms."""
        query_lower = query.lower()
        return any(term in query_lower for term in self.TECHNICAL_TERMS)
    
    def _detect_numbers(self, query: str) -> bool:
        """Detect if query contains numbers."""
        return bool(re.search(r'\d+', query))
    
    def _classify_domain(self, query: str) -> QueryDomain:
        """Classify query domain."""
        query_lower = query.lower()
        
        # Count keyword matches for each domain
        domain_scores = {
            QueryDomain.CODE: sum(1 for kw in self.CODE_KEYWORDS if kw in query_lower),
            QueryDomain.SCIENTIFIC: sum(1 for kw in self.SCIENTIFIC_KEYWORDS if kw in query_lower),
            QueryDomain.MEDICAL: sum(1 for kw in self.MEDICAL_KEYWORDS if kw in query_lower),
            QueryDomain.LEGAL: sum(1 for kw in self.LEGAL_KEYWORDS if kw in query_lower),
            QueryDomain.FINANCIAL: sum(1 for kw in self.FINANCIAL_KEYWORDS if kw in query_lower),
        }
        
        # Get domain with highest score
        max_score = max(domain_scores.values())
        if max_score >= 2:  # Threshold for domain classification
            for domain, score in domain_scores.items():
                if score == max_score:
                    return domain
        
        return QueryDomain.GENERAL
    
    def _classify_complexity(self, query: str, length: int) -> QueryComplexity:
        """Classify query complexity."""
        query_lower = query.lower()
        
        # Count complexity indicators
        complexity_count = sum(
            1 for indicator in self.COMPLEX_INDICATORS
            if indicator in query_lower
        )
        
        # Classify based on length and indicators
        if length < 5 and complexity_count == 0:
            return QueryComplexity.SIMPLE
        elif length < 15 and complexity_count <= 1:
            return QueryComplexity.MODERATE
        elif length < 30 and complexity_count <= 2:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.VERY_COMPLEX
    
    def _classify_intent(self, query: str) -> QueryIntent:
        """Classify query intent."""
        query_lower = query.lower()
        
        # Check for intent patterns
        if any(word in query_lower for word in ["how to", "how do", "steps", "guide", "tutorial"]):
            return QueryIntent.PROCEDURAL
        elif any(word in query_lower for word in ["compare", "difference", "versus", "vs", "better"]):
            return QueryIntent.COMPARATIVE
        elif any(word in query_lower for word in ["analyze", "explain", "why", "reason", "cause"]):
            return QueryIntent.ANALYTICAL
        elif any(word in query_lower for word in ["create", "generate", "write", "design", "build"]):
            return QueryIntent.CREATIVE
        elif any(word in query_lower for word in ["chat", "talk", "discuss", "conversation"]):
            return QueryIntent.CONVERSATIONAL
        else:
            return QueryIntent.FACTUAL
    
    def _requires_accuracy(self, query: str, domain: QueryDomain) -> bool:
        """Check if query requires high accuracy."""
        query_lower = query.lower()
        
        # High-stakes domains always require accuracy
        if domain in [QueryDomain.MEDICAL, QueryDomain.LEGAL, QueryDomain.FINANCIAL]:
            return True
        
        # Check for accuracy indicators
        return any(indicator in query_lower for indicator in self.ACCURACY_INDICATORS)
    
    def _requires_speed(self, query: str) -> bool:
        """Check if query requires fast response."""
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in self.SPEED_INDICATORS)
    
    def _requires_cost_optimization(self, query: str, length: int) -> bool:
        """Check if query requires cost optimization."""
        # Long queries or batch queries benefit from cost optimization
        return length > 50 or "batch" in query.lower() or "many" in query.lower()
    
    def _requires_multimodal(self, query: str, context: Optional[Dict]) -> bool:
        """Check if query requires multimodal understanding."""
        query_lower = query.lower()
        
        # Check for multimodal keywords
        multimodal_keywords = {
            "image", "picture", "photo", "diagram", "chart", "graph",
            "video", "visual", "screenshot", "figure", "illustration",
        }
        
        if any(kw in query_lower for kw in multimodal_keywords):
            return True
        
        # Check context for multimodal content
        if context and context.get("has_images"):
            return True
        
        return False
    
    def _requires_conversation_context(self, context: Optional[Dict]) -> bool:
        """Check if query requires conversation context."""
        if not context:
            return False
        
        # Check if there's conversation history
        if context.get("conversation_history"):
            return True
        
        # Check if this is a follow-up query
        if context.get("is_followup"):
            return True
        
        return False
    
    def _calculate_confidence(
        self,
        query: str,
        domain: QueryDomain,
        complexity: QueryComplexity,
        intent: QueryIntent,
    ) -> float:
        """Calculate confidence in classification."""
        # Start with base confidence
        confidence = 0.7
        
        # Increase confidence for clear domain indicators
        query_lower = query.lower()
        if domain != QueryDomain.GENERAL:
            domain_keywords = {
                QueryDomain.CODE: self.CODE_KEYWORDS,
                QueryDomain.SCIENTIFIC: self.SCIENTIFIC_KEYWORDS,
                QueryDomain.MEDICAL: self.MEDICAL_KEYWORDS,
                QueryDomain.LEGAL: self.LEGAL_KEYWORDS,
                QueryDomain.FINANCIAL: self.FINANCIAL_KEYWORDS,
            }
            
            if domain in domain_keywords:
                keyword_count = sum(
                    1 for kw in domain_keywords[domain]
                    if kw in query_lower
                )
                confidence += min(keyword_count * 0.05, 0.2)
        
        # Increase confidence for clear intent indicators
        if intent != QueryIntent.FACTUAL:
            confidence += 0.05
        
        # Cap at 0.95
        return min(confidence, 0.95)
    
    def _generate_reasoning(
        self,
        query: str,
        domain: QueryDomain,
        complexity: QueryComplexity,
        intent: QueryIntent,
        length: int,
    ) -> str:
        """Generate reasoning for classification."""
        reasons = []
        
        # Domain reasoning
        if domain != QueryDomain.GENERAL:
            reasons.append(f"Domain: {domain.value} (detected domain-specific keywords)")
        
        # Complexity reasoning
        reasons.append(f"Complexity: {complexity.value} (query length: {length} words)")
        
        # Intent reasoning
        reasons.append(f"Intent: {intent.value}")
        
        return "; ".join(reasons)
    
    def recommend_patterns(
        self,
        characteristics: QueryCharacteristics,
    ) -> List[str]:
        """
        Recommend RAG patterns based on query characteristics.
        
        Args:
            characteristics: Query characteristics
            
        Returns:
            List of recommended pattern names (ordered by priority)
        """
        recommendations = []
        
        # Domain-specific patterns
        if characteristics.domain == QueryDomain.CODE:
            recommendations.append("code_rag")
        elif characteristics.domain == QueryDomain.CONVERSATIONAL:
            recommendations.append("coral")
        elif characteristics.requires_multimodal:
            recommendations.append("reveal")
        
        # Accuracy requirements
        if characteristics.requires_accuracy:
            if characteristics.complexity in [QueryComplexity.COMPLEX, QueryComplexity.VERY_COMPLEX]:
                recommendations.append("self_rag")
            recommendations.append("corrective_rag")
        
        # Speed requirements
        if characteristics.requires_speed:
            recommendations.append("adaptive_rag")
            recommendations.append("speculative_rag")
        
        # Cost optimization
        if characteristics.requires_cost_optimization:
            recommendations.append("corag")
            recommendations.append("adaptive_rag")
        
        # Conversation context
        if characteristics.requires_conversation_context:
            recommendations.append("coral")
        
        # Default: adaptive RAG for intelligent routing
        if not recommendations:
            recommendations.append("adaptive_rag")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for pattern in recommendations:
            if pattern not in seen:
                seen.add(pattern)
                unique_recommendations.append(pattern)
        
        return unique_recommendations
    
    def analyze_with_routing(
        self,
        query: str,
        context: Optional[Dict] = None
    ) -> QueryAnalysisResult:
        """
        Analyze query and determine routing strategy.
        
        This is the enhanced analysis method that includes routing logic
        for production orchestration.
        
        Args:
            query: Query text
            context: Optional context (conversation history, user preferences, etc.)
            
        Returns:
            QueryAnalysisResult: Complete analysis with routing information
        """
        # Step 1: Perform basic analysis
        characteristics = self.analyze(query, context)
        
        # Step 2: Determine routing mode
        routing_mode = self._determine_routing_mode(characteristics)

        # Step 2.5: Rewriting Query if needed
        rewritten_queries = self._rewrite_query_if_needed(query, characteristics)
        
        # Step 3: Check if composition is needed
        requires_composition = self._check_composition_need(characteristics)
        
        # Step 4: Assign SLA budget
        sla_budget_ms = self._assign_sla_budget(characteristics.complexity)
        
        # Step 5: Recommend execution strategy
        recommended_strategy = self._recommend_strategy(characteristics)
        
        logger.debug(
            f"Query analysis complete: routing_mode={routing_mode.value}, "
            f"requires_composition={requires_composition}, "
            f"sla_budget_ms={sla_budget_ms}, "
            f"strategy={recommended_strategy.value}"
        )
        
        return QueryAnalysisResult(
            characteristics=characteristics,
            routing_mode=routing_mode,
            requires_composition=requires_composition,
            sla_budget_ms=sla_budget_ms,
            recommended_strategy=recommended_strategy,
            rewritten_queries=rewritten_queries
        )
    
    def _rewrite_query_if_needed(
        self,
        query: str,
        characteristics: QueryCharacteristics
    ) -> List[str]:
        """
        Rewrite query if ambiguous or lacks context.
        
        Args:
            query: Original query
            characteristics: Analyzed characteristics
            
        Returns:
            List[str]: List of rewritten/expanded queries
        """
        rewritten = []
        
        # Placeholder logic for low confidence queries
        if characteristics.confidence < 0.7:
            logger.info(f"Query '{query}' has low confidence ({characteristics.confidence}). Tagged for optional rewriting.")
            
        return rewritten
    
    def _determine_routing_mode(
        self,
        characteristics: QueryCharacteristics
    ) -> RoutingMode:
        """
        Determine routing mode based on query characteristics.
        
        Simple queries use DIRECT routing (fast, single pattern).
        Complex queries use WORKFLOW_PLANNING (DAG-based, multi-pattern).
        """
        # Simple queries -> Direct routing
        if characteristics.complexity == QueryComplexity.SIMPLE:
            return RoutingMode.DIRECT
        
        # Complex queries with multiple requirements -> Workflow planning
        if characteristics.complexity in [QueryComplexity.COMPLEX, QueryComplexity.VERY_COMPLEX]:
            return RoutingMode.WORKFLOW_PLANNING
        
        # Moderate queries with high accuracy requirements -> Workflow planning
        if characteristics.complexity == QueryComplexity.MODERATE:
            if characteristics.requires_accuracy and characteristics.requires_multimodal:
                return RoutingMode.WORKFLOW_PLANNING
            if characteristics.requires_accuracy and characteristics.requires_conversation_context:
                return RoutingMode.WORKFLOW_PLANNING
        
        # Default: Direct routing for moderate queries
        return RoutingMode.DIRECT
    
    def _check_composition_need(
        self,
        characteristics: QueryCharacteristics
    ) -> bool:
        """Check if query requires composite pattern orchestration."""
        # Complex queries always need composition
        if characteristics.complexity in [QueryComplexity.COMPLEX, QueryComplexity.VERY_COMPLEX]:
            return True
        
        # Count active requirements
        requirement_count = sum([
            characteristics.requires_accuracy,
            characteristics.requires_speed,
            characteristics.requires_cost_optimization,
            characteristics.requires_multimodal,
            characteristics.requires_conversation_context,
        ])
        
        # Multiple requirements -> composition needed
        if requirement_count >= 2:
            return True
        
        # Specific combinations that benefit from composition
        if characteristics.requires_multimodal and characteristics.requires_conversation_context:
            return True
        
        if characteristics.requires_accuracy and characteristics.domain in [
            QueryDomain.MEDICAL, QueryDomain.LEGAL, QueryDomain.FINANCIAL
        ]:
            return True
        
        return False
    
    def _assign_sla_budget(
        self,
        complexity: QueryComplexity
    ) -> int:
        """
        Assign SLA budget based on query complexity.
        
        SLA budgets (in milliseconds):
        - SIMPLE: 2000ms (2 seconds)
        - MODERATE: 5000ms (5 seconds)
        - COMPLEX: 30000ms (30 seconds)
        - VERY_COMPLEX: 60000ms (60 seconds)
        """
        sla_budgets = {
            QueryComplexity.SIMPLE: 2000,
            QueryComplexity.MODERATE: 5000,
            QueryComplexity.COMPLEX: 30000,
            QueryComplexity.VERY_COMPLEX: 60000,
        }
        
        return sla_budgets.get(complexity, 5000)  # Default to moderate
    
    def _recommend_strategy(
        self,
        characteristics: QueryCharacteristics
    ) -> ExecutionStrategy:
        """Recommend execution strategy based on query characteristics."""
        # Speed requirements -> Parallel execution
        if characteristics.requires_speed:
            return ExecutionStrategy.PARALLEL
        
        # Accuracy requirements with complex queries -> Sequential with refinement
        if characteristics.requires_accuracy:
            if characteristics.complexity in [QueryComplexity.COMPLEX, QueryComplexity.VERY_COMPLEX]:
                return ExecutionStrategy.SEQUENTIAL
        
        # High-stakes domains -> Sequential with validation
        if characteristics.domain in [QueryDomain.MEDICAL, QueryDomain.LEGAL, QueryDomain.FINANCIAL]:
            return ExecutionStrategy.SEQUENTIAL
        
        # Conversational context -> Conditional (context-aware)
        if characteristics.requires_conversation_context:
            return ExecutionStrategy.CONDITIONAL
        
        # Default: Sequential for most queries
        return ExecutionStrategy.SEQUENTIAL


__all__ = [
    "RoutingMode",
    "QueryComplexity",
    "ExecutionStrategy",
    "QueryDomain",
    "QueryIntent",
    "QueryCharacteristics",
    "QueryAnalysisResult",
    "QueryAnalyzer",
]
