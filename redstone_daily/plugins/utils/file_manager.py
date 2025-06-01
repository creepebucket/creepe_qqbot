"""
文件管理轮子
作者: AI Assistant
版本: 1.0.0
用于在Ubuntu服务器环境上管理文件操作
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class FileManagerError(Exception):
    """文件管理异常基类"""
    pass


class FileNotFoundError(FileManagerError):
    """文件未找到异常"""
    pass


class PermissionError(FileManagerError):
    """权限不足异常"""
    pass


class FileManager:
    """
    文件管理器
    
    提供安全的文件操作功能，包括：
    - JSON文件的读写
    - 文件和目录的创建、删除
    - 权限检查和安全验证
    """
    
    def __init__(self, base_path: str = "/opt/minecraft", allowed_extensions: List[str] = None):
        """
        初始化文件管理器
        
        Args:
            base_path: 基础路径，所有操作限制在此路径下
            allowed_extensions: 允许操作的文件扩展名列表
        """
        self.base_path = Path(base_path).resolve()
        self.allowed_extensions = allowed_extensions or ['.json', '.txt', '.log', '.yml', '.yaml']
        
        # 确保基础路径存在
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _validate_path(self, file_path: str) -> Path:
        """
        验证文件路径的安全性
        
        Args:
            file_path: 要验证的文件路径
            
        Returns:
            Path: 验证后的绝对路径
            
        Raises:
            PermissionError: 路径不安全时
        """
        path = Path(file_path)
        
        # 如果是相对路径，则相对于基础路径
        if not path.is_absolute():
            path = self.base_path / path
        
        # 解析路径，防止目录遍历攻击
        path = path.resolve()
        
        # 检查路径是否在允许的基础路径下
        try:
            path.relative_to(self.base_path)
        except ValueError:
            raise PermissionError(f'路径 {file_path} 超出了允许的操作范围')
        
        # 检查文件扩展名
        if self.allowed_extensions and path.suffix not in self.allowed_extensions:
            raise PermissionError(f'不允许操作 {path.suffix} 类型的文件')
        
        return path
    
    def read_json(self, file_path: str) -> Dict[str, Any]:
        """
        读取JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            Dict: JSON内容
            
        Raises:
            FileNotFoundError: 文件不存在
            FileManagerError: 文件格式错误
        """
        path = self._validate_path(file_path)
        
        try:
            if not path.exists():
                raise FileNotFoundError(f'文件 {file_path} 不存在')
            
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except json.JSONDecodeError as e:
            raise FileManagerError(f'JSON文件格式错误: {str(e)}')
        except Exception as e:
            raise FileManagerError(f'读取文件失败: {str(e)}')
    
    def write_json(self, file_path: str, data: Dict[str, Any], backup: bool = True) -> bool:
        """
        写入JSON文件
        
        Args:
            file_path: JSON文件路径
            data: 要写入的数据
            backup: 是否创建备份
            
        Returns:
            bool: 是否成功
            
        Raises:
            FileManagerError: 写入失败
        """
        path = self._validate_path(file_path)
        
        try:
            # 创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件存在且需要备份，创建备份
            if backup and path.exists():
                backup_path = path.with_suffix(f'{path.suffix}.backup')
                shutil.copy2(path, backup_path)
                logger.info(f'已创建备份文件: {backup_path}')
            
            # 写入JSON文件
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f'成功写入文件: {path}')
            return True
            
        except Exception as e:
            raise FileManagerError(f'写入文件失败: {str(e)}')
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 文件是否存在
        """
        try:
            path = self._validate_path(file_path)
            return path.exists()
        except Exception:
            return False
    
    def create_file(self, file_path: str, content: str = '') -> bool:
        """
        创建文件
        
        Args:
            file_path: 文件路径
            content: 初始内容
            
        Returns:
            bool: 是否成功
        """
        try:
            path = self._validate_path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f'成功创建文件: {path}')
            return True
            
        except Exception as e:
            logger.error(f'创建文件失败: {str(e)}')
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            path = self._validate_path(file_path)
            
            if path.exists():
                path.unlink()
                logger.info(f'成功删除文件: {path}')
                return True
            else:
                logger.warning(f'文件不存在: {path}')
                return False
                
        except Exception as e:
            logger.error(f'删除文件失败: {str(e)}')
            return False
    
    def list_files(self, directory: str = '', pattern: str = '*') -> List[str]:
        """
        列出目录中的文件
        
        Args:
            directory: 目录路径（相对于基础路径）
            pattern: 文件模式
            
        Returns:
            List[str]: 文件路径列表
        """
        try:
            if directory:
                path = self._validate_path(directory)
            else:
                path = self.base_path
            
            if not path.is_dir():
                return []
            
            files = []
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    # 返回相对于基础路径的路径
                    rel_path = file_path.relative_to(self.base_path)
                    files.append(str(rel_path))
            
            return sorted(files)
            
        except Exception as e:
            logger.error(f'列出文件失败: {str(e)}')
            return []


# 全局文件管理器实例
file_manager = FileManager()


def get_file_manager(base_path: str = None, allowed_extensions: List[str] = None) -> FileManager:
    """
    获取文件管理器实例
    
    Args:
        base_path: 自定义基础路径
        allowed_extensions: 自定义允许的扩展名
        
    Returns:
        FileManager: 文件管理器实例
    """
    if base_path or allowed_extensions:
        return FileManager(base_path or "/opt/minecraft", allowed_extensions)
    
    return file_manager 