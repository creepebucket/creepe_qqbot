# 这个文件现在为空，因为所有函数都已经移动到 config.py 中
# 保留这个文件是为了兼容性，避免破坏现有的导入

# 从 config.py 中重新导入所有函数，保持兼容性
from redstone_daily.plugins.mc_management.config import (
    load_server_instances, get_instance_id, check_mcsm_config,
    check_git_backup_config, get_server_backup_path, get_directory_size,
    format_size, parse_latest_player_list
)

# 为了保持兼容性而保留的函数别名
def parse_player_list_from_log(log_text: str) -> list:
    """保留原函数作为备用"""
    return parse_latest_player_list(log_text)
