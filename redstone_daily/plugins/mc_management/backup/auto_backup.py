import asyncio
import logging

import nonebot
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event

from redstone_daily.plugins.mc_management.config import check_mcsm_config, check_git_backup_config, SERVER_INSTANCES, get_instance_id
from redstone_daily.plugins.utils import check_command_enabled, get_context, User, check_server_permission_async

# 配置日志记录器
logger = logging.getLogger(__name__)
# 设置日志级别为DEBUG以便看到详细信息
logger.setLevel(logging.DEBUG)

async def backup_scheduler():
    """定时备份调度器"""
    from datetime import datetime, timedelta
    
    logger.info('🚀 自动备份调度器开始运行')

    while True:
        try:
            # 延迟导入避免循环导入
            from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
            
            # 尝试初始化备份管理器
            try:
                backup_manager = AutoBackupManager()
            except Exception as e:
                logger.error(f'❌ AutoBackupManager初始化失败: {str(e)}')
                await asyncio.sleep(60)
                continue
            
            # 检查所有启用的服务器
            try:
                enabled_servers = backup_manager.get_all_enabled_servers()
                # 使用 print 确保能看到这个信息
                print(f'检查到 {len(enabled_servers)} 个启用自动备份的服务器')
                logger.debug(f'检查到 {len(enabled_servers)} 个启用自动备份的服务器')
            except Exception as e:
                logger.error(f'❌ 获取启用服务器列表失败: {str(e)}')
                await asyncio.sleep(60)
                continue

            for server_config in enabled_servers:
                try:
                    server_name = server_config['server_name']
                    interval_minutes = server_config.get('interval_minutes', 360)
                    last_backup = server_config.get('last_backup')

                    # 检查是否需要备份
                    should_backup = False
                    if not last_backup:
                        should_backup = True  # 从未备份过
                        logger.debug(f'{server_name}: 从未备份过，准备执行首次备份')
                    else:
                        try:
                            last_backup_time = datetime.fromisoformat(last_backup)
                            next_backup_time = last_backup_time + timedelta(minutes=interval_minutes)
                            if datetime.now() >= next_backup_time:
                                should_backup = True
                                logger.debug(f'{server_name}: 到达备份时间，准备执行备份')
                            else:
                                logger.debug(f'{server_name}: 距离下次备份还有 {(next_backup_time - datetime.now()).total_seconds()//60:.0f} 分钟')
                        except Exception as e:
                            should_backup = True  # 解析时间失败，执行备份
                            logger.warning(f'{server_name}: 解析备份时间失败，执行备份: {str(e)}')

                    if should_backup:
                        print(f'🔄 开始执行 {server_name} 的定时备份')
                        logger.info(f'🔄 开始执行 {server_name} 的定时备份')
                        # 执行静默备份
                        success, message = await backup_manager.silent_backup(server_name)
                        log_level = logging.INFO if success else logging.ERROR
                        print(f'定时备份 {server_name}: {"✅ 成功" if success else "❌ 失败"} - {message}')
                        logger.log(log_level, f'定时备份 {server_name}: {"✅ 成功" if success else "❌ 失败"} - {message}')

                except Exception as e:
                    logger.error(f'❌ 处理服务器 {server_config.get("server_name", "未知")} 备份时出错: {str(e)}')

        except Exception as e:
            logger.error(f'❌ 定时备份调度器出错: {str(e)}', exc_info=True)

        # 每1分钟检查一次
        await asyncio.sleep(60)


# 全局调度器状态
_scheduler_running = False
_scheduler_task = None

@nonebot.get_driver().on_startup
async def start_backup_scheduler():
    """启动时自动启动备份调度器"""
    global _scheduler_running, _scheduler_task
    
    logger.info('🔧 准备启动自动备份调度器...')
    
    try:
        # 检查必要配置
        if not check_mcsm_config():
            logger.warning('⚠️ MCSM配置不完整，跳过启动自动备份调度器')
            return
            
        if not check_git_backup_config():
            logger.warning('⚠️ Git备份配置不完整，跳过启动自动备份调度器')
            return
        
        # 检查调度器是否已在运行
        if _scheduler_running and _scheduler_task and not _scheduler_task.done():
            logger.info('⚠️ 自动备份调度器已在运行')
            return
        
        # 启动调度器
        _scheduler_running = True
        _scheduler_task = asyncio.create_task(backup_scheduler())
        logger.info('✅ 自动备份调度器已成功启动')
        
        # 测试数据库连接
        try:
            from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
            backup_manager = AutoBackupManager()
            enabled_count = len(backup_manager.get_all_enabled_servers())
            logger.info(f'📊 当前有 {enabled_count} 个服务器启用了自动备份')
        except Exception as e:
            logger.error(f'❌ 数据库连接测试失败: {str(e)}')
            # 不阻止调度器启动，但记录错误
            
    except Exception as e:
        _scheduler_running = False
        _scheduler_task = None
        logger.error(f'❌ 启动自动备份调度器失败: {str(e)}', exc_info=True)


