import os

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event

from redstone_daily.plugins.mc_management.config import (
    check_mcsm_config, check_git_backup_config, SERVER_INSTANCES, 
    get_instance_id, get_server_backup_path, get_directory_size, format_size, GIT_BACKUP_CONFIG
)
from redstone_daily.plugins.mc_management.backup.utils import execute_git_backup, execute_backup_rollback, \
    analyze_single_server, clean_git_repository
from redstone_daily.plugins.utils import check_command_enabled, get_context, check_server_permission_async

server_backup = on_command('server_backup')


@server_backup.handle()
@check_command_enabled('server_backup')
async def handle_server_backup(event: Event):
    """Git备份服务器存档"""
    user, args, group = get_context(event)

    # 检查MCSM配置
    if not check_mcsm_config():
        await server_backup.send('❌ MCSM配置不完整，请检查环境变量配置')
        return

    # 检查Git备份配置
    if not check_git_backup_config():
        await server_backup.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    # 参数验证
    if not args:
        available_servers = ', '.join(SERVER_INSTANCES.keys())
        await server_backup.send(f'❌ 请指定服务器名\n用法: /server_backup <服务器名> [备份描述]\n可用服务器: {available_servers}')
        return

    server_name = args[0]

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await server_backup.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    backup_description = ' '.join(args[1:]) if len(args) > 1 else ''

    # 验证服务器名是否存在
    try:
        get_instance_id(server_name)
    except ValueError as e:
        await server_backup.send(f'❌ {str(e)}')
        return

    # 验证备份路径配置
    try:
        get_server_backup_path(server_name)
    except ValueError as e:
        await server_backup.send(f'❌ {str(e)}')
        return

    # 发送开始备份的消息
    await server_backup.send(f'🔄 开始备份服务器 {server_name}...')

    try:
        # 执行备份
        success, message = await execute_git_backup(server_name, backup_description)

        if success:
            await server_backup.send(f'✅ {message}')
        else:
            await server_backup.send(f'❌ 备份失败: {message}')

    except Exception as e:
        import logging
        logging.error(f'备份服务器 {server_name} 时出错: {str(e)}', exc_info=True)
        await server_backup.send(f'❌ 备份过程中发生未知错误，请查看日志或联系管理员')


backup_info = on_command('backup_info')


