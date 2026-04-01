"""
Pipeline Configuration Loader
Load và quản lý cấu hình pipeline với hỗ trợ hot-reload.

Tính năng:
- Cấu hình dựa trên YAML
- Hot-reload không cần restart
- Validation cấu hình
- Thông báo thay đổi
- Giá trị mặc định và fallback

"""

import yaml
import os
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConfigChange:
    """Lưu lại thông tin thay đổi cấu hình"""
    timestamp: str
    changed_keys: List[str]
    old_values: Dict[str, Any]
    new_values: Dict[str, Any]
    changed_by: str = "system"


class ConfigValidationError(Exception):
    """Lỗi khi validation cấu hình thất bại"""
    pass


class PipelineConfigLoader:
    """
    Loader cấu hình có hỗ trợ hot-reload.
    
    Tính năng:
    - Load cấu hình từ file YAML
    - Validate schema và giá trị
    - Tự động reload khi file thay đổi
    - Thông báo cho listeners khi có thay đổi
    - Cung cấp giá trị mặc định khi cần
    """
    
    def __init__(
        self,
        config_path: str = "server/config/pipeline_config.yml",
        auto_reload: bool = True,
        reload_interval_seconds: int = 30
    ):
        """
        Khởi tạo configuration loader.
        
        Args:
            config_path: Đường dẫn đến file cấu hình
            auto_reload: Có tự động reload khi thay đổi không
            reload_interval_seconds: Khoảng thời gian check thay đổi
        """
        self.config_path = config_path
        self.auto_reload = auto_reload
        self.reload_interval_seconds = reload_interval_seconds
        
        self.config: Dict[str, Any] = {}
        self.last_modified: Optional[float] = None
        self.change_listeners: List[Callable] = []
        self.change_history: List[ConfigChange] = []
        
        # Load cấu hình ban đầu
        self.load_config()
        
        # Start thread auto-reload nếu bật
        if auto_reload:
            self._start_auto_reload()
        
        logger.info(f"ConfigLoader đã khởi tạo: path={config_path}, auto_reload={auto_reload}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load cấu hình từ file.
        
        Returns:
            Dictionary cấu hình
        
        Raises:
            ConfigValidationError: Nếu cấu hình không hợp lệ
        """
        try:
            # Check file có tồn tại không
            if not os.path.exists(self.config_path):
                logger.warning(f"Không tìm thấy file config: {self.config_path}, dùng mặc định")
                self.config = self._get_default_config()
                return self.config
            
            # Load YAML
            with open(self.config_path, 'r', encoding='utf-8') as f:
                new_config = yaml.safe_load(f)
            
            # Validate cấu hình
            self._validate_config(new_config)
            
            # Check có thay đổi không
            if self.config:
                changes = self._detect_changes(self.config, new_config)
                if changes:
                    self._record_change(changes)
                    self._notify_listeners(changes)
            
            # Cập nhật cấu hình
            old_config = self.config.copy()
            self.config = new_config
            self.last_modified = os.path.getmtime(self.config_path)
            
            logger.info("Đã load cấu hình thành công")
            return self.config
        
        except yaml.YAMLError as e:
            logger.error(f"Lỗi parse YAML: {e}")
            raise ConfigValidationError(f"YAML không hợp lệ: {e}")
        except Exception as e:
            logger.error(f"Lỗi khi load cấu hình: {e}")
            raise
    
    def reload_if_changed(self) -> bool:
        """
        Reload cấu hình nếu file đã thay đổi.
        
        Returns:
            True nếu đã reload cấu hình
        """
        try:
            if not os.path.exists(self.config_path):
                return False
            
            current_modified = os.path.getmtime(self.config_path)
            
            if self.last_modified is None or current_modified > self.last_modified:
                logger.info("File cấu hình đã thay đổi, đang reload...")
                self.load_config()
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Lỗi khi check thay đổi config: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Lấy giá trị cấu hình theo đường dẫn phân cách bằng dấu chấm.
        
        Args:
            key_path: Đường dẫn phân cách bằng dấu chấm (vd: "pre_llm.validation.enabled")
            default: Giá trị mặc định nếu không tìm thấy key
        
        Returns:
            Giá trị cấu hình hoặc default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any, save: bool = True) -> None:
        """
        Set giá trị cấu hình theo đường dẫn phân cách bằng dấu chấm.
        
        Args:
            key_path: Đường dẫn phân cách bằng dấu chấm
            value: Giá trị cần set
            save: Có lưu vào file không
        """
        keys = key_path.split('.')
        config = self.config
        
        # Navigate đến parent
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set giá trị
        old_value = config.get(keys[-1])
        config[keys[-1]] = value
        
        # Ghi lại thay đổi
        change = ConfigChange(
            timestamp=datetime.now().isoformat(),
            changed_keys=[key_path],
            old_values={key_path: old_value},
            new_values={key_path: value},
            changed_by="api"
        )
        self._record_change(change)
        self._notify_listeners(change)
        
        # Lưu vào file nếu yêu cầu
        if save:
            self.save_config()
    
    def save_config(self) -> None:
        """Lưu cấu hình hiện tại vào file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            
            self.last_modified = os.path.getmtime(self.config_path)
            logger.info("Đã lưu cấu hình thành công")
        
        except Exception as e:
            logger.error(f"Lỗi khi lưu cấu hình: {e}")
            raise
    
    def is_enabled(self, feature_path: str) -> bool:
        """
        Check xem một feature có được bật không.
        
        Args:
            feature_path: Đường dẫn đến feature (vd: "pre_llm.validation.enabled")
        
        Returns:
            True nếu bật, False nếu không
        """
        return self.get(feature_path, False) is True
    
    def add_change_listener(self, listener: Callable[[ConfigChange], None]) -> None:
        """
        Thêm listener để lắng nghe thay đổi cấu hình.
        
        Args:
            listener: Callback function nhận ConfigChange
        """
        self.change_listeners.append(listener)
    
    def remove_change_listener(self, listener: Callable) -> None:
        """Xóa một change listener."""
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)
    
    def get_change_history(self, limit: int = 10) -> List[ConfigChange]:
        """
        Lấy các thay đổi cấu hình gần đây.
        
        Args:
            limit: Số lượng thay đổi tối đa trả về
        
        Returns:
            List các thay đổi gần đây
        """
        return self.change_history[-limit:]
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate cấu trúc và giá trị cấu hình.
        
        Args:
            config: Cấu hình cần validate
        
        Raises:
            ConfigValidationError: Nếu validation thất bại
        """
        # Các key bắt buộc ở top-level
        required_keys = ['service', 'pre_llm', 'rag_patterns', 'post_llm', 'observability']
        
        for key in required_keys:
            if key not in config:
                raise ConfigValidationError(f"Thiếu key bắt buộc: {key}")
        
        # Validate thông tin service
        if 'name' not in config['service']:
            raise ConfigValidationError("Thiếu service.name")
        
        # Validate sampling rates (0-1)
        sampling_paths = [
            'observability.tracing.sampling_rate',
            'observability.logging.sampling_rate',
            'post_llm.evaluation.sample_rate'
        ]
        
        for path in sampling_paths:
            value = self._get_nested(config, path.split('.'))
            if value is not None and not (0 <= value <= 1):
                raise ConfigValidationError(f"{path} phải từ 0 đến 1")
        
        # Validate thresholds (0-1)
        threshold_paths = [
            'rag_patterns.adaptive.high_confidence_threshold',
            'rag_patterns.adaptive.low_confidence_threshold',
            'rag_patterns.corrective.relevance_threshold',
            'rag_patterns.corag.quality_alert_threshold'
        ]
        
        for path in threshold_paths:
            value = self._get_nested(config, path.split('.'))
            if value is not None and not (0 <= value <= 1):
                raise ConfigValidationError(f"{path} phải từ 0 đến 1")
        
        logger.debug("Validation cấu hình đã pass")
    
    def _detect_changes(self, old_config: Dict, new_config: Dict, prefix: str = "") -> Optional[ConfigChange]:
        """
        Phát hiện thay đổi giữa các cấu hình.
        
        Args:
            old_config: Cấu hình cũ
            new_config: Cấu hình mới
            prefix: Prefix key cho phát hiện nested
        
        Returns:
            ConfigChange nếu phát hiện thay đổi, None nếu không
        """
        changed_keys = []
        old_values = {}
        new_values = {}
        
        # Kiểm tra tất cả keys trong new config
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            
            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    # Kiểm tra đệ quy các nested dicts
                    nested_change = self._detect_changes(old_val, new_val, full_key)
                    if nested_change:
                        changed_keys.extend(nested_change.changed_keys)
                        old_values.update(nested_change.old_values)
                        new_values.update(nested_change.new_values)
                else:
                    changed_keys.append(full_key)
                    old_values[full_key] = old_val
                    new_values[full_key] = new_val
        
        if changed_keys:
            return ConfigChange(
                timestamp=datetime.now().isoformat(),
                changed_keys=changed_keys,
                old_values=old_values,
                new_values=new_values
            )
        
        return None
    
    def _record_change(self, change: ConfigChange) -> None:
        """Ghi lại thay đổi cấu hình vào history."""
        self.change_history.append(change)
        
        # Giữ lại 100 thay đổi gần nhất thôi
        if len(self.change_history) > 100:
            self.change_history = self.change_history[-100:]
        
        logger.info(f"Cấu hình đã thay đổi: {len(change.changed_keys)} keys")
    
    def _notify_listeners(self, change: ConfigChange) -> None:
        """Thông báo cho các listeners về thay đổi cấu hình."""
        for listener in self.change_listeners:
            try:
                listener(change)
            except Exception as e:
                logger.error(f"Lỗi khi notify listener: {e}")
    
    def _start_auto_reload(self) -> None:
        """Chạy thread background để auto-reload cấu hình."""
        def reload_loop() -> None:
            while self.auto_reload:
                try:
                    time.sleep(self.reload_interval_seconds)
                    self.reload_if_changed()
                except Exception as e:
                    logger.error(f"Lỗi trong auto-reload: {e}")
        
        thread = threading.Thread(target=reload_loop, daemon=True)
        thread.start()
        logger.info("Thread auto-reload đã chạy")
    
    def _get_nested(self, config: Dict, keys: List[str]) -> Any:
        """Lấy giá trị nested từ config theo list keys."""
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Lấy cấu hình mặc định khi không có file config."""
        return {
            'service': {
                'name': 'rag-anything',
                'version': '2.0.0',
                'environment': 'development'
            },
            'pre_llm': {
                'validation': {'enabled': True},
                'input_guardrails': {'enabled': False},
                'intent_detection': {'enabled': True},
                'text_processing': {'enabled': True},
                'memory': {'enabled': True}
            },
            'rag_patterns': {
                'default_pattern': 'standard',
                'adaptive': {'enabled': False},
                'corrective': {'enabled': False},
                'self_rag': {'enabled': False},
                'corag': {'enabled': False},
                'hybrid': {'enabled': True}
            },
            'post_llm': {
                'grounding': {'enabled': True},
                'output_guardrails': {'enabled': False},
                'policy': {'enabled': True},
                'formatting': {'enabled': True},
                'evaluation': {'enabled': False}
            },
            'observability': {
                'tracing': {'enabled': False},
                'logging': {'enabled': True, 'level': 'INFO'},
                'metrics': {'enabled': False}
            },
            'performance': {
                'token_budget': {'max_context_tokens': 4000},
                'timeouts': {'total_pipeline_timeout_ms': 60000},
                'caching': {'intent_cache_enabled': True}
            }
        }