@nonebot.get_driver().on_shutdown
async def stop_backup_scheduler():
    """关闭时停止备份调度器"""
    global _scheduler_running, _scheduler_task
    
    logger.info('🛑 准备停止自动备份调度器...')
    
    try:
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass
            logger.info('🛑 自动备份调度器已停止')
        else:
            logger.info('🛑 自动备份调度器未在运行')
            
        _scheduler_running = False
        _scheduler_task = None
        
    except Exception as e:
        logger.error(f'❌ 停止自动备份调度器失败: {str(e)}', exc_info=True)


auto_backup = on_command('auto_backup')


@auto_backup.handle()
@check_command_enabled('auto_backup')
async def handle_auto_backup(event: Event):
    """管理定时自动备份"""
    global _scheduler_running, _scheduler_task
    user, args, group = get_context(event)

    if not check_mcsm_config():
        await auto_backup.send('❌ MCSM配置不完整，请检查环境变量配置')
        return

    if not check_git_backup_config():
        await auto_backup.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    if not args:
        await auto_backup.send('❌ 参数错误\n用法: /auto_backup <on/off/status/restart> [服务器名] [间隔分钟]')
        return

    action = args[0].lower()

    if action == 'status':
        # 显示所有服务器的自动备份状态
        message = '⚙️ 自动备份状态:\n\n'

        # 显示调度器状态
        scheduler_status = "❌ 已停止"
        if _scheduler_running:
            if _scheduler_task and not _scheduler_task.done():
                scheduler_status = "✅ 运行中"
            else:
                scheduler_status = "⚠️ 状态异常"
        
        message += f'📡 调度器: {scheduler_status}\n'
        
        # 添加调度器详细信息
        if _scheduler_task:
            if _scheduler_task.done():
                message += f'   任务状态: 已完成/异常\n'
                if _scheduler_task.exception():
                    message += f'   异常信息: {str(_scheduler_task.exception())[:50]}...\n'
            else:
                message += f'   任务状态: 正在运行\n'
        
        message += '\n'

        # 延迟导入避免循环导入
        try:
            from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
            backup_manager = AutoBackupManager()

            # 显示各服务器状态
            for server_name in SERVER_INSTANCES.keys():
                try:
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
                            from datetime import datetime
                            next_time = datetime.fromisoformat(config['next_backup'])
                            message += f'   下次备份: {next_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                        except:
                            pass

                    message += '\n'
                except Exception as e:
                    message += f'🖥️ {server_name}: ❌ 获取状态失败 ({str(e)})\n\n'

        except Exception as e:
            message += f'❌ 数据库连接失败: {str(e)}\n\n'

        message += '💡 使用说明:\n'
        message += '/auto_backup on <服务器名> [间隔分钟] - 启用自动备份\n'
        message += '/auto_backup off <服务器名> - 禁用自动备份\n'
        message += '/auto_backup status - 查看状态\n'
        message += '/auto_backup restart - 重启调度器\n\n'
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

    if action == 'restart':
        # 重启调度器（需要管理员权限）
        if await user.get_permission(group) < 3:
            await auto_backup.send('❌ 重启调度器需要3级权限')
            return
        
        # 停止现有调度器
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass
        
        # 重新启动
        await start_backup_scheduler()
        
        scheduler_status = "✅ 重启成功" if _scheduler_running else "❌ 重启失败"
        await auto_backup.send(f'🔄 调度器重启完成: {scheduler_status}')
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
        try:
            from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
            backup_manager = AutoBackupManager()

            # 保存配置
            config = backup_manager.get_server_config(server_name)
            config['enabled'] = True
            config['interval_minutes'] = interval_minutes
            backup_manager.set_server_config(server_name, config)

            # 确保调度器运行
            if not _scheduler_running or not _scheduler_task or _scheduler_task.done():
                await start_backup_scheduler()

            await auto_backup.send(f'✅ 已启用服务器 {server_name} 的自动备份\n⏰ 备份间隔: {interval_minutes}分钟\n💡 只在有玩家在线时备份，不会发送QQ消息')
            
        except Exception as e:
            await auto_backup.send(f'❌ 启用自动备份失败: {str(e)}')

    elif action == 'off':
        # 延迟导入避免循环导入
        try:
            from redstone_daily.plugins.mc_management.backup.utils import AutoBackupManager
            backup_manager = AutoBackupManager()

            # 禁用自动备份
            config = backup_manager.get_server_config(server_name)
            config['enabled'] = False
            backup_manager.set_server_config(server_name, config)

            await auto_backup.send(f'✅ 已禁用服务器 {server_name} 的自动备份')
            
        except Exception as e:
            await auto_backup.send(f'❌ 禁用自动备份失败: {str(e)}')

    else:
        await auto_backup.send('❌ 无效操作，请使用 on、off、status 或 restart')