@backup_info.handle()
@check_command_enabled('backup_info')
async def handle_backup_info(event: Event):
    """查看备份配置信息"""
    user, args, group = get_context(event)

    # 检查Git备份配置
    if not check_git_backup_config():
        await backup_info.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    try:
        # 如果指定了服务器名，显示特定服务器的备份信息
        if args:
            server_name = args[0]

            # 验证服务器名是否存在
            try:
                get_instance_id(server_name)
            except ValueError as e:
                await backup_info.send(f'❌ {str(e)}')
                return

            # 获取备份路径
            try:
                backup_path = get_server_backup_path(server_name)
            except ValueError as e:
                await backup_info.send(f'❌ {str(e)}')
                return

            message = f'📁 服务器 {server_name} 备份信息:\n\n'
            message += f'备份路径: {backup_path}\n'

            # 检查目录状态
            if os.path.exists(backup_path):
                message += f'目录状态: ✅ 存在\n'

                # 检查是否为Git仓库
                git_path = os.path.join(backup_path, '.git')
                if os.path.exists(git_path):
                    message += f'Git仓库: ✅ 已初始化\n'

                    # 获取提交数量
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['git', 'rev-list', '--count', 'HEAD'],
                            cwd=backup_path,
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            commit_count = int(result.stdout.strip())
                            message += f'备份次数: {commit_count} 次\n'

                            # 获取最后一次备份时间
                            result = subprocess.run(
                                ['git', 'log', '-1', '--format=%ci'],
                                cwd=backup_path,
                                capture_output=True,
                                text=True
                            )
                            if result.returncode == 0:
                                last_commit = result.stdout.strip()
                                message += f'最后备份: {last_commit}\n'
                        else:
                            message += f'备份次数: 0 次（未提交）\n'
                    except Exception:
                        message += f'备份次数: 无法获取\n'
                else:
                    message += f'Git仓库: ❌ 未初始化\n'

                # 检查文件数量
                file_count = 0
                for root, dirs, files in os.walk(backup_path):
                    if '.git' in dirs:
                        dirs.remove('.git')
                    file_count += len(files)

                message += f'文件数量: {file_count} 个\n'

                # 添加大小信息
                total_size = get_directory_size(backup_path)
                message += f'总大小: {format_size(total_size)}\n'

                # Git 仓库大小
                git_dir = os.path.join(backup_path, '.git')
                if os.path.exists(git_dir):
                    git_size = get_directory_size(git_dir)
                    message += f'Git仓库: {format_size(git_size)}\n'

                # 如果是全服备份，单独显示世界大小
                if GIT_BACKUP_CONFIG['backup_target'].lower() != 'world':
                    world_dir = os.path.join(backup_path, 'world')
                    if os.path.exists(world_dir):
                        world_size = get_directory_size(world_dir)
                        message += f'存档大小: {format_size(world_size)}\n'

                if file_count == 0:
                    message += f'\n⚠️ 备份目录为空！\n'
                    message += f'请确保：\n'
                    message += f'1. 服务器文件存在于备份目录中\n'
                    message += f'2. 或重新配置备份路径指向服务器实际目录\n'
                    message += f'3. 或手动复制服务器文件到备份目录'

            else:
                message += f'目录状态: ❌ 不存在（将自动创建）\n'

        else:
            # 显示总体备份配置
            message = f'⚙️ Git备份配置信息:\n\n'
            message += f'功能状态: {"✅ 已启用" if GIT_BACKUP_CONFIG["enabled"] else "❌ 已禁用"}\n'
            message += f'最大备份数: {GIT_BACKUP_CONFIG["max_backups"]} 个\n'
            message += f'提交者: {GIT_BACKUP_CONFIG["git_user_name"]} <{GIT_BACKUP_CONFIG["git_user_email"]}>\n\n'

            message += f'📂 配置的服务器:\n'
            for server_name in SERVER_INSTANCES.keys():
                try:
                    backup_path = get_server_backup_path(server_name)
                    status = "✅" if os.path.exists(backup_path) else "❌"
                    message += f'{status} {server_name}: {backup_path}\n'
                except ValueError:
                    message += f'❌ {server_name}: 未配置备份路径\n'

            message += f'\n💡 使用 /backup_info <服务器名> 查看详细信息'

        await backup_info.send(message)

    except Exception as e:
        import logging
        logging.error(f'获取备份信息时出错: {str(e)}', exc_info=True)
        await backup_info.send(f'❌ 获取备份信息时出错，请查看日志')


backup_list = on_command('backup_list')


