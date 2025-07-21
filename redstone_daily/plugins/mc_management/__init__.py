from redstone_daily.plugins.base.helper import add_info

from .chat_sync import *
from .server_commands import *
from .server_monitor import *
from .server_operations import *
from .backup.command_handlers import *
from .backup.auto_backup import *



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
add_info('backup_diagnose', '诊断Git备份仓库问题\n快速检测模式或详细逐个检查文件找出损坏的文件\n需要对应服务器特殊权限\n用法: /backup_diagnose <服务器名> [--detailed]')
add_info('backup_fix', '修复Git备份仓库问题\n删除或备份损坏的文件\n需要对应服务器特殊权限\n用法: /backup_fix <服务器名> <delete/backup/skip>')
add_info('bind', '绑定此群消息到服务器')
