"""
环境变量读取轮子
作者: AI Assistant  
版本: 1.0.0
用于安全地读取环境变量和配置文件
"""

import os
from pathlib import Path
from typing import Union, Optional, Any
import logging

logger = logging.getLogger(__name__)


class EnvLoader:
    """
    环境变量加载器
    
    支持从 .env 文件和系统环境变量读取配置
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        初始化环境变量加载器
        
        Args:
            env_file: .env文件路径，默认为项目根目录的.env
        """
        self.env_file = env_file or self._find_env_file()
        self.env_vars = {}
        self._load_env_file()
    
    def _find_env_file(self) -> Optional[str]:
        """查找.env文件"""
        # 从当前目录开始向上查找
        current_dir = Path(__file__).parent
        for _ in range(5):  # 最多向上查找5级目录
            env_path = current_dir / '.env'
            if env_path.exists():
                return str(env_path)
            current_dir = current_dir.parent
        
        # 检查项目根目录
        project_root = Path(__file__).parent.parent.parent.parent
        env_path = project_root / '.env'
        if env_path.exists():
            return str(env_path)
        
        return None
    
    def _load_env_file(self):
        """加载.env文件"""
        if not self.env_file or not os.path.exists(self.env_file):
            logger.info('未找到.env文件，将仅使用系统环境变量')
            return
        
        try:
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析 KEY=VALUE 格式
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 去除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        self.env_vars[key] = value
                        logger.debug(f'从.env文件加载: {key}')
                    else:
                        logger.warning(f'.env文件第{line_num}行格式错误: {line}')
            
            logger.info(f'成功加载.env文件: {self.env_file}')
        
        except Exception as e:
            logger.error(f'加载.env文件失败: {str(e)}')
    
    def get(self, key: str, default: Any = None, type_func: callable = str) -> Any:
        """
        获取环境变量值
        
        Args:
            key: 环境变量名
            default: 默认值
            type_func: 类型转换函数
            
        Returns:
            环境变量值
        """
        # 优先从系统环境变量获取
        value = os.environ.get(key)
        
        # 如果系统环境变量没有，从.env文件获取
        if value is None:
            value = self.env_vars.get(key)
        
        # 如果都没有，使用默认值
        if value is None:
            return default
        
        # 类型转换
        try:
            if type_func == bool:
                return self._str_to_bool(value)
            elif type_func == list:
                return self._str_to_list(value)
            else:
                return type_func(value)
        except (ValueError, TypeError) as e:
            logger.warning(f'环境变量 {key} 类型转换失败: {str(e)}，使用默认值')
            return default
    
    def get_str(self, key: str, default: str = '') -> str:
        """获取字符串类型环境变量"""
        return self.get(key, default, str)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数类型环境变量"""
        return self.get(key, default, int)
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """获取浮点数类型环境变量"""
        return self.get(key, default, float)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔类型环境变量"""
        return self.get(key, default, bool)
    
    def get_list(self, key: str, default: list = None, separator: str = ',') -> list:
        """获取列表类型环境变量"""
        if default is None:
            default = []
        
        value = self.get_str(key)
        if not value:
            return default
        
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    def _str_to_bool(self, value: str) -> bool:
        """字符串转布尔值"""
        if isinstance(value, bool):
            return value
        
        value = value.lower().strip()
        return value in ('true', '1', 'yes', 'on', 'enabled')
    
    def _str_to_list(self, value: str, separator: str = ',') -> list:
        """字符串转列表"""
        if not value:
            return []
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    def reload(self):
        """重新加载配置"""
        self.env_vars = {}
        self._load_env_file()
    
    def set_env_file(self, env_file: str):
        """设置.env文件路径并重新加载"""
        self.env_file = env_file
        self.reload()
    
    def list_vars(self) -> dict:
        """列出所有已加载的环境变量（不包含值）"""
        all_vars = set(self.env_vars.keys())
        all_vars.update(os.environ.keys())
        return {var: '***' for var in sorted(all_vars)}


# 全局环境变量加载器实例
env_loader = EnvLoader()


def get_env(key: str, default: Any = None, type_func: callable = str) -> Any:
    """
    获取环境变量的便捷函数
    
    Args:
        key: 环境变量名
        default: 默认值
        type_func: 类型转换函数
        
    Returns:
        环境变量值
    """
    return env_loader.get(key, default, type_func)


def get_env_str(key: str, default: str = '') -> str:
    """获取字符串环境变量"""
    return env_loader.get_str(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数环境变量"""
    return env_loader.get_int(key, default)


def get_env_float(key: str, default: float = 0.0) -> float:
    """获取浮点数环境变量"""
    return env_loader.get_float(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """获取布尔环境变量"""
    return env_loader.get_bool(key, default)


def get_env_list(key: str, default: list = None, separator: str = ',') -> list:
    """获取列表环境变量"""
    return env_loader.get_list(key, default, separator) 