@backup_list.handle()
@check_command_enabled('backup_list')
async def handle_backup_list(event: Event):
    """查看备份历史列表"""
    user, args, group = get_context(event)

    if not check_git_backup_config():
        await backup_list.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    if not args:
        await backup_list.send('❌ 请指定服务器名\n用法: /backup_list <服务器名>')
        return

    server_name = args[0]

    try:
        get_instance_id(server_name)
    except ValueError as e:
        await backup_list.send(f'❌ {str(e)}')
        return

    try:
        # 获取备份路径
        backup_path = get_server_backup_path(server_name)

        if not os.path.exists(backup_path):
            await backup_list.send(f'❌ 备份目录不存在: {backup_path}')
            return

        # 检查是否为Git仓库
        git_path = os.path.join(backup_path, '.git')
        if not os.path.exists(git_path):
            await backup_list.send(f'❌ 服务器 {server_name} 还没有Git备份历史')
            return

        # 获取Git提交历史
        import subprocess
        result = subprocess.run(
            ['git', 'log', '--oneline', '--max-count=20'],
            cwd=backup_path,
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().split('\n')
            message = f'📁 服务器 {server_name} 备份历史（最近20个）:\n\n'

            for i, commit in enumerate(commits, 1):
                # 解析提交信息
                parts = commit.split(' ', 1)
                if len(parts) >= 2:
                    commit_hash = parts[0]
                    commit_msg = parts[1]

                    # 获取提交日期
                    date_result = subprocess.run(
                        ['git', 'log', '-1', '--format=%ci', commit_hash],
                        cwd=backup_path,
                        capture_output=True,
                        text=True
                    )

                    # 获取文件变化统计
                    stat_result = subprocess.run(
                        ['git', 'show', '--stat', '--format=', commit_hash],
                        cwd=backup_path,
                        capture_output=True,
                        text=True
                    )

                    # 格式化显示
                    commit_date = ''
                    if date_result.returncode == 0:
                        full_date = date_result.stdout.strip()
                        # 提取日期部分 (YYYY-MM-DD HH:MM)
                        commit_date = full_date[:16] if len(full_date) >= 16 else full_date

                    # 解析文件变化统计
                    file_changes = ''
                    if stat_result.returncode == 0 and stat_result.stdout.strip():
                        lines = stat_result.stdout.strip().split('\n')
                        if lines:
                            # 最后一行通常是统计信息
                            last_line = lines[-1]
                            if 'file' in last_line and ('insertion' in last_line or 'deletion' in last_line):
                                # 简化统计信息
                                file_changes = f' ({last_line.strip()})'

                    message += f'{i:2d}. {commit_hash[:8]} - {commit_msg}\n'
                    if commit_date:
                        message += f'     📅 {commit_date}{file_changes}\n'
                else:
                    message += f'{i:2d}. {commit}\n'

            message += f'\n💡 使用 /backup_rollback {server_name} <版本号> 回滚'
            message += f'\n💡 版本号可以是序号(如 1)或提交hash(如 {commits[0].split()[0][:8]})'

            await backup_list.send(message)
        else:
            await backup_list.send(f'❌ 服务器 {server_name} 没有备份历史')

    except Exception as e:
        import logging
        logging.error(f'获取备份历史时出错: {str(e)}', exc_info=True)
        await backup_list.send(f'❌ 获取备份历史时出错: {str(e)}')


backup_rollback = on_command('backup_rollback')


@backup_rollback.handle()
@check_command_enabled('backup_rollback')
async def handle_backup_rollback(event: Event):
    """回滚到指定备份版本"""
    user, args, group = get_context(event)

    if not check_mcsm_config():
        await backup_rollback.send('❌ MCSM配置不完整，请检查环境变量配置')
        return

    if not check_git_backup_config():
        await backup_rollback.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    if len(args) < 2:
        await backup_rollback.send('❌ 请提供服务器名和版本号\n用法: /backup_rollback <服务器名> <版本号>\n使用 /backup_list <服务器名> 查看可用版本')
        return

    server_name = args[0]
    version_input = args[1]

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await backup_rollback.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    try:
        instance_id = get_instance_id(server_name)
    except ValueError as e:
        await backup_rollback.send(f'❌ {str(e)}')
        return

    try:
        # 获取备份路径
        backup_path = get_server_backup_path(server_name)

        if not os.path.exists(backup_path):
            await backup_rollback.send(f'❌ 备份目录不存在: {backup_path}')
            return

        # 检查是否为Git仓库
        git_path = os.path.join(backup_path, '.git')
        if not os.path.exists(git_path):
            await backup_rollback.send(f'❌ 服务器 {server_name} 还没有Git备份历史')
            return

        # 发送开始回滚的消息
        await backup_rollback.send(f'🔄 开始回滚服务器 {server_name} 到版本 {version_input}...')

        # 执行回滚操作
        success, message = await execute_backup_rollback(server_name, instance_id, backup_path, version_input)

        if success:
            await backup_rollback.send(f'✅ {message}')
        else:
            await backup_rollback.send(f'❌ 回滚失败: {message}')

    except Exception as e:
        import logging
        logging.error(f'回滚服务器 {server_name} 时出错: {str(e)}', exc_info=True)
        await backup_rollback.send(f'❌ 回滚过程中发生未知错误，请查看日志或联系管理员')


backup_analyze = on_command('backup_analyze')


@backup_analyze.handle()
@check_command_enabled('backup_analyze')
async def handle_backup_analyze(event: Event):
    """分析备份仓库大小和增长趋势"""
    user, args, group = get_context(event)

    if not check_git_backup_config():
        await backup_analyze.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    # 如果指定了服务器名，分析特定服务器
    if args:
        server_name = args[0]

        try:
            get_instance_id(server_name)
        except ValueError as e:
            await backup_analyze.send(f'❌ {str(e)}')
            return

        try:
            backup_path = get_server_backup_path(server_name)
        except ValueError as e:
            await backup_analyze.send(f'❌ {str(e)}')
            return

        if not os.path.exists(backup_path):
            await backup_analyze.send(f'❌ 备份目录不存在: {backup_path}')
            return

        # 分析单个服务器
        await analyze_single_server(backup_analyze, server_name, backup_path)

    else:
        # 分析所有服务器
        message = '📊 所有服务器备份分析:\n\n'
        total_size = 0
        total_git_size = 0
        total_commits = 0

        for server_name in SERVER_INSTANCES.keys():
            try:
                backup_path = get_server_backup_path(server_name)
                if os.path.exists(backup_path):
                    # 快速分析
                    size = get_directory_size(backup_path)
                    git_size = get_directory_size(os.path.join(backup_path, '.git'))

                    # 获取提交数量
                    import subprocess
                    commit_count_result = subprocess.run(
                        ['git', 'rev-list', '--count', 'HEAD'],
                        capture_output=True,
                        text=True,
                        cwd=backup_path
                    )
                    commits = int(commit_count_result.stdout.strip()) if commit_count_result.returncode == 0 else 0

                    total_size += size
                    total_git_size += git_size
                    total_commits += commits

                    message += f'🖥️ {server_name}:\n'
                    message += f'   📁 总大小: {format_size(size)}\n'
                    message += f'   📝 提交数: {commits} 个\n'
                    message += f'   💾 Git历史: {format_size(git_size)}\n\n'
                else:
                    message += f'🖥️ {server_name}: ❌ 无备份\n\n'
            except Exception as e:
                message += f'🖥️ {server_name}: ❌ 分析失败 - {str(e)}\n\n'

        message += f'📈 总计统计:\n'
        message += f'总大小: {format_size(total_size)}\n'
        message += f'Git历史: {format_size(total_git_size)}\n'
        message += f'总提交数: {total_commits} 个\n\n'
        message += f'💡 使用 /backup_analyze <服务器名> 查看详细分析'

        await backup_analyze.send(message)


backup_clean = on_command('backup_clean')


@backup_clean.handle()
@check_command_enabled('backup_clean')
async def handle_backup_clean(event: Event):
    """手动清理备份仓库Git历史"""
    user, args, group = get_context(event)

    if not check_git_backup_config():
        await backup_clean.send('❌ Git备份功能未启用或配置不完整\n请检查环境变量: GIT_BACKUP_ENABLED, GIT_BACKUP_PATHS')
        return

    if not args:
        await backup_clean.send('❌ 请指定服务器名\n用法: /backup_clean <服务器名>')
        return

    server_name = args[0]

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await backup_clean.send(f'❌ 权限不足，需要 "{server_name}" 服务器权限')
        return

    try:
        get_instance_id(server_name)
    except ValueError as e:
        await backup_clean.send(f'❌ {str(e)}')
        return

    try:
        # 获取备份路径
        backup_path = get_server_backup_path(server_name)

        if not os.path.exists(backup_path):
            await backup_clean.send(f'❌ 备份目录不存在: {backup_path}')
            return

        # 检查是否为Git仓库
        git_path = os.path.join(backup_path, '.git')
        if not os.path.exists(git_path):
            await backup_clean.send(f'❌ 服务器 {server_name} 不是Git备份仓库')
            return

        # 获取清理前的信息
        total_size_before = get_directory_size(backup_path)
        git_size_before = get_directory_size(git_path)

        import subprocess
        commit_count_result = subprocess.run(
            ['git', 'rev-list', '--count', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=backup_path
        )
        commit_count = int(commit_count_result.stdout.strip()) if commit_count_result.returncode == 0 else 0

        # 发送确认消息
        await backup_clean.send(f'🔄 开始清理服务器 {server_name} 的备份仓库...\n'
                               f'📊 当前状态：{commit_count} 个提交，Git历史 {format_size(git_size_before)}')

        # 执行清理
        success, message = await clean_git_repository(backup_path, server_name)

        if success:
            # 获取清理后的信息
            total_size_after = get_directory_size(backup_path)
            savings = total_size_before - total_size_after

            await backup_clean.send(f'✅ {message}\n'
                                   f'💾 节省空间：{format_size(savings)}\n'
                                   f'📁 新大小：{format_size(total_size_after)}')
        else:
            await backup_clean.send(f'❌ 清理失败: {message}')

    except Exception as e:
        import logging
        logging.error(f'清理备份仓库 {server_name} 时出错: {str(e)}', exc_info=True)
        await backup_clean.send(f'❌ 清理过程中发生未知错误，请查看日志或联系管理员')
