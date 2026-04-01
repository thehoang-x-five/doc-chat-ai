"""
Code RAG Service - Code-aware queries and analysis.

Coordinates code parsing, symbol resolution, and code-aware RAG queries.
Consolidated from: base.py, code_parser.py, symbol_resolver.py, doc_extractor.py
"""
import ast
import logging
from pathlib import Path
from typing import Any, Callable

from .models import (
    Symbol, SymbolType, CodeContext, CodeAnalysis, CodeRAGResult
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Components
# =============================================================================

class CodeParser:
    """Parses code files using AST."""

    def parse_file(self, file_path: str) -> CodeAnalysis:
        """Parse a code file and extract symbols."""
        path = Path(file_path)
        language = self._detect_language(path)
        symbols = []
        imports = []
        
        if language == "python":
            try:
                with open(path, "r", encoding="utf-8") as f:
                    source = f.read()
                
                tree = ast.parse(source)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        symbols.append(Symbol(
                            name=node.name,
                            type=SymbolType.FUNCTION,
                            file_path=str(path),
                            line_number=node.lineno,
                            docstring=ast.get_docstring(node),
                            signature=self._extract_signature(node)
                        ))
                    elif isinstance(node, ast.ClassDef):
                        symbols.append(Symbol(
                            name=node.name,
                            type=SymbolType.CLASS,
                            file_path=str(path),
                            line_number=node.lineno,
                            docstring=ast.get_docstring(node)
                        ))
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports.extend(self._extract_imports(node))
                        
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
        
        doc_coverage = sum(1 for s in symbols if s.docstring) / len(symbols) if symbols else 0.0
        
        return CodeAnalysis(
            file_path=str(path),
            language=language,
            symbols=symbols,
            imports=imports,
            documentation_coverage=doc_coverage
        )

    def _detect_language(self, path: Path) -> str:
        ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".java": "java"}
        return ext_map.get(path.suffix.lower(), "unknown")

    def _extract_signature(self, node: ast.FunctionDef) -> str:
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"{node.name}({', '.join(args)})"

    def _extract_imports(self, node) -> list[str]:
        imports = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
        return imports


class SymbolResolver:
    """Resolves and tracks code symbols."""

    def __init__(self):
        self._symbols: dict[str, Symbol] = {}
        self._by_type: dict[SymbolType, list[Symbol]] = {}

    def add_symbols(self, symbols: list[Symbol]) -> None:
        for s in symbols:
            key = f"{s.file_path}::{s.name}"
            self._symbols[key] = s
            if s.type not in self._by_type:
                self._by_type[s.type] = []
            self._by_type[s.type].append(s)

    def resolve_symbol(self, name: str) -> Symbol | None:
        for key, symbol in self._symbols.items():
            if symbol.name.lower() == name.lower():
                return symbol
        return None

    def find_related_symbols(self, symbol: Symbol, max_depth: int = 1) -> list[Symbol]:
        """Find symbols related to given symbol."""
        related = []
        for s in self._symbols.values():
            if s.file_path == symbol.file_path and s.name != symbol.name:
                related.append(s)
        return related[:5]

    def clear(self) -> None:
        self._symbols.clear()
        self._by_type.clear()


class DocExtractor:
    """Extracts and processes documentation."""

    def extract_from_symbol(self, symbol: Symbol) -> str:
        """Extract documentation from symbol."""
        parts = [f"**{symbol.name}** ({symbol.type.value})"]
        
        if symbol.signature:
            parts.append(f"```\n{symbol.signature}\n```")
        
        if symbol.docstring:
            parts.append(symbol.docstring[:500])
        
        parts.append(f"File: {symbol.file_path}:{symbol.line_number}")
        return "\n".join(parts)

    def extract_code_examples(self, text: str) -> list[str]:
        """Extract code blocks from text."""
        examples = []
        in_code = False
        current = []
        
        for line in text.split("\n"):
            if line.startswith("```"):
                if in_code:
                    examples.append("\n".join(current))
                    current = []
                in_code = not in_code
            elif in_code:
                current.append(line)
        
        return examples

    def summarize_documentation(self, docs: list[str], max_length: int = 200) -> str:
        combined = " ".join(docs)
        return combined[:max_length] + "..." if len(combined) > max_length else combined


# =============================================================================
# Main Service
# =============================================================================