# Instance global của config loader
_config_loader: Optional[PipelineConfigLoader] = None


def get_config_loader() -> PipelineConfigLoader:
    """Lấy hoặc tạo instance global của config loader."""
    global _config_loader
    if _config_loader is None:
        _config_loader = PipelineConfigLoader()
    return _config_loader


def set_config_loader(loader: PipelineConfigLoader) -> None:
    """Set instance global của config loader."""
    global _config_loader
    _config_loader = loader


# Ví dụ sử dụng
if __name__ == "__main__":
    # Khởi tạo loader
    loader = PipelineConfigLoader(
        config_path="server/config/pipeline_config.yml",
        auto_reload=True
    )
    
    # Lấy các giá trị cấu hình
    print(f"Service name: {loader.get('service.name')}")
    print(f"Validation enabled: {loader.is_enabled('pre_llm.validation.enabled')}")
    print(f"Default RAG pattern: {loader.get('rag_patterns.default_pattern')}")
    
    # Thêm listener để lắng nghe thay đổi
    def on_config_change(change: ConfigChange) -> None:
        print(f"\nCấu hình đã thay đổi lúc {change.timestamp}")
        print(f"Các keys thay đổi: {change.changed_keys}")
        for key in change.changed_keys:
            print(f"  {key}: {change.old_values.get(key)} -> {change.new_values.get(key)}")
    
    loader.add_change_listener(on_config_change)
    
    # Sửa cấu hình
    loader.set('rag_patterns.default_pattern', 'adaptive', save=False)
    
    # Xem lịch sử thay đổi
    print("\nCác thay đổi gần đây:")
    for change in loader.get_change_history(limit=5):
        print(f"  {change.timestamp}: {len(change.changed_keys)} keys đã thay đổi")
