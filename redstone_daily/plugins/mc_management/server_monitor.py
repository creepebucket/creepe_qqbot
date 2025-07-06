from nonebot.adapters.onebot.v11 import Event

from baimomcsm_api import common, applications
from redstone_daily.plugins.mc_management import mcsm_status, check_mcsm_config, MCSM_CONFIG, server_list, \
    SERVER_INSTANCES, server_info, get_instance_id, server_status, players, player_list, parse_latest_player_list
from redstone_daily.plugins.utils import check_command_enabled, permission_required, get_context


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
