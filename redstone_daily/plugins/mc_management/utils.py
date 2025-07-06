import os

from redstone_daily.plugins.mc_management import MCSM_CONFIG, SERVER_INSTANCES, GIT_BACKUP_CONFIG
from redstone_daily.plugins.utils import get_env_str


def load_server_instances() -> dict:
    """从环境变量加载服务器实例配置"""

    default_instances = {}
    for i in MCSM_CONFIG['instances']:
        default_instances[i] = get_env_str(f'MCSM_{i.upper()}_ID')

    print(f'检测到mcsm实例: {default_instances}')
    # 过滤掉空值的实例
    return {name: instance_id for name, instance_id in default_instances.items() if instance_id}


def get_instance_id(server_name: str) -> str:
    """获取服务器实例ID"""
    if server_name.lower() not in SERVER_INSTANCES:
        available_servers = ', '.join(SERVER_INSTANCES.keys())
        raise ValueError(f'服务器名 "{server_name}" 不存在。可用服务器: {available_servers}')
    return SERVER_INSTANCES[server_name.lower()]


def check_mcsm_config() -> bool:
    """检查MCSM配置是否完整"""
    if not MCSM_CONFIG['apikey']:
        return False
    if not MCSM_CONFIG['daemon_id']:
        return False
    return True


def check_git_backup_config() -> bool:
    """检查Git备份配置是否完整"""
    if not GIT_BACKUP_CONFIG['enabled']:
        return False

    # 如果配置了具体的备份路径，检查路径配置
    if GIT_BACKUP_CONFIG['backup_paths']:
        return True

    # 如果没有配置具体路径，检查是否可以使用动态路径生成
    # 检查是否有服务器实例配置
    if SERVER_INSTANCES:
        return True

    # 都没有配置，返回False
    return False


def get_server_backup_path(server_name: str) -> str:
    """获取服务器备份路径"""
    import os

    # 从配置中获取服务器路径映射
    backup_paths = GIT_BACKUP_CONFIG['backup_paths']

    # 如果配置了具体的服务器路径
    for path_config in backup_paths:
        if isinstance(path_config, str) and ':' in path_config:
            name, path = path_config.split(':', 1)
            if name.strip().lower() == server_name.lower():
                # 规范化路径，处理Windows路径分隔符
                normalized_path = os.path.normpath(path.strip())
                return os.path.abspath(normalized_path)

    # 动态生成MCSM标准路径
    try:
        # 获取服务器实例ID
        instance_id = get_instance_id(server_name)

        # 获取MCSM基础路径配置
        mcsm_base_path = get_env_str('MCSM_BASE_PATH', '/opt/mcsmanager/daemon/data/InstanceData')
        backup_target = get_env_str('MCSM_BACKUP_TARGET', 'full')  # 'full' 或 'world'

        # 构建服务器目录路径
        server_dir = os.path.join(mcsm_base_path, instance_id)

        # 根据备份目标选择路径
        if backup_target.lower() == 'world':
            # 只备份存档目录
            backup_path = os.path.join(server_dir, 'World')
        else:
            # 备份整个服务器目录
            backup_path = server_dir

        # 规范化路径
        normalized_path = os.path.normpath(backup_path)
        return os.path.abspath(normalized_path)

    except ValueError:
        # 如果无法获取实例ID，回退到基础路径模式
        pass

    # 如果没有具体配置，使用默认路径
    if backup_paths and isinstance(backup_paths[0], str):
        base_path = backup_paths[0]
        # 构建服务器特定路径
        server_path = os.path.join(base_path, server_name)
        # 规范化路径
        normalized_path = os.path.normpath(server_path)
        return os.path.abspath(normalized_path)

    raise ValueError(f'未配置服务器 "{server_name}" 的备份路径，请配置 MCSM_BASE_PATH 或 GIT_BACKUP_PATHS')


def get_directory_size(path: str) -> int:
    """
    计算目录大小（字节）

    Args:
        path: 目录路径

    Returns:
        int: 目录大小（字节）
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    # 文件可能被删除或无法访问，跳过
                    continue
    except (OSError, PermissionError):
        pass
    return total_size


def format_size(size_bytes: int) -> str:
    """
    将字节数格式化为人类可读的大小

    Args:
        size_bytes: 字节数

    Returns:
        str: 格式化的大小字符串
    """
    if size_bytes == 0:
        return '0 B'

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f'{int(size_bytes)} {unit}'
            else:
                return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024.0

    return f'{size_bytes:.1f} PB'


def parse_latest_player_list(log_text: str) -> list:
    """解析最新的玩家列表 - 改进版本，确保获取最新的list命令结果"""
    import re

    lines = log_text.split('\n')

    # 从最后开始查找，寻找最近的list命令输出
    # 我们要找的是最新的时间戳后的list命令结果
    latest_list_result = None
    latest_timestamp = None

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()

        if not line:
            continue

        # 尝试提取时间戳（不同服务器可能有不同的日志格式）
        timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', line)
        if timestamp_match:
            current_timestamp = timestamp_match.group(1)
        else:
            current_timestamp = None

        # 检查是否是list命令的结果
        # 格式1: "There are X of a max of Y players online: ..."
        pattern1 = r"There are (\d+) of a max of \d+ players online:?\s*(.*)"
        match1 = re.search(pattern1, line)
        if match1:
            player_count = int(match1.group(1))
            players_str = match1.group(2).strip()

            if player_count == 0:
                latest_list_result = []
            elif players_str:
                latest_list_result = [name.strip() for name in players_str.split(',') if name.strip()]
            else:
                latest_list_result = []

            latest_timestamp = current_timestamp
            break

        # 格式2: "Online players (X): ..."
        pattern2 = r"Online players \((\d+)\):\s*(.*)"
        match2 = re.search(pattern2, line)
        if match2:
            player_count = int(match2.group(1))
            players_str = match2.group(2).strip()

            if player_count == 0:
                latest_list_result = []
            elif players_str:
                latest_list_result = [name.strip() for name in players_str.split(',') if name.strip()]
            else:
                latest_list_result = []

            latest_timestamp = current_timestamp
            break

        # 如果查找了太多行还没找到，就停止
        if len(lines) - i > 30:
            break

    return latest_list_result


def parse_player_list_from_log(log_text: str) -> list:
    """保留原函数作为备用"""
    return parse_latest_player_list(log_text)
