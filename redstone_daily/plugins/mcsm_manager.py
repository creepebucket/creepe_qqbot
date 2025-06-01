"""
MCSM 服务器管理插件
作者: AI Assistant
版本: 1.0.0
基于 BaimoMCSManager API
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import (
    get_context, permission_required, check_command_enabled,
    get_env_str, get_env_list
)
from baimomcsm_api import *

# 帮助信息
add_info('mcsm_status', 'MCSM面板状态查看\n需要mc_server特殊权限\n用法: /mcsm_status')
add_info('server_list', '服务器实例列表\n需要mc_server特殊权限\n用法: /server_list')
add_info('server_info', '查看服务器详情\n需要mc_server特殊权限\n用法: /server_info <服务器名>')
add_info('server_status', '查看服务器状态\n需要mc_server特殊权限\n用法: /server_status <服务器名>')
add_info('server_start', '启动服务器\n需要mc_server特殊权限\n用法: /server_start <服务器名>')
add_info('server_stop', '停止服务器\n需要mc_server特殊权限\n用法: /server_stop <服务器名>')
add_info('server_restart', '重启服务器\n需要mc_server特殊权限\n用法: /server_restart <服务器名>')
add_info('server_kill', '强制停止服务器\n需要mc_server特殊权限\n用法: /server_kill <服务器名>')
add_info('whitelist', 'MC白名单管理\n需要mc_server特殊权限\n用法: /whitelist <add/remove/list> [玩家名] [服务器名]')

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

# MCSM 配置 - 从环境变量读取
MCSM_CONFIG = {
    'url': get_env_str('MCSM_URL', 'http://localhost:23333'),
    'apikey': get_env_str('MCSM_APIKEY', ''),
    'daemon_id': get_env_str('MCSM_DAEMON_ID', ''),
}

# 服务器实例映射 - 从环境变量读取
def load_server_instances() -> dict:
    """从环境变量加载服务器实例配置"""
    # 默认配置
    default_instances = {
        'slimefun': get_env_str('MCSM_SLIMEFUN_ID', 'f645c80e421f4fea8997ba6eb53644b7'),
        'survival': get_env_str('MCSM_SURVIVAL_ID', ''),
        'creative': get_env_str('MCSM_CREATIVE_ID', ''),
        'skyblock': get_env_str('MCSM_SKYBLOCK_ID', ''),
        'main': get_env_str('MCSM_MAIN_ID', ''),
        'test': get_env_str('MCSM_TEST_ID', ''),
    }
    
    # 过滤掉空值的实例
    return {name: instance_id for name, instance_id in default_instances.items() if instance_id}

SERVER_INSTANCES = load_server_instances()

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

@mcsm_status.handle()
@check_command_enabled('mcsm_status')
@permission_required('mc_server')
async def handle_mcsm_status(event: Event):
    """查看MCSM面板状态"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await mcsm_status.send('❌ MCSM配置不完整，请检查环境变量 MCSM_APIKEY 和 MCSM_DAEMON_ID')
        return
    
    result = get_overview(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'])
    
    if result.get('status') == 200:
        data = result['data']
        system = data['system']
        remote_count = data['remoteCount']
        
        message = f"📊 MCSM面板状态\n"
        message += f"版本: {data['version']}\n"
        message += f"系统: {system['platform']} {system['release']}\n"
        message += f"CPU使用率: {system['cpu']:.1f}%\n"
        message += f"内存使用: {(system['totalmem'] - system['freemem']) / 1024**3:.1f}GB / {system['totalmem'] / 1024**3:.1f}GB\n"
        message += f"守护进程: {remote_count['available']}/{remote_count['total']} 在线"
        
        await mcsm_status.send(message)
    else:
        await mcsm_status.send(f'❌ 获取面板状态失败，状态码: {result.get("status")}')

@server_list.handle()
@check_command_enabled('server_list')
@permission_required('mc_server')
async def handle_server_list(event: Event):
    """查看服务器列表"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_list.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    message = "🖥️ 可用服务器列表:\n"
    for server_name, instance_id in SERVER_INSTANCES.items():
        # 获取服务器状态
        status_result = get_status(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id)
        
        if status_result.get('status') == 200:
            status = status_result['data']['status']
            status_emoji = "🟢" if status == 3 else "🔴"
            status_text = "运行中" if status == 3 else "已停止"
            message += f"{status_emoji} {server_name}: {status_text}\n"
        else:
            message += f"❓ {server_name}: 状态未知\n"
    
    await server_list.send(message)

@server_info.handle()
@check_command_enabled('server_info')
@permission_required('mc_server')
async def handle_server_info(event: Event):
    """查看服务器详情"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_info.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_info.send('❌ 参数错误\n用法: /server_info <服务器名>')
        return
    
    server_name = args[0]
    instance_id = get_instance_id(server_name)
    
    result = get_info(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id)
    
    if result.get('status') == 200:
        data = result['data']
        config = data['config']
        
        message = f"ℹ️ 服务器 {server_name} 详情\n"
        message += f"名称: {config.get('nickname', 'N/A')}\n"
        message += f"类型: {config.get('type', 'N/A')}\n"
        message += f"启动命令: {config.get('startCommand', 'N/A')}\n"
        message += f"工作目录: {config.get('cwd', 'N/A')}\n"
        message += f"最大内存: {config.get('maxSpace', 'N/A')}MB\n"
        message += f"文件编码: {config.get('ie', 'N/A')}\n"
        message += f"输出编码: {config.get('oe', 'N/A')}"
        
        await server_info.send(message)
    else:
        await server_info.send(f'❌ 获取服务器信息失败')

@server_status.handle()
@check_command_enabled('server_status')
@permission_required('mc_server')
async def handle_server_status(event: Event):
    """查看服务器状态"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_status.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_status.send('❌ 参数错误\n用法: /server_status <服务器名>')
        return
    
    server_name = args[0]
    instance_id = get_instance_id(server_name)
    
    result = get_status(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id)
    
    if result.get('status') == 200:
        data = result['data']
        
        status_map = {0: "停止", 1: "停止中", 2: "启动中", 3: "运行中"}
        status_text = status_map.get(data['status'], "未知")
        
        message = f"📈 服务器 {server_name} 状态\n"
        message += f"状态: {status_text}\n"
        
        if 'info' in data:
            info = data['info']
            if 'maxPlayers' in info:
                message += f"在线玩家: {info.get('currentPlayers', 0)}/{info.get('maxPlayers', 0)}\n"
            if 'version' in info:
                message += f"版本: {info['version']}\n"
        
        await server_status.send(message)
    else:
        await server_status.send(f'❌ 获取服务器状态失败')

@server_start.handle()
@check_command_enabled('server_start')
@permission_required('mc_server')
async def handle_server_start(event: Event):
    """启动服务器"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_start.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_start.send('❌ 参数错误\n用法: /server_start <服务器名>')
        return
    
    server_name = args[0]
    instance_id = get_instance_id(server_name)
    
    result = send_command(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id, 'start')
    
    if result.get('status') == 200:
        await server_start.send(f'✅ 服务器 {server_name} 启动指令已发送')
    else:
        await server_start.send(f'❌ 启动服务器失败')

@server_stop.handle()
@check_command_enabled('server_stop')
@permission_required('mc_server')
async def handle_server_stop(event: Event):
    """停止服务器"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_stop.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_stop.send('❌ 参数错误\n用法: /server_stop <服务器名>')
        return
    
    server_name = args[0]
    instance_id = get_instance_id(server_name)
    
    result = send_command(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id, 'stop')
    
    if result.get('status') == 200:
        await server_stop.send(f'✅ 服务器 {server_name} 停止指令已发送')
    else:
        await server_stop.send(f'❌ 停止服务器失败')

@server_restart.handle()
@check_command_enabled('server_restart')
@permission_required('mc_server')
async def handle_server_restart(event: Event):
    """重启服务器"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_restart.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_restart.send('❌ 参数错误\n用法: /server_restart <服务器名>')
        return
    
    server_name = args[0]
    instance_id = get_instance_id(server_name)
    
    result = send_command(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id, 'restart')
    
    if result.get('status') == 200:
        await server_restart.send(f'✅ 服务器 {server_name} 重启指令已发送')
    else:
        await server_restart.send(f'❌ 重启服务器失败')

@server_kill.handle()
@check_command_enabled('server_kill')
@permission_required('mc_server')
async def handle_server_kill(event: Event):
    """强制停止服务器"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_kill.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_kill.send('❌ 参数错误\n用法: /server_kill <服务器名>')
        return
    
    server_name = args[0]
    instance_id = get_instance_id(server_name)
    
    result = send_command(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id, 'kill')
    
    if result.get('status') == 200:
        await server_kill.send(f'✅ 服务器 {server_name} 强制停止指令已发送')
    else:
        await server_kill.send(f'❌ 强制停止服务器失败')

@whitelist.handle()
@check_command_enabled('whitelist')
@permission_required('mc_server')
async def handle_whitelist(event: Event):
    """MC白名单管理"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await whitelist.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await whitelist.send('❌ 参数错误\n用法: /whitelist <add/remove/list> [玩家名] [服务器名]')
        return
    
    action = args[0].lower()
    
    if action == 'list':
        # 列出白名单
        server_name = args[1] if len(args) > 1 else 'slimefun'
        instance_id = get_instance_id(server_name)
        
        result = send_command(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id, 'whitelist list')
        
        if result.get('status') == 200:
            await whitelist.send(f'✅ 已发送白名单查询指令到服务器 {server_name}')
        else:
            await whitelist.send(f'❌ 发送指令失败')
    
    elif action in ['add', 'remove']:
        if len(args) < 2:
            await whitelist.send(f'❌ 参数错误\n用法: /whitelist {action} <玩家名> [服务器名]')
            return
        
        player_name = args[1]
        server_name = args[2] if len(args) > 2 else 'slimefun'
        instance_id = get_instance_id(server_name)
        
        command = f'whitelist {action} {player_name}'
        result = send_command(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'], MCSM_CONFIG['daemon_id'], instance_id, command)
        
        if result.get('status') == 200:
            action_text = '添加到' if action == 'add' else '从'
            action_text2 = '' if action == 'add' else '移除'
            await whitelist.send(f'✅ 已将玩家 {player_name} {action_text}服务器 {server_name} 的白名单{action_text2}')
        else:
            await whitelist.send(f'❌ 发送指令失败')
    
    else:
        await whitelist.send('❌ 无效操作，请使用 add、remove 或 list') 