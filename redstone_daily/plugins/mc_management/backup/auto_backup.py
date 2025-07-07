import asyncio

import nonebot
from nonebot.adapters.onebot.v11 import Event

from redstone_daily.plugins import check_server_permission_async
from redstone_daily.plugins.mc_management import auto_backup
from redstone_daily.plugins.mc_management.config import check_mcsm_config, check_git_backup_config, SERVER_INSTANCES, get_instance_id
from redstone_daily.plugins.utils import check_command_enabled, get_context, User

async def backup_scheduler():
    """定时备份调度器"""
    import asyncio
    from datetime import datetime, timedelta
    import logging

    logging.info('自动备份调度器已启动')

    while True:
        try:
            # 延迟导入避免循环导入
            from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
            backup_manager = AutoBackupManager()
            
            # 检查所有启用的服务器
            enabled_servers = backup_manager.get_all_enabled_servers()

            for server_config in enabled_servers:
                server_name = server_config['server_name']
                interval_minutes = server_config.get('interval_minutes', 360)
                last_backup = server_config.get('last_backup')

                # 检查是否需要备份
                should_backup = False
                if not last_backup:
                    should_backup = True  # 从未备份过
                else:
                    try:
                        last_backup_time = datetime.fromisoformat(last_backup)
                        next_backup_time = last_backup_time + timedelta(minutes=interval_minutes)
                        if datetime.now() >= next_backup_time:
                            should_backup = True
                    except:
                        should_backup = True  # 解析时间失败，执行备份

                if should_backup:
                    # 执行静默备份
                    success, message = await backup_manager.silent_backup(server_name)
                    logging.info(f'定时备份 {server_name}: {"成功" if success else "失败"} - {message}')

        except Exception as e:
            logging.error(f'定时备份调度器出错: {str(e)}')

        # 每1分钟检查一次
        await asyncio.sleep(60)


# 全局调度器状态
_scheduler_running = False
_scheduler_task = None

@nonebot.get_driver().on_startup
async def start_backup_scheduler():
    """启动时自动启动备份调度器"""
    global _scheduler_running, _scheduler_task
    try:
        if not _scheduler_running:
            _scheduler_running = True
            _scheduler_task = asyncio.create_task(backup_scheduler())
            import logging
            logging.info('✅ 自动备份调度器已启动')
        else:
            import logging
            logging.info('⚠️ 自动备份调度器已在运行')
    except Exception as e:
        import logging
        logging.error(f'❌ 启动自动备份调度器失败: {str(e)}')


@nonebot.get_driver().on_shutdown
async def stop_backup_scheduler():
    """关闭时停止备份调度器"""
    global _scheduler_running, _scheduler_task
    try:
        if _scheduler_task:
            _scheduler_task.cancel()
            _scheduler_running = False
            import logging
            logging.info('🛑 自动备份调度器已停止')
    except Exception as e:
        import logging
        logging.error(f'❌ 停止自动备份调度器失败: {str(e)}')


@auto_backup.handle()
@check_command_enabled('auto_backup')
async def handle_auto_backup(event: Event):
    """管理定时自动备份"""
    user, args, group = get_context(event)

    if not check_mcsm_config():
        await auto_backup.send('❌ MCSM配置不完整，请检查环境变量配置')
        return

    if not check_git_backup_config():
        await auto_backup.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    if not args:
        await auto_backup.send('❌ 参数错误\n用法: /auto_backup <on/off/status> [服务器名] [间隔分钟]')
        return

    action = args[0].lower()

    if action == 'status':
        # 显示所有服务器的自动备份状态
        message = '⚙️ 自动备份状态:\n\n'

        # 显示调度器状态
        scheduler_status = "✅ 运行中" if _scheduler_running else "❌ 已停止"
        message += f'📡 调度器: {scheduler_status}\n\n'

        # 延迟导入避免循环导入
        from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
        backup_manager = AutoBackupManager()

        # 显示各服务器状态
        for server_name in SERVER_INSTANCES.keys():
            config = backup_manager.get_server_config(server_name)
            status = "✅ 启用" if config['enabled'] else "❌ 禁用"
            interval = config['interval_minutes']

            message += f'🖥️ {server_name}: {status} (间隔: {interval}分钟)\n'

            if config['last_backup']:
                try:
                    from datetime import datetime
                    last_time = datetime.fromisoformat(config['last_backup'])
                    message += f'   最后备份: {last_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                except:
                    message += f'   最后备份: 解析失败\n'
            else:
                message += f'   最后备份: 从未备份\n'

            if config['next_backup'] and config['enabled']:
                try:
                    next_time = datetime.fromisoformat(config['next_backup'])
                    message += f'   下次备份: {next_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                except:
                    pass

            message += '\n'

        message += '💡 使用说明:\n'
        message += '/auto_backup on <服务器名> [间隔分钟] - 启用自动备份\n'
        message += '/auto_backup off <服务器名> - 禁用自动备份\n'
        message += '/auto_backup status - 查看状态\n\n'
        message += '⏰ 常用间隔参考:\n'
        message += '• 5分钟 = 5 (最小值)\n'
        message += '• 15分钟 = 15\n'
        message += '• 30分钟 = 30\n'
        message += '• 1小时 = 60\n'
        message += '• 2小时 = 120\n'
        message += '• 6小时 = 360 (默认)\n'
        message += '• 12小时 = 720'

        await auto_backup.send(message)
        return

    if len(args) < 2:
        await auto_backup.send('❌ 参数错误\n用法: /auto_backup <on/off> <服务器名> [间隔分钟]')
        return

    server_name = args[1]

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await auto_backup.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    # 验证服务器名
    try:
        get_instance_id(server_name)
    except ValueError as e:
        await auto_backup.send(f'❌ {str(e)}')
        return

    if action == 'on':
        # 启用自动备份
        interval_minutes = 360  # 默认6小时=360分钟
        if len(args) > 2:
            try:
                interval_minutes = int(args[2])
                if interval_minutes < 5:
                    await auto_backup.send('❌ 备份间隔必须大于等于5分钟')
                    return
                if interval_minutes > 10080:  # 一周
                    await auto_backup.send('❌ 备份间隔不能超过10080分钟(一周)')
                    return
            except ValueError:
                await auto_backup.send('❌ 间隔分钟必须是数字')
                return

        # 延迟导入避免循环导入
        from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
        backup_manager = AutoBackupManager()

        # 保存配置
        config = backup_manager.get_server_config(server_name)
        config['enabled'] = True
        config['interval_minutes'] = interval_minutes
        backup_manager.set_server_config(server_name, config)

        # 确保调度器运行
        if not _scheduler_running:
            import asyncio
            global _scheduler_running, _scheduler_task
            _scheduler_running = True
            _scheduler_task = asyncio.create_task(backup_scheduler())

        await auto_backup.send(f'✅ 已启用服务器 {server_name} 的自动备份\n⏰ 备份间隔: {interval_minutes}分钟\n💡 只在有玩家在线时备份，不会发送QQ消息')

    elif action == 'off':
        # 延迟导入避免循环导入
        from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
        backup_manager = AutoBackupManager()

        # 禁用自动备份
        config = backup_manager.get_server_config(server_name)
        config['enabled'] = False
        backup_manager.set_server_config(server_name, config)

        await auto_backup.send(f'✅ 已禁用服务器 {server_name} 的自动备份')

    else:
        await auto_backup.send('❌ 无效操作，请使用 on、off 或 status')
