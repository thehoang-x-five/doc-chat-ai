"""
Function Registry Service cho LLM Function Calling.

Module này cung cấp khả năng function calling cho tương tác LLM,
cho phép AI thực thi các functions và tools bên ngoài khi cần.

CHIẾN LƯỢC:
- Đăng ký functions với JSON schemas
- Thực thi functions được LLM yêu cầu
- Xử lý lỗi một cách graceful
- Hỗ trợ sequential tool use

"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID
import asyncio
import inspect
import json
import logging
import traceback

logger = logging.getLogger(__name__)


class FunctionStatus(str, Enum):
    """Trạng thái thực thi function."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    TIMEOUT = "timeout"


@dataclass
class FunctionParameter:
    """Định nghĩa một parameter của function."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None
    items: Optional[Dict[str, Any]] = None  # Cho array types


@dataclass
class FunctionDefinition:
    """Định nghĩa một callable function."""
    name: str
    description: str
    parameters: List[FunctionParameter]
    handler: Callable
    category: str = "general"
    requires_auth: bool = False
    timeout_seconds: int = 30
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Chuyển sang OpenAI function calling schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.items:
                prop["items"] = param.items
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
    
    def to_claude_schema(self) -> Dict[str, Any]:
        """Chuyển sang Claude/Anthropic tool schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.items:
                prop["items"] = param.items
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


@dataclass
class FunctionCall:
    """Ghi lại một lần gọi function."""
    id: str
    function_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    status: FunctionStatus = FunctionStatus.PENDING
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FunctionCallResult:
    """Kết quả thực thi một function."""
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time_ms: int = 0


