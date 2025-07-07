# 这个文件现在为空，因为所有函数都已经移动到 config.py 中
# 保留这个文件是为了兼容性，避免破坏现有的导入

# 从 config.py 中重新导入所有函数，保持兼容性
from redstone_daily.plugins.mc_management.config import (
    load_server_instances, get_instance_id, check_mcsm_config,
    check_git_backup_config, get_server_backup_path, get_directory_size,
    format_size, parse_latest_player_list
)
from redstone_daily.plugins.utils import User


# 为了保持兼容性而保留的函数别名
def parse_player_list_from_log(log_text: str) -> list:
    """保留原函数作为备用"""
    return parse_latest_player_list(log_text)


async def check_server_permission_async(user: User, server_name: str, group) -> bool:
    """
    检查用户是否有指定服务器的特殊权限

    Args:
        user: 用户对象
        server_name: 服务器名称
        group: 群组对象（保留参数以保持接口一致性）

    Returns:
        bool: 是否有权限
    """
    try:
        return await user.has_special_permission(server_name)
    except Exception:
        return False
