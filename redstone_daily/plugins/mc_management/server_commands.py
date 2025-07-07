from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event

from baimomcsm_api import applications
from redstone_daily.plugins.mc_management.config import check_mcsm_config, get_instance_id, MCSM_CONFIG
from redstone_daily.plugins.utils import check_command_enabled, get_context, check_server_permission_async

server_command = on_command('server_command')
whitelist = on_command('whitelist')

@whitelist.handle()
@check_command_enabled('whitelist')
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

        # 检查用户是否有该服务器的特殊权限
        if not await check_server_permission_async(user, server_name, group):
            await whitelist.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
            return

        try:
            instance_id = get_instance_id(server_name)
        except ValueError as e:
            await whitelist.send(f'❌ {str(e)}')
            return

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

        # 检查用户是否有该服务器的特殊权限
        if not await check_server_permission_async(user, server_name, group):
            await whitelist.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
            return

        try:
            instance_id = get_instance_id(server_name)
        except ValueError as e:
            await whitelist.send(f'❌ {str(e)}')
            return

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


@server_command.handle()
@check_command_enabled('server_command')
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

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await server_command.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

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