class FunctionRegistry:
    """
    Registry để quản lý các callable functions.
    
    Cung cấp:
    - Đăng ký function với JSON schemas
    - Thực thi function với error handling
    - Hỗ trợ sequential tool use
    - Xử lý timeout
    
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    
    def __init__(self):
        """Khởi tạo function registry."""
        self._functions: Dict[str, FunctionDefinition] = {}
        self._call_history: List[FunctionCall] = []
        self._max_history = 100
    
    def register(
        self,
        name: str,
        description: str,
        parameters: List[FunctionParameter],
        handler: Callable,
        category: str = "general",
        requires_auth: bool = False,
        timeout_seconds: int = 30,
    ) -> None:
        """
        Đăng ký một function cho LLM calling.
        
        Args:
            name: Tên function duy nhất
            description: Mô tả để LLM hiểu khi nào dùng
            parameters: Danh sách định nghĩa parameters
            handler: Async hoặc sync callable để thực thi
            category: Category để nhóm functions
            requires_auth: Function có cần authentication không
            timeout_seconds: Thời gian thực thi tối đa
            
        Requirements: 6.1, 6.2
        """
        if name in self._functions:
            logger.warning(f"Ghi đè function đã tồn tại: {name}")
        
        self._functions[name] = FunctionDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            category=category,
            requires_auth=requires_auth,
            timeout_seconds=timeout_seconds,
        )
        logger.info(f"Đã đăng ký function: {name} (category: {category})")
    
    def register_decorator(
        self,
        name: Optional[str] = None,
        description: str = "",
        category: str = "general",
        requires_auth: bool = False,
        timeout_seconds: int = 30,
    ) -> Callable:
        """
        Decorator để đăng ký functions.
        
        Cách dùng:
            @registry.register_decorator(
                name="search_documents",
                description="Tìm kiếm documents trong knowledge base"
            )
            async def search_documents(query: str, limit: int = 10):
                ...
        """
        def decorator(func: Callable) -> Callable:
            func_name = name or func.__name__
            func_description = description or func.__doc__ or ""
            
            # Trích xuất parameters từ function signature
            sig = inspect.signature(func)
            params = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                
                # Xác định type từ annotation
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "number"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == list or str(param.annotation).startswith("List"):
                        param_type = "array"
                    elif param.annotation == dict or str(param.annotation).startswith("Dict"):
                        param_type = "object"
                
                # Xác định có required không
                required = param.default == inspect.Parameter.empty
                default = None if required else param.default
                
                params.append(FunctionParameter(
                    name=param_name,
                    type=param_type,
                    description=f"Parameter: {param_name}",
                    required=required,
                    default=default,
                ))
            
            self.register(
                name=func_name,
                description=func_description,
                parameters=params,
                handler=func,
                category=category,
                requires_auth=requires_auth,
                timeout_seconds=timeout_seconds,
            )
            
            return func
        
        return decorator
    
    def unregister(self, name: str) -> bool:
        """
        Hủy đăng ký một function.
        
        Args:
            name: Tên function cần xóa
            
        Returns:
            True nếu function đã được xóa, False nếu không tìm thấy
        """
        if name in self._functions:
            del self._functions[name]
            logger.info(f"Đã hủy đăng ký function: {name}")
            return True
        return False
    
    def get_function(self, name: str) -> Optional[FunctionDefinition]:
        """Lấy định nghĩa function theo tên."""
        return self._functions.get(name)
    
    def list_functions(
        self,
        category: Optional[str] = None,
    ) -> List[FunctionDefinition]:
        """
        Liệt kê tất cả functions đã đăng ký.
        
        Args:
            category: Lọc theo category (tùy chọn)
            
        Returns:
            Danh sách định nghĩa functions
        """
        functions = list(self._functions.values())
        if category:
            functions = [f for f in functions if f.category == category]
        return functions
    
    def get_schemas_for_provider(
        self,
        provider: str = "openai",
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lấy function schemas được format cho provider cụ thể.
        
        Args:
            provider: "openai", "claude", hoặc "gemini"
            category: Lọc theo category (tùy chọn)
            
        Returns:
            Danh sách function schemas
        """
        functions = self.list_functions(category)
        
        if provider in ("openai", "gemini"):
            return [f.to_openai_schema() for f in functions]
        elif provider == "claude":
            return [f.to_claude_schema() for f in functions]
        else:
            # Mặc định dùng OpenAI format
            return [f.to_openai_schema() for f in functions]

    
    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> FunctionCallResult:
        """
        Thực thi một function đã đăng ký.
        
        Args:
            name: Tên function cần thực thi
            arguments: Arguments truyền cho function
            context: Context tùy chọn (user_id, workspace_id, etc.)
            
        Returns:
            FunctionCallResult with success status and result/error

        """
        import time
        start_time = time.time()
        
        # Lấy định nghĩa function
        func_def = self._functions.get(name)
        if not func_def:
            return FunctionCallResult(
                success=False,
                result=None,
                error=f"Không tìm thấy function: {name}",
                execution_time_ms=0,
            )
        
        # Tạo call record
        call_id = f"{name}_{int(start_time * 1000)}"
        call = FunctionCall(
            id=call_id,
            function_name=name,
            arguments=arguments,
            status=FunctionStatus.PENDING,
        )
        
        try:
            # Validate required parameters
            for param in func_def.parameters:
                if param.required and param.name not in arguments:
                    raise ValueError(f"Thiếu required parameter: {param.name}")
            
            # Áp dụng defaults cho missing optional parameters
            for param in func_def.parameters:
                if not param.required and param.name not in arguments:
                    if param.default is not None:
                        arguments[param.name] = param.default
            
            # Thực thi với timeout
            handler = func_def.handler
            
            if asyncio.iscoroutinefunction(handler):
                # Async function
                result = await asyncio.wait_for(
                    handler(**arguments),
                    timeout=func_def.timeout_seconds,
                )
            else:
                # Sync function - chạy trong executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: handler(**arguments)),
                    timeout=func_def.timeout_seconds,
                )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Cập nhật call record
            call.result = result
            call.status = FunctionStatus.SUCCESS
            call.execution_time_ms = execution_time_ms
            
            # Thêm vào history
            self._add_to_history(call)
            
            logger.info(f"Function {name} thực thi thành công trong {execution_time_ms}ms")
            
            return FunctionCallResult(
                success=True,
                result=result,
                execution_time_ms=execution_time_ms,
            )
            
        except asyncio.TimeoutError:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Function {name} timeout sau {func_def.timeout_seconds}s"
            
            call.status = FunctionStatus.TIMEOUT
            call.error_message = error_msg
            call.execution_time_ms = execution_time_ms
            self._add_to_history(call)
            
            logger.error(error_msg)
            
            return FunctionCallResult(
                success=False,
                result=None,
                error=error_msg,
                execution_time_ms=execution_time_ms,
            )
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Function {name} thất bại: {str(e)}"
            
            call.status = FunctionStatus.ERROR
            call.error_message = error_msg
            call.execution_time_ms = execution_time_ms
            self._add_to_history(call)
            
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            
            return FunctionCallResult(
                success=False,
                result=None,
                error=error_msg,
                execution_time_ms=execution_time_ms,
            )
    
    async def execute_sequential(
        self,
        calls: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        stop_on_error: bool = True,
    ) -> List[FunctionCallResult]:
        """
        Execute multiple function calls sequentially.
        
        Args:
            calls: List of {"name": str, "arguments": dict}
            context: Optional context for all calls
            stop_on_error: Stop execution if any call fails
            
        Returns:
            List of FunctionCallResult for each call
            

        """
        results = []
        
        for call in calls:
            name = call.get("name")
            arguments = call.get("arguments", {})
            
            result = await self.execute(name, arguments, context)
            results.append(result)
            
            if stop_on_error and not result.success:
                logger.warning(f"Thực thi tuần tự dừng do lỗi trong {name}")
                break
        
        return results
    
    def _add_to_history(self, call: FunctionCall) -> None:
        """Thêm call vào history, duy trì kích thước tối đa."""
        self._call_history.append(call)
        if len(self._call_history) > self._max_history:
            self._call_history = self._call_history[-self._max_history:]
    
    def get_call_history(
        self,
        function_name: Optional[str] = None,
        status: Optional[FunctionStatus] = None,
        limit: int = 50,
    ) -> List[FunctionCall]:
        """
        Get function call history.
        
        Args:
            function_name: Filter by function name
            status: Filter by status
            limit: Maximum number of records
            
        Returns:
            List of FunctionCall records
        """
        history = self._call_history.copy()
        
        if function_name:
            history = [c for c in history if c.function_name == function_name]
        if status:
            history = [c for c in history if c.status == status]
        
        return history[-limit:]
    
    def clear_history(self) -> None:
        """Xóa call history."""
        self._call_history.clear()


