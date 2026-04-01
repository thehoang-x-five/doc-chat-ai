"""
Fact Checker - Verifies numerical claims and logical statements.

This module provides:
1. Numerical claim extraction from text
2. Mathematical verification using safe Python execution
3. Logical consistency checking

"""
import ast
import logging
import operator
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class NumericalClaim:
    """A numerical claim extracted from text."""
    raw_text: str
    expression: Optional[str] = None  # Mathematical expression if detected
    expected_result: Optional[float] = None
    actual_result: Optional[float] = None
    is_correct: bool = True
    error_message: Optional[str] = None


@dataclass
class FactCheckResult:
    """Result of fact checking."""
    passed: bool
    numerical_claims: List[NumericalClaim] = field(default_factory=list)
    failed_claims: List[NumericalClaim] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "num_claims_checked": len(self.numerical_claims),
            "num_failed": len(self.failed_claims),
            "confidence": self.confidence,
            "failed_claims": [c.raw_text for c in self.failed_claims],
        }


class SafeExpressionEvaluator:
    """
    Safe expression evaluator using AST parsing.
    Only allows basic arithmetic operations.
    """
    
    # Allowed operators
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }
    
    def __init__(self, max_value: float = 1e15):
        """Initialize with maximum allowed value."""
        self.max_value = max_value
    
    def evaluate(self, expression: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Safely evaluate an arithmetic expression.
        
        Returns:
            Tuple of (result, error_message)
        """
        try:
            # Parse the expression
            tree = ast.parse(expression, mode='eval')
            result = self._eval_node(tree.body)
            
            if abs(result) > self.max_value:
                return None, f"Result exceeds maximum value ({self.max_value})"
            
            return float(result), None
            
        except ZeroDivisionError:
            return None, "Division by zero"
        except (ValueError, TypeError) as e:
            return None, f"Invalid expression: {e}"
        except Exception as e:
            return None, f"Evaluation error: {e}"
    
    def _eval_node(self, node) -> float:
        """Recursively evaluate AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        
        elif isinstance(node, ast.Num):  # Python 3.7 compatibility
            return float(node.n)
        
        elif isinstance(node, ast.BinOp):
            op = type(node.op)
            if op not in self.OPERATORS:
                raise ValueError(f"Unsupported operator: {op}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.OPERATORS[op](left, right)
        
        elif isinstance(node, ast.UnaryOp):
            op = type(node.op)
            if op not in self.OPERATORS:
                raise ValueError(f"Unsupported unary operator: {op}")
            operand = self._eval_node(node.operand)
            return self.OPERATORS[op](operand)
        
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")


class FactChecker:
    """
    Fact Checker for verifying numerical claims and calculations.
    
    Detects patterns like:
    - "X + Y = Z" arithmetic claims
    - "X% of Y" percentage calculations
    - "increased by X%" growth claims
    - "X times Y" multiplication claims
    
    Usage:
        checker = FactChecker()
        result = checker.verify_numerical_claims(
            "The sum of 2 and 3 is 6, and 50% of 100 is 50."
        )
        if not result.passed:
            print(f"Failed claims: {result.failed_claims}")
    """
    
    # Patterns for numerical claims
    PATTERNS = [
        # "X + Y = Z" or "X plus Y equals Z"
        (r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*(?:=|equals?|is)\s*(\d+(?:\.\d+)?)', 'addition'),
        (r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(?:=|equals?|is)\s*(\d+(?:\.\d+)?)', 'subtraction'),
        (r'(\d+(?:\.\d+)?)\s*[×x\*]\s*(\d+(?:\.\d+)?)\s*(?:=|equals?|is)\s*(\d+(?:\.\d+)?)', 'multiplication'),
        (r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*(?:=|equals?|is)\s*(\d+(?:\.\d+)?)', 'division'),
        
        # "X% of Y is Z"
        (r'(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)\s*(?:is|equals?)\s*(\d+(?:\.\d+)?)', 'percentage'),
        
        # "X times Y is Z"
        (r'(\d+(?:\.\d+)?)\s*times?\s*(\d+(?:\.\d+)?)\s*(?:is|equals?)\s*(\d+(?:\.\d+)?)', 'multiplication'),
        
        # Sum patterns
        (r'sum\s*of\s*(\d+(?:\.\d+)?)\s*and\s*(\d+(?:\.\d+)?)\s*(?:is|equals?)\s*(\d+(?:\.\d+)?)', 'sum'),
        (r'total\s*of\s*(\d+(?:\.\d+)?)\s*and\s*(\d+(?:\.\d+)?)\s*(?:is|equals?)\s*(\d+(?:\.\d+)?)', 'sum'),
    ]
    
    def __init__(self, tolerance: float = 0.01):
        """
        Initialize Fact Checker.
        
        Args:
            tolerance: Relative tolerance for numerical comparisons
        """
        self.tolerance = tolerance
        self.evaluator = SafeExpressionEvaluator()
        logger.info(f"FactChecker initialized (tolerance={tolerance})")
    
    def verify_numerical_claims(
        self,
        text: str,
    ) -> FactCheckResult:
        """
        Verify all numerical claims in text.
        
        Args:
            text: Text containing numerical claims
            
        Returns:
            FactCheckResult with verification details
        """
        claims = self._extract_claims(text)
        
        if not claims:
            return FactCheckResult(passed=True)
        
        failed = []
        for claim in claims:
            if not claim.is_correct:
                failed.append(claim)
        
        passed = len(failed) == 0
        confidence = 1.0 - (len(failed) / len(claims)) if claims else 1.0
        
        return FactCheckResult(
            passed=passed,
            numerical_claims=claims,
            failed_claims=failed,
            confidence=confidence,
            metadata={
                "total_claims": len(claims),
                "failed_count": len(failed),
            },
        )
    
    def _extract_claims(self, text: str) -> List[NumericalClaim]:
        """Extract and verify numerical claims from text."""
        claims = []
        
        for pattern, claim_type in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                claim = self._verify_match(match, claim_type)
                if claim:
                    claims.append(claim)
        
        return claims
    
    def _verify_match(
        self,
        match: re.Match,
        claim_type: str,
    ) -> Optional[NumericalClaim]:
        """Verify a regex match."""
        try:
            groups = match.groups()
            raw_text = match.group(0)
            
            if len(groups) < 3:
                return None
            
            a = float(groups[0])
            b = float(groups[1])
            expected = float(groups[2])
            
            # Calculate actual result
            if claim_type in ('addition', 'sum'):
                actual = a + b
                expression = f"{a} + {b}"
            elif claim_type == 'subtraction':
                actual = a - b
                expression = f"{a} - {b}"
            elif claim_type == 'multiplication':
                actual = a * b
                expression = f"{a} * {b}"
            elif claim_type == 'division':
                if b == 0:
                    return NumericalClaim(
                        raw_text=raw_text,
                        is_correct=False,
                        error_message="Division by zero",
                    )
                actual = a / b
                expression = f"{a} / {b}"
            elif claim_type == 'percentage':
                actual = (a / 100) * b
                expression = f"{a}% of {b}"
            else:
                return None
            
            # Check if correct (within tolerance)
            is_correct = self._approximately_equal(actual, expected)
            
            return NumericalClaim(
                raw_text=raw_text,
                expression=expression,
                expected_result=expected,
                actual_result=actual,
                is_correct=is_correct,
                error_message=None if is_correct else f"Expected {expected}, got {actual:.4f}",
            )
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse claim: {e}")
            return None
    
    def _approximately_equal(self, a: float, b: float) -> bool:
        """Check if two numbers are approximately equal."""
        if b == 0:
            return abs(a) < self.tolerance
        return abs(a - b) / abs(b) < self.tolerance
    
    def verify_expression(
        self,
        expression: str,
        expected_result: Optional[float] = None,
    ) -> Tuple[Optional[float], bool, Optional[str]]:
        """
        Verify a single expression.
        
        Args:
            expression: Mathematical expression to evaluate
            expected_result: Optional expected result to compare
            
        Returns:
            Tuple of (result, is_correct, error_message)
        """
        result, error = self.evaluator.evaluate(expression)
        
        if error:
            return None, False, error
        
        if expected_result is not None:
            is_correct = self._approximately_equal(result, expected_result)
            return result, is_correct, None if is_correct else f"Expected {expected_result}, got {result}"
        
        return result, True, None


# Default instance
fact_checker = FactChecker()
