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
from baimomcsm_api import common, applications

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
add_info('players', '查询所有服务器概览信息\n无需权限\n用法: /players')
add_info('player_list', '查询指定服务器在线玩家名单\n无需权限\n用法: /player_list [服务器名]')
add_info('server_command', '给服务器发送指令\n需要mc_server特殊权限\n用法: /server_command <服务器名> <指令>')

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
        'slimefun': get_env_str('MCSM_SLIMEFUN_ID'),
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
    
    result = common.get_overview(MCSM_CONFIG['url'], MCSM_CONFIG['apikey'])
    
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
        try:
            # 获取服务器状态 - get_status 直接返回状态值
            status = applications.get_status(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
            
            status_emoji = "🟢" if status == 3 else "🔴"
            status_text = "运行中" if status == 3 else "已停止"
            message += f"{status_emoji} {server_name}: {status_text}\n"
        except Exception as e:
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
    
    result = applications.get_info(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
    
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
    
    result = applications.get_info(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
    
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
    
    result = applications.start_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
    
    if result:
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
    
    result = applications.stop_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
    
    if result:
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
    
    result = applications.restart_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
    
    if result:
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
    
    result = applications.kill_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
    
    if result:
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
        
        result = applications.send_command(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'], 'whitelist list')
        
        if result:
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
        result = applications.send_command(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'], command)
        
        if result:
            action_text = '添加到' if action == 'add' else '从'
            action_text2 = '' if action == 'add' else '移除'
            await whitelist.send(f'✅ 已将玩家 {player_name} {action_text}服务器 {server_name} 的白名单{action_text2}')
        else:
            await whitelist.send(f'❌ 发送指令失败')
    
    else:
        await whitelist.send('❌ 无效操作，请使用 add、remove 或 list')

@players.handle()
@check_command_enabled('players')
async def handle_players(event: Event):
    """查询所有服务器概览信息"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await players.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    message = "📊 服务器概览信息:\n"
    total_players = 0
    
    for server_name, instance_id in SERVER_INSTANCES.items():
        try:
            # 获取服务器详细信息
            result = applications.get_info(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
            
            if result.get('status') == 200:
                data = result['data']
                status = data['status']
                
                # 服务器状态
                status_map = {0: "停止", 1: "停止中", 2: "启动中", 3: "运行中"}
                status_text = status_map.get(status, "未知")
                status_emoji = "🟢" if status == 3 else "🔴"
                
                message += f"\n{status_emoji} {server_name} ({status_text})\n"
                
                # 只显示玩家数量概览，不显示具体玩家名
                if status == 3:  # 运行中
                    if 'info' in data:
                        info = data['info']
                        current_players = info.get('currentPlayers', -1)
                        max_players = info.get('maxPlayers', -1)
                        version = info.get('version', 'N/A')
                        
                        if current_players >= 0:
                            message += f"  玩家: {current_players}/{max_players}\n"
                            total_players += current_players
                            if version and version != 'N/A':
                                message += f"  版本: {version}\n"
                        else:
                            message += f"  玩家信息不可用\n"
                    else:
                        message += f"  无玩家信息\n"
                else:
                    message += f"  服务器未运行\n"
            else:
                message += f"\n❓ {server_name}: 无法获取信息\n"
                
        except Exception as e:
            message += f"\n❓ {server_name}: 查询失败\n"
    
    message += f"\n🎮 总在线玩家数: {total_players}"
    message += f"\n\n💡 查看具体玩家名单请使用: /player_list <服务器名>"
    await players.send(message)

@player_list.handle()
@check_command_enabled('player_list')
async def handle_player_list(event: Event):
    """查询指定服务器在线玩家名单"""
    user, args, group = get_context(event)

    await player_list.send('正在查询, 请等候3-10秒......')

    if not check_mcsm_config():
        await player_list.send('❌ MCSM配置不完整，请检查环境变量配置')
        return

    # 如果没有指定服务器，默认使用第一个服务器或提示用户选择
    if not args:
        if len(SERVER_INSTANCES) == 1:
            server_name = list(SERVER_INSTANCES.keys())[0]
        else:
            available_servers = ', '.join(SERVER_INSTANCES.keys())
            await player_list.send(f'❌ 请指定服务器名\n用法: /player_list <服务器名>\n可用服务器: {available_servers}')
            return
    else:
        server_name = args[0]

    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await player_list.send(f'❌ {str(e)}')
        return

    try:
        # 获取服务器状态
        result = applications.get_info(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])

        if result.get('status') == 200:
            data = result['data']
            status = data['status']

            if status != 3:
                status_map = {0: "停止", 1: "停止中", 2: "启动中", 3: "运行中"}
                status_text = status_map.get(status, "未知")
                await player_list.send(f'❌ 服务器 {server_name} 当前状态: {status_text}，无法查询玩家列表')
                return

            # 多次尝试获取最新的玩家列表
            player_names = []
            max_attempts = 3
            
            for attempt in range(max_attempts):
                # 发送list指令
                applications.send_command(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'], 'list')
                
                # 等待指令执行
                import time
                time.sleep(2 + attempt)  # 每次尝试等待更久一点
                
                # 获取日志
                log_result = applications.get_outputlog(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
                
                if log_result:
                    # 解析最新的玩家列表
                    parsed_players = parse_latest_player_list(log_result)
                    
                    # 如果成功解析到玩家列表（包括空列表），就使用这个结果
                    if parsed_players is not None:
                        player_names = parsed_players
                        break
                
                # 如果不是最后一次尝试，短暂等待后重试
                if attempt < max_attempts - 1:
                    time.sleep(1)

            # 显示结果
            if player_names is not None:  # 成功获取到列表（可能为空）
                if player_names:
                    message = f"🎮 服务器 {server_name} 在线玩家列表:\n\n"
                    for i, player in enumerate(player_names, 1):
                        message += f"{i}. {player}\n"
                    message += f"\n📊 总计: {len(player_names)} 位玩家在线"
                else:
                    message = f"🎮 服务器 {server_name}:\n当前没有玩家在线"
            else:
                # 如果无法解析玩家名，显示基础信息
                if 'info' in data:
                    info = data['info']
                    current_players = info.get('currentPlayers', -1)
                    max_players = info.get('maxPlayers', -1)
                    if current_players >= 0:
                        message = f"🎮 服务器 {server_name}:\n"
                        message += f"在线玩家: {current_players}/{max_players}\n"
                        message += f"具体玩家名无法获取，请稍后重试或查看服务器控制台"
                    else:
                        message = f"🎮 服务器 {server_name}:\n无法获取玩家信息"
                else:
                    message = f"🎮 服务器 {server_name}:\n无法获取玩家信息"

            await player_list.send(message)
        else:
            await player_list.send(f'❌ 无法连接到服务器 {server_name}')

    except Exception as e:
        await player_list.send(f'❌ 查询服务器 {server_name} 玩家列表时出错: {str(e)}')

def parse_latest_player_list(log_text: str) -> list:
    """解析最新的玩家列表 - 改进版本，确保获取最新的list命令结果"""
    import re
    from datetime import datetime
    
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

@server_command.handle()
@check_command_enabled('server_command')
@permission_required('mc_server')
async def handle_server_command(event: Event):
    """给服务器发送指令"""
    user, args, group = get_context(event)
    
    if not check_mcsm_config():
        await server_command.send('❌ MCSM配置不完整，请检查环境变量配置')
        return
    
    if not args:
        await server_command.send('❌ 请提供服务器名和指令\n用法: /server_command <服务器名> <指令>')
        return
    
    server_name = args[0]
    
    # 将除服务器名外的所有参数组合成完整指令
    if len(args) < 2:
        await server_command.send('❌ 请提供要发送的指令\n用法: /server_command <服务器名> <指令>')
        return
    
    command = ' '.join(args[1:])  # 将服务器名后的所有参数组合成指令
    
    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await server_command.send(f'❌ {str(e)}')
        return
    
    try:
        result = applications.send_command(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'], command)
        
        if result:
            await server_command.send(f'✅ 已发送指令到服务器 {server_name}\n指令: {command}')
        else:
            await server_command.send(f'❌ 发送指令失败')
    except Exception as e:
        await server_command.send(f'❌ 发送指令时出错: {str(e)}') 