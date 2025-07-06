from nonebot.adapters.onebot.v11 import Event

from baimomcsm_api import applications
from redstone_daily.plugins.mc_management import server_start, check_mcsm_config, get_instance_id, MCSM_CONFIG, \
    server_stop, server_restart, server_kill
from redstone_daily.plugins.mc_management.backup.auto_backup import check_server_permission_async
from redstone_daily.plugins.utils import check_command_enabled, get_context


@server_start.handle()
@check_command_enabled('server_start')
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

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await server_start.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await server_start.send(f'❌ {str(e)}')
        return

    result = applications.start_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])

    if result:
        await server_start.send(f'✅ 服务器 {server_name} 启动指令已发送')
    else:
        await server_start.send(f'❌ 启动服务器失败')


@server_stop.handle()
@check_command_enabled('server_stop')
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

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await server_stop.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await server_stop.send(f'❌ {str(e)}')
        return

    result = applications.stop_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])

    if result:
        await server_stop.send(f'✅ 服务器 {server_name} 停止指令已发送')
    else:
        await server_stop.send(f'❌ 停止服务器失败')


@server_restart.handle()
@check_command_enabled('server_restart')
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

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await server_restart.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await server_restart.send(f'❌ {str(e)}')
        return

    result = applications.restart_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])

    if result:
        await server_restart.send(f'✅ 服务器 {server_name} 重启指令已发送')
    else:
        await server_restart.send(f'❌ 重启服务器失败')


@server_kill.handle()
@check_command_enabled('server_kill')
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

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await server_kill.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await server_kill.send(f'❌ {str(e)}')
        return

    result = applications.kill_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])

    if result:
        await server_kill.send(f'✅ 服务器 {server_name} 强制停止指令已发送')
    else:
        await server_kill.send(f'❌ 强制停止服务器失败')
