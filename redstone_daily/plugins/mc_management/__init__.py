from nonebot import on_command
from redstone_daily.plugins.base.helper import add_info
from redstone_daily.plugins.mc_management.config import (
    MCSM_CONFIG, GIT_BACKUP_CONFIG, SERVER_INSTANCES, 
    get_instance_id, check_mcsm_config, check_git_backup_config, 
    get_server_backup_path, get_directory_size, format_size, parse_latest_player_list
)
from redstone_daily.plugins.utils import (
    get_env_str, get_env_list
)

# 帮助信息
add_info('mcsm_status', 'MCSM面板状态查看\n需要mc_server特殊权限\n用法: /mcsm_status')
add_info('server_list', '服务器实例列表\n无需权限\n用法: /server_list')
add_info('server_info', '查看服务器详情\n无需权限\n用法: /server_info <服务器名>')
add_info('server_status', '查看服务器状态\n无需权限\n用法: /server_status <服务器名>')
add_info('server_start', '启动服务器\n需要对应服务器特殊权限\n用法: /server_start <服务器名>')
add_info('server_stop', '停止服务器\n需要对应服务器特殊权限\n用法: /server_stop <服务器名>')
add_info('server_restart', '重启服务器\n需要对应服务器特殊权限\n用法: /server_restart <服务器名>')
add_info('server_kill', '强制停止服务器\n需要对应服务器特殊权限\n用法: /server_kill <服务器名>')
add_info('whitelist', 'MC白名单管理\n需要对应服务器特殊权限\n用法: /whitelist <add/remove/list> [玩家名] [服务器名]')
add_info('players', '查询所有服务器概览信息\n无需权限\n用法: /players')
add_info('player_list', '查询指定服务器在线玩家名单\n无需权限\n用法: /player_list [服务器名]')
add_info('server_command', '给服务器发送指令\n需要对应服务器特殊权限\n用法: /server_command <服务器名> <指令>')
add_info('server_backup', 'Git备份服务器存档\n需要对应服务器特殊权限\n用法: /server_backup <服务器名> [备份描述]')
add_info('backup_info', '查看备份配置信息\n无需权限\n用法: /backup_info [服务器名]')
add_info('backup_list', '查看备份历史列表\n无需权限\n用法: /backup_list <服务器名>')
add_info('backup_rollback', '回滚到指定备份版本\n需要对应服务器特殊权限\n用法: /backup_rollback <服务器名> <版本号>')
add_info('auto_backup', '管理定时自动备份\n需要对应服务器特殊权限\n用法: /auto_backup <on/off/status> [服务器名] [间隔分钟]')
add_info('backup_analyze', '分析备份仓库大小和增长趋势\n无需权限\n用法: /backup_analyze [服务器名]')
add_info('backup_clean', '手动清理备份仓库Git历史\n需要对应服务器特殊权限\n用法: /backup_clean <服务器名>')

# 命令处理器
mcsm_status = on_command('mcsm_status')
server_list = on_command('server_list')
server_info = on_command('server_info')
server_status = on_command('server_status')
server_start = on_command('server_start')
server_stop = on_command('server_stop')
server_restart = on_command('server_restart')
server_kill = on_command('server_kill')
whitelist = on_command('whitelist')
players = on_command('players')
player_list = on_command('player_list')
server_command = on_command('server_command')
server_backup = on_command('server_backup')
backup_info = on_command('backup_info')
backup_list = on_command('backup_list')
backup_rollback = on_command('backup_rollback')
auto_backup = on_command('auto_backup')
backup_analyze = on_command('backup_analyze')
backup_clean = on_command('backup_clean')
# 定时备份调度器和自动备份管理器在 auto_backup.py 中处理

add_info('bind', '绑定此群消息到服务器')

# 服务器到QQ的反向互通 - 简单的定时检查

# 存储每个服务器的最后日志位置
server_log_positions = {}

# 启动服务器消息检查任务