# Instance registry global
_global_registry: Optional[FunctionRegistry] = None


def get_function_registry() -> FunctionRegistry:
    """Lấy instance global của function registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = FunctionRegistry()
    return _global_registry


# ============================================================================
# Built-in Functions
# ============================================================================

def register_builtin_functions(registry: FunctionRegistry) -> None:
    """
    Đăng ký các built-in functions cho các thao tác phổ biến.
    
    Các functions này cung cấp khả năng cơ bản mà LLMs có thể sử dụng.
    """
    
    # Search documents function
    registry.register(
        name="search_documents",
        description="Tìm kiếm tài liệu trong knowledge base theo query. Trả về các document chunks liên quan với scores.",
        parameters=[
            FunctionParameter(
                name="query",
                type="string",
                description="Search query to find relevant documents",
                required=True,
            ),
            FunctionParameter(
                name="limit",
                type="number",
                description="Maximum number of results to return (default: 5)",
                required=False,
                default=5,
            ),
            FunctionParameter(
                name="tags",
                type="array",
                description="Filter by document tags",
                required=False,
                items={"type": "string"},
            ),
        ],
        handler=_builtin_search_documents,
        category="knowledge",
    )
    
    # Get document info function
    registry.register(
        name="get_document_info",
        description="Lấy thông tin chi tiết về một document cụ thể theo ID.",
        parameters=[
            FunctionParameter(
                name="document_id",
                type="string",
                description="UUID of the document to retrieve",
                required=True,
            ),
        ],
        handler=_builtin_get_document_info,
        category="knowledge",
    )
    
    # Calculate function
    registry.register(
        name="calculate",
        description="Thực hiện phép tính toán học. Hỗ trợ các phép toán cơ bản và hàm toán học phổ biến.",
        parameters=[
            FunctionParameter(
                name="expression",
                type="string",
                description="Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', 'sin(3.14)')",
                required=True,
            ),
        ],
        handler=_builtin_calculate,
        category="utility",
    )
    
    # Get current time function
    registry.register(
        name="get_current_time",
        description="Lấy ngày giờ hiện tại.",
        parameters=[
            FunctionParameter(
                name="timezone",
                type="string",
                description="Timezone name (e.g., 'Asia/Ho_Chi_Minh', 'UTC'). Default: UTC",
                required=False,
                default="UTC",
            ),
            FunctionParameter(
                name="format",
                type="string",
                description="Output format (e.g., '%Y-%m-%d %H:%M:%S'). Default: ISO format",
                required=False,
            ),
        ],
        handler=_builtin_get_current_time,
        category="utility",
    )
    
    # Format text function
    registry.register(
        name="format_text",
        description="Format text với các phép biến đổi khác nhau.",
        parameters=[
            FunctionParameter(
                name="text",
                type="string",
                description="Text to format",
                required=True,
            ),
            FunctionParameter(
                name="operation",
                type="string",
                description="Formatting operation to apply",
                required=True,
                enum=["uppercase", "lowercase", "title", "strip", "slug"],
            ),
        ],
        handler=_builtin_format_text,
        category="utility",
    )
    
    logger.info(f"Đã đăng ký {len(registry.list_functions())} built-in functions")


# Built-in function handlers

async def _builtin_search_documents(
    query: str,
    limit: int = 5,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Tìm kiếm documents trong knowledge base."""
    # Đây là placeholder - implementation thật sẽ dùng RetrieverService
    return {
        "query": query,
        "limit": limit,
        "tags": tags,
        "results": [],
        "message": "Search function placeholder - integrate with RetrieverService",
    }


