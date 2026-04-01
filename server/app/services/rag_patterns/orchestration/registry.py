"""
Pattern Registry - Central registry for all RAG patterns.

This module provides:
1. Pattern registration and metadata management
2. Pattern compatibility and conflict tracking
3. Pattern discovery and lookup
4. Pattern capability queries

Migrated from raganything/patterns/registry.py
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PatternCapability(Enum):
    """Capabilities that patterns can provide."""
    
    # Core capabilities
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    CORRECTION = "correction"
    REFINEMENT = "refinement"
    OPTIMIZATION = "optimization"
    
    # Specialized capabilities
    MULTIMODAL = "multimodal"
    CONVERSATIONAL = "conversational"
    CODE_ANALYSIS = "code_analysis"
    SCIENTIFIC = "scientific"
    COMPLIANCE = "compliance"
    
    # Performance capabilities
    COST_OPTIMIZATION = "cost_optimization"
    SPEED_OPTIMIZATION = "speed_optimization"
    ACCURACY_OPTIMIZATION = "accuracy_optimization"
    
    # Advanced capabilities
    SELF_CORRECTION = "self_correction"
    ADAPTIVE_ROUTING = "adaptive_routing"
    PARALLEL_EXECUTION = "parallel_execution"


class PatternDomain(Enum):
    """Domains that patterns are specialized for."""
    
    GENERAL = "general"
    CODE = "code"
    SCIENTIFIC = "scientific"
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    CONVERSATIONAL = "conversational"
    MULTIMODAL = "multimodal"


class PatternComplexity(Enum):
    """Complexity levels for patterns."""
    
    LOW = "low"          # Simple, fast patterns
    MEDIUM = "medium"    # Moderate complexity
    HIGH = "high"        # Complex, resource-intensive patterns


@dataclass
class PatternMetadata:
    """
    Metadata for a RAG pattern.
    
    Attributes:
        name: Pattern name (e.g., "corrective_rag")
        display_name: Human-readable name (e.g., "Corrective RAG")
        description: Brief description of the pattern
        capabilities: Set of capabilities this pattern provides
        domains: Domains this pattern is specialized for
        complexity: Complexity level of the pattern
        
        # Performance characteristics
        avg_latency_ms: Average latency in milliseconds
        cost_multiplier: Cost relative to baseline (1.0 = baseline)
        accuracy_boost: Accuracy improvement over baseline (0.0-1.0)
        
        # Compatibility
        compatible_with: Patterns this can be combined with
        conflicts_with: Patterns this conflicts with
        requires: Patterns that must be present for this to work
        
        # Configuration
        default_config: Default configuration parameters
        required_config: Required configuration parameters
        
        # Status
        enabled: Whether this pattern is enabled
        experimental: Whether this pattern is experimental
        version: Pattern version
    """
    
    name: str
    display_name: str
    description: str
    capabilities: Set[PatternCapability] = field(default_factory=set)
    domains: Set[PatternDomain] = field(default_factory=set)
    complexity: PatternComplexity = PatternComplexity.MEDIUM
    
    # Performance characteristics
    avg_latency_ms: float = 0.0
    cost_multiplier: float = 1.0
    accuracy_boost: float = 0.0
    
    # Compatibility
    compatible_with: Set[str] = field(default_factory=set)
    conflicts_with: Set[str] = field(default_factory=set)
    requires: Set[str] = field(default_factory=set)
    
    # Configuration
    default_config: Dict[str, Any] = field(default_factory=dict)
    required_config: Set[str] = field(default_factory=set)
    
    # Status
    enabled: bool = True
    experimental: bool = False
    version: str = "1.0.0"


class PatternRegistry:
    """
    Central registry for all RAG patterns.
    
    Features:
    - Pattern registration and metadata management
    - Pattern compatibility and conflict tracking
    - Pattern discovery and lookup
    - Pattern capability queries
    
    Usage:
        registry = PatternRegistry()
        
        # Register a pattern
        registry.register_pattern(
            name="corrective_rag",
            display_name="Corrective RAG",
            description="Validates and corrects retrieved information",
            capabilities={PatternCapability.CORRECTION, PatternCapability.RETRIEVAL},
            domains={PatternDomain.GENERAL},
        )
        
        # Get pattern metadata
        metadata = registry.get_pattern("corrective_rag")
        
        # Check compatibility
        compatible = registry.are_compatible("corrective_rag", "self_rag")
        
        # Find patterns by capability
        patterns = registry.find_by_capability(PatternCapability.CORRECTION)
    """
    
    def __init__(self):
        """Initialize the pattern registry."""
        self._patterns: Dict[str, PatternMetadata] = {}
        self._capability_index: Dict[PatternCapability, Set[str]] = {}
        self._domain_index: Dict[PatternDomain, Set[str]] = {}
        
        # Register built-in patterns
        self._register_builtin_patterns()
    
    def _register_builtin_patterns(self) -> None:
        """Register all built-in patterns with their metadata."""
        
        # Phase 1: Currently Implemented Patterns
        
        # Corrective RAG
        self.register_pattern(
            name="corrective_rag",
            display_name="Corrective RAG",
            description="Validates and corrects retrieved information using LLM-based relevance scoring and web search fallback",
            capabilities={
                PatternCapability.RETRIEVAL,
                PatternCapability.CORRECTION,
                PatternCapability.ACCURACY_OPTIMIZATION,
            },
            domains={PatternDomain.GENERAL},
            complexity=PatternComplexity.MEDIUM,
            avg_latency_ms=500,
            cost_multiplier=1.2,
            accuracy_boost=0.15,
            compatible_with={"self_rag", "adaptive_rag", "corag"},
            conflicts_with=set(),
        )
        
        # Self RAG
        self.register_pattern(
            name="self_rag",
            display_name="Self RAG",
            description="Iterative self-refinement and validation using NLI-based relevance checking and hallucination detection",
            capabilities={
                PatternCapability.GENERATION,
                PatternCapability.REFINEMENT,
                PatternCapability.SELF_CORRECTION,
                PatternCapability.ACCURACY_OPTIMIZATION,
            },
            domains={PatternDomain.GENERAL},
            complexity=PatternComplexity.HIGH,
            avg_latency_ms=1500,
            cost_multiplier=2.0,
            accuracy_boost=0.25,
            compatible_with={"corrective_rag", "adaptive_rag"},
            conflicts_with=set(),
        )
        
        # Adaptive RAG
        self.register_pattern(
            name="adaptive_rag",
            display_name="Adaptive RAG",
            description="Intelligently decides when to retrieve based on LLM confidence and query complexity",
            capabilities={
                PatternCapability.RETRIEVAL,
                PatternCapability.ADAPTIVE_ROUTING,
                PatternCapability.COST_OPTIMIZATION,
                PatternCapability.SPEED_OPTIMIZATION,
            },
            domains={PatternDomain.GENERAL},
            complexity=PatternComplexity.MEDIUM,
            avg_latency_ms=300,
            cost_multiplier=0.7,
            accuracy_boost=0.10,
            compatible_with={"corrective_rag", "self_rag", "corag"},
            conflicts_with=set(),
        )
        
        # CORAG
        self.register_pattern(
            name="corag",
            display_name="CORAG",
            description="Cost-constrained optimization using utility-based chunk selection and MCTS",
            capabilities={
                PatternCapability.RETRIEVAL,
                PatternCapability.OPTIMIZATION,
                PatternCapability.COST_OPTIMIZATION,
            },
            domains={PatternDomain.GENERAL},
            complexity=PatternComplexity.HIGH,
            avg_latency_ms=800,
            cost_multiplier=0.6,
            accuracy_boost=0.05,
            compatible_with={"corrective_rag", "adaptive_rag"},
            conflicts_with=set(),
        )
        
        # Phase 2: High-Priority Patterns
        
        # Speculative RAG
        self.register_pattern(
            name="speculative_rag",
            display_name="Speculative RAG",
            description="Parallel draft generation with small model and verification with large model",
            capabilities={
                PatternCapability.GENERATION,
                PatternCapability.PARALLEL_EXECUTION,
                PatternCapability.SPEED_OPTIMIZATION,
                PatternCapability.COST_OPTIMIZATION,
            },
            domains={PatternDomain.GENERAL},
            complexity=PatternComplexity.MEDIUM,
            avg_latency_ms=400,
            cost_multiplier=0.7,
            accuracy_boost=0.08,
            compatible_with={"adaptive_rag", "corag"},
            conflicts_with={"self_rag"},  # Both do generation refinement
        )
        
        # CORAL (Conversational RAG)
        self.register_pattern(
            name="coral",
            display_name="CORAL",
            description="Conversational RAG with multi-turn context tracking and conversation-aware retrieval",
            capabilities={
                PatternCapability.RETRIEVAL,
                PatternCapability.GENERATION,
                PatternCapability.CONVERSATIONAL,
            },
            domains={PatternDomain.CONVERSATIONAL},
            complexity=PatternComplexity.MEDIUM,
            avg_latency_ms=600,
            cost_multiplier=1.1,
            accuracy_boost=0.20,
            compatible_with={"corrective_rag", "adaptive_rag", "reveal"},
            conflicts_with=set(),
        )
        
        # Phase 3: Medium-Priority Patterns
        
        # REVEAL (Visual-Language RAG)
        self.register_pattern(
            name="reveal",
            display_name="REVEAL",
            description="Visual-language RAG with vision transformer encoding and multimodal fusion",
            capabilities={
                PatternCapability.RETRIEVAL,
                PatternCapability.GENERATION,
                PatternCapability.MULTIMODAL,
            },
            domains={PatternDomain.MULTIMODAL},
            complexity=PatternComplexity.HIGH,
            avg_latency_ms=1200,
            cost_multiplier=1.5,
            accuracy_boost=0.30,
            compatible_with={"coral", "adaptive_rag"},
            conflicts_with=set(),
        )
        
        # Phase 4: Domain-Specific Patterns
        
        # Code RAG
        self.register_pattern(
            name="code_rag",
            display_name="Code RAG",
            description="Code-specific RAG with AST parsing, symbol resolution, and code-aware retrieval",
            capabilities={
                PatternCapability.RETRIEVAL,
                PatternCapability.GENERATION,
                PatternCapability.CODE_ANALYSIS,
            },
            domains={PatternDomain.CODE},
            complexity=PatternComplexity.MEDIUM,
            avg_latency_ms=700,
            cost_multiplier=1.0,
            accuracy_boost=0.25,
            compatible_with={"corrective_rag", "self_rag"},
            conflicts_with=set(),
        )
        
        # Semantic Highlight RAG
        self.register_pattern(
            name="semantic_highlight",
            display_name="Semantic Highlight RAG",
            description="Post-retrieval optimization that filters sentences by semantic relevance, achieving 60-80% token reduction",
            capabilities={
                PatternCapability.OPTIMIZATION,
                PatternCapability.COST_OPTIMIZATION,
                PatternCapability.ACCURACY_OPTIMIZATION,
            },
            domains={PatternDomain.GENERAL},
            complexity=PatternComplexity.LOW,
            avg_latency_ms=200,
            cost_multiplier=0.3,  # Reduces tokens by 60-80%
            accuracy_boost=0.12,
            compatible_with={"corrective_rag", "self_rag", "adaptive_rag", "corag", "speculative_rag", "coral", "reveal", "code_rag"},
            conflicts_with=set(),
        )
        
        logger.info(f"Registered {len(self._patterns)} built-in patterns")
    
    def register_pattern(
        self,
        name: str,
        display_name: str,
        description: str,
        capabilities: Set[PatternCapability] = None,
        domains: Set[PatternDomain] = None,
        complexity: PatternComplexity = PatternComplexity.MEDIUM,
        avg_latency_ms: float = 0.0,
        cost_multiplier: float = 1.0,
        accuracy_boost: float = 0.0,
        compatible_with: Set[str] = None,
        conflicts_with: Set[str] = None,
        requires: Set[str] = None,
        default_config: Dict[str, Any] = None,
        required_config: Set[str] = None,
        enabled: bool = True,
        experimental: bool = False,
        version: str = "1.0.0",
    ) -> None:
        """
        Register a pattern with the registry.
        
        Args:
            name: Pattern name (unique identifier)
            display_name: Human-readable name
            description: Brief description
            capabilities: Set of capabilities
            domains: Set of domains
            complexity: Complexity level
            avg_latency_ms: Average latency
            cost_multiplier: Cost relative to baseline
            accuracy_boost: Accuracy improvement
            compatible_with: Compatible patterns
            conflicts_with: Conflicting patterns
            requires: Required patterns
            default_config: Default configuration
            required_config: Required configuration keys
            enabled: Whether enabled
            experimental: Whether experimental
            version: Pattern version
        """
        if name in self._patterns:
            logger.warning(f"Pattern '{name}' already registered, overwriting")
        
        metadata = PatternMetadata(
            name=name,
            display_name=display_name,
            description=description,
            capabilities=capabilities or set(),
            domains=domains or {PatternDomain.GENERAL},
            complexity=complexity,
            avg_latency_ms=avg_latency_ms,
            cost_multiplier=cost_multiplier,
            accuracy_boost=accuracy_boost,
            compatible_with=compatible_with or set(),
            conflicts_with=conflicts_with or set(),
            requires=requires or set(),
            default_config=default_config or {},
            required_config=required_config or set(),
            enabled=enabled,
            experimental=experimental,
            version=version,
        )
        
        self._patterns[name] = metadata
        
        # Update capability index
        for capability in metadata.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(name)
        
        # Update domain index
        for domain in metadata.domains:
            if domain not in self._domain_index:
                self._domain_index[domain] = set()
            self._domain_index[domain].add(name)
        
        logger.debug(f"Registered pattern: {name}")
    
    def get_pattern(self, name: str) -> Optional[PatternMetadata]:
        """Get pattern metadata by name."""
        return self._patterns.get(name)
    
    def list_patterns(
        self,
        enabled_only: bool = True,
        include_experimental: bool = False,
    ) -> List[PatternMetadata]:
        """List all registered patterns."""
        patterns = []
        for metadata in self._patterns.values():
            if enabled_only and not metadata.enabled:
                continue
            if not include_experimental and metadata.experimental:
                continue
            patterns.append(metadata)
        return patterns
    
    def find_by_capability(
        self,
        capability: PatternCapability,
        enabled_only: bool = True,
    ) -> List[PatternMetadata]:
        """Find patterns by capability."""
        pattern_names = self._capability_index.get(capability, set())
        patterns = []
        for name in pattern_names:
            metadata = self._patterns[name]
            if enabled_only and not metadata.enabled:
                continue
            patterns.append(metadata)
        return patterns
    
    def find_by_domain(
        self,
        domain: PatternDomain,
        enabled_only: bool = True,
    ) -> List[PatternMetadata]:
        """Find patterns by domain."""
        pattern_names = self._domain_index.get(domain, set())
        patterns = []
        for name in pattern_names:
            metadata = self._patterns[name]
            if enabled_only and not metadata.enabled:
                continue
            patterns.append(metadata)
        return patterns
    
    def are_compatible(self, pattern1: str, pattern2: str) -> bool:
        """Check if two patterns are compatible."""
        metadata1 = self.get_pattern(pattern1)
        metadata2 = self.get_pattern(pattern2)
        
        if not metadata1 or not metadata2:
            return False
        
        # Check explicit conflicts
        if pattern2 in metadata1.conflicts_with:
            return False
        if pattern1 in metadata2.conflicts_with:
            return False
        
        # Check if explicitly compatible
        if pattern2 in metadata1.compatible_with:
            return True
        if pattern1 in metadata2.compatible_with:
            return True
        
        # Default: compatible if no conflicts
        return True
    
    def check_requirements(self, pattern: str, available: Set[str]) -> bool:
        """Check if pattern requirements are satisfied."""
        metadata = self.get_pattern(pattern)
        if not metadata:
            return False
        return metadata.requires.issubset(available)
    
    def get_conflicts(self, patterns: List[str]) -> List[tuple]:
        """Get all conflicts in a list of patterns."""
        conflicts = []
        for i, pattern1 in enumerate(patterns):
            for pattern2 in patterns[i + 1:]:
                if not self.are_compatible(pattern1, pattern2):
                    conflicts.append((pattern1, pattern2))
        return conflicts
    
    def validate_combination(
        self,
        patterns: List[str],
    ) -> tuple:
        """Validate a pattern combination."""
        errors = []
        
        # Check if all patterns exist
        for pattern in patterns:
            if pattern not in self._patterns:
                errors.append(f"Pattern '{pattern}' not found")
        
        if errors:
            return False, errors
        
        # Check if all patterns are enabled
        for pattern in patterns:
            metadata = self._patterns[pattern]
            if not metadata.enabled:
                errors.append(f"Pattern '{pattern}' is disabled")
        
        # Check for conflicts
        conflicts = self.get_conflicts(patterns)
        for pattern1, pattern2 in conflicts:
            errors.append(f"Patterns '{pattern1}' and '{pattern2}' conflict")
        
        # Check requirements
        available = set(patterns)
        for pattern in patterns:
            if not self.check_requirements(pattern, available):
                metadata = self._patterns[pattern]
                missing = metadata.requires - available
                errors.append(
                    f"Pattern '{pattern}' requires: {', '.join(missing)}"
                )
        
        return len(errors) == 0, errors
    
    def estimate_combination_metrics(
        self,
        patterns: List[str],
    ) -> Dict[str, float]:
        """Estimate metrics for a pattern combination."""
        if not patterns:
            return {
                "total_latency_ms": 0.0,
                "total_cost_multiplier": 1.0,
                "total_accuracy_boost": 0.0,
            }
        
        # Sum latencies (sequential execution)
        total_latency = sum(
            self._patterns[p].avg_latency_ms
            for p in patterns
            if p in self._patterns
        )
        
        # Multiply cost multipliers
        total_cost = 1.0
        for pattern in patterns:
            if pattern in self._patterns:
                total_cost *= self._patterns[pattern].cost_multiplier
        
        # Sum accuracy boosts (with diminishing returns)
        total_accuracy = 0.0
        for i, pattern in enumerate(patterns):
            if pattern in self._patterns:
                boost = self._patterns[pattern].accuracy_boost
                # Diminishing returns: each additional pattern contributes less
                total_accuracy += boost * (0.8 ** i)
        
        return {
            "total_latency_ms": total_latency,
            "total_cost_multiplier": total_cost,
            "total_accuracy_boost": min(total_accuracy, 1.0),  # Cap at 100%
        }


# Global registry instance
_registry: Optional[PatternRegistry] = None


def get_registry() -> PatternRegistry:
    """Get the global pattern registry instance."""
    global _registry
    if _registry is None:
        _registry = PatternRegistry()
    return _registry


__all__ = [
    "PatternCapability",
    "PatternDomain",
    "PatternComplexity",
    "PatternMetadata",
    "PatternRegistry",
    "get_registry",
]