class CodeRAGService:
    """
    Code RAG Service for code-aware queries.
    
    Features:
    - AST-based code parsing
    - Symbol resolution and tracking
    - Documentation extraction
    - Code-aware retrieval
    - Context-aware code generation
    """

    def __init__(self, max_context_symbols: int = 10, include_related_symbols: bool = True):
        self.max_context_symbols = max_context_symbols
        self.include_related_symbols = include_related_symbols
        
        self.parser = CodeParser()
        self.resolver = SymbolResolver()
        self.doc_extractor = DocExtractor()

        logger.info(f"CodeRAGService: max_context_symbols={max_context_symbols}")

    async def analyze_file(self, file_path: str) -> CodeAnalysis:
        """Analyze a single code file."""
        logger.info(f"Analyzing file: {file_path}")
        analysis = self.parser.parse_file(file_path)
        self.resolver.add_symbols(analysis.symbols)
        return analysis

    async def analyze_codebase(self, directory: str, extensions: list[str] | None = None) -> list[CodeAnalysis]:
        """Analyze an entire codebase."""
        if extensions is None:
            extensions = [".py"]
        
        logger.info(f"Analyzing codebase: {directory}")
        analyses = []
        
        for ext in extensions:
            for file_path in Path(directory).rglob(f"*{ext}"):
                try:
                    analyses.append(await self.analyze_file(str(file_path)))
                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {e}")
        
        logger.info(f"Analyzed {len(analyses)} files")
        return analyses

    async def query(
        self,
        query: str,
        retrieve_func: Callable | None = None,
        generate_func: Callable | None = None,
        language: str = "python"
    ) -> CodeRAGResult:
        """Execute a code-aware RAG query."""
        logger.info(f"Processing code query: {query}")
        
        code_context = await self._build_code_context(query, language)
        
        if retrieve_func:
            code_context.code_snippets = await retrieve_func(query)
        
        relevant_symbols = self._find_relevant_symbols(query, code_context)
        
        if generate_func:
            context_text = self._format_context_for_generation(code_context, relevant_symbols)
            answer = await generate_func(query, context_text)
        else:
            answer = self._generate_default_answer(query, relevant_symbols)
        
        code_examples = self.doc_extractor.extract_code_examples(answer)
        confidence = self._calculate_confidence(query, relevant_symbols)

        return CodeRAGResult(
            query=query,
            answer=answer,
            code_context=code_context,
            relevant_symbols=relevant_symbols,
            code_examples=code_examples,
            confidence=confidence,
            sources=[s.file_path for s in relevant_symbols],
            metadata={"language": language, "num_symbols": len(relevant_symbols)}
        )

    async def _build_code_context(self, query: str, language: str) -> CodeContext:
        words = query.lower().split()
        matching = [self.resolver.resolve_symbol(w) for w in words]
        matching = [s for s in matching if s]
        
        return CodeContext(
            query=query,
            language=language,
            symbols=matching[:self.max_context_symbols],
            imports=[s.name for s in matching if s.type == SymbolType.IMPORT]
        )

    def _find_relevant_symbols(self, query: str, context: CodeContext) -> list[Symbol]:
        relevant = list(context.symbols)
        
        if self.include_related_symbols:
            for s in context.symbols:
                relevant.extend(self.resolver.find_related_symbols(s)[:3])
        
        seen = set()
        unique = []
        for s in relevant:
            key = f"{s.file_path}::{s.name}"
            if key not in seen:
                seen.add(key)
                unique.append(s)
        
        return unique[:self.max_context_symbols]

    def _format_context_for_generation(self, context: CodeContext, symbols: list[Symbol]) -> str:
        lines = ["# Code Context", ""]
        
        if symbols:
            lines.append("## Relevant Symbols")
            for s in symbols:
                doc = self.doc_extractor.extract_from_symbol(s)
                lines.extend([f"### {s.name}", doc, ""])
        
        if context.imports:
            lines.append("## Imports")
            lines.extend([f"- {i}" for i in context.imports])
        
        return "\n".join(lines)

    def _generate_default_answer(self, query: str, symbols: list[Symbol]) -> str:
        if not symbols:
            return f"No relevant code symbols found for: {query}"
        
        lines = [f"Found {len(symbols)} relevant symbols:", ""]
        for s in symbols[:5]:
            lines.append(f"- **{s.name}** ({s.type.value})")
            if s.docstring:
                lines.append(f"  {s.docstring[:100]}...")
        
        return "\n".join(lines)

    def _calculate_confidence(self, query: str, symbols: list[Symbol]) -> float:
        if not symbols:
            return 0.0
        base = min(len(symbols) / self.max_context_symbols, 1.0)
        doc_bonus = sum(1 for s in symbols if s.docstring) / len(symbols) * 0.2
        return min(base + doc_bonus, 1.0)

    def clear_cache(self) -> None:
        self.resolver.clear()
        logger.info("Code RAG cache cleared")