async def _builtin_get_document_info(document_id: str) -> Dict[str, Any]:
    """Lấy thông tin document."""
    # Đây là placeholder - implementation thật sẽ dùng DocumentService
    return {
        "document_id": document_id,
        "message": "Document info placeholder - integrate with DocumentService",
    }


def _builtin_calculate(expression: str) -> Dict[str, Any]:
    """Đánh giá biểu thức toán học một cách an toàn."""
    import math
    import re
    
    # Các functions và constants được phép
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }
    
    # Validate expression (chỉ cho phép các ký tự an toàn)
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.\,a-z]+$', expression.lower()):
        return {
            "expression": expression,
            "error": "Ký tự không hợp lệ trong expression",
            "result": None,
        }
    
    try:
        # Đánh giá với namespace bị hạn chế
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {
            "expression": expression,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {
            "expression": expression,
            "error": str(e),
            "result": None,
        }


def _builtin_get_current_time(
    timezone: str = "UTC",
    format: Optional[str] = None,
) -> Dict[str, Any]:
    """Lấy thời gian hiện tại theo timezone chỉ định."""
    from datetime import datetime
    try:
        import pytz
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
    except ImportError:
        # Fallback nếu pytz không có
        now = datetime.utcnow()
        timezone = "UTC"
    except Exception:
        now = datetime.utcnow()
        timezone = "UTC"
    
    if format:
        formatted = now.strftime(format)
    else:
        formatted = now.isoformat()
    
    return {
        "timezone": timezone,
        "datetime": formatted,
        "timestamp": now.timestamp(),
    }


def _builtin_format_text(text: str, operation: str) -> Dict[str, Any]:
    """Format text với operation chỉ định."""
    import re
    
    operations = {
        "uppercase": lambda t: t.upper(),
        "lowercase": lambda t: t.lower(),
        "title": lambda t: t.title(),
        "strip": lambda t: t.strip(),
        "slug": lambda t: re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-'),
    }
    
    if operation not in operations:
        return {
            "original": text,
            "error": f"Operation không rõ: {operation}",
            "result": None,
        }
    
    result = operations[operation](text)
    return {
        "original": text,
        "operation": operation,
        "result": result,
    }
