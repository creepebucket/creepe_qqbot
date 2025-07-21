import os

from baimomcsm_api import applications
from redstone_daily.plugins.mc_management.config import (
    get_instance_id, get_server_backup_path, MCSM_CONFIG, 
    GIT_BACKUP_CONFIG, get_directory_size, format_size
)
from redstone_daily.plugins.utils import get_database


async def execute_git_backup(server_name: str, backup_description: str = '') -> tuple[bool, str]:
    """
    执行 Git 备份流程

    Args:
        server_name: 服务器名称
        backup_description: 备份描述

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    import subprocess
    import os
    from datetime import datetime

    try:
        # 获取服务器实例ID和备份路径
        instance_id = get_instance_id(server_name)
        backup_path = get_server_backup_path(server_name)

        # 自动创建备份目录（如果不存在）
        try:
            os.makedirs(backup_path, exist_ok=True)
        except PermissionError:
            return False, f'无权限创建备份目录: {backup_path}'
        except OSError as e:
            return False, f'创建备份目录失败: {backup_path} - {str(e)}'

        # 验证备份路径是否可用
        if not os.path.exists(backup_path):
            return False, f'备份路径创建失败: {backup_path}'

        if not os.path.isdir(backup_path):
            return False, f'备份路径不是有效目录: {backup_path}'

        # 步骤1: 发送 save-all 指令保存世界
        save_result = applications.send_command(
            MCSM_CONFIG['url'],
            instance_id,
            MCSM_CONFIG['daemon_id'],
            MCSM_CONFIG['apikey'],
            'save-all'
        )

        if not save_result:
            return False, '发送存档保存指令失败'

        # 等待存档完成
        import time
        time.sleep(20)

        # 切换到备份目录
        original_cwd = os.getcwd()
        os.chdir(backup_path)

        try:
            # 步骤2: 检查是否需要 git 初始化
            if not os.path.exists('.git'):
                # 初始化 git 仓库
                subprocess.run(['git', 'init'], check=True, capture_output=True)
                subprocess.run(['git', 'config', 'user.name', GIT_BACKUP_CONFIG['git_user_name']], check=True)
                subprocess.run(['git', 'config', 'user.email', GIT_BACKUP_CONFIG['git_user_email']], check=True)

                # 创建 .gitignore 文件，忽略一些不需要备份的文件
                gitignore_content = """# 临时文件
*.tmp
*.temp
*.log

# 系统文件
Thumbs.db
.DS_Store

# 进程锁文件
*.pid
*.lock
"""
                with open('.gitignore', 'w', encoding='utf-8') as f:
                    f.write(gitignore_content)

            # 检查目录中是否有文件（除了.git目录）
            all_files = []
            for root, dirs, files in os.walk('..'):
                # 跳过.git目录
                if '.git' in dirs:
                    dirs.remove('.git')
                for file in files:
                    if not file.startswith('.git'):
                        all_files.append(os.path.join(root, file))

            # 如果目录为空或只有.gitignore，提供提示
            if not all_files or (len(all_files) == 1 and all_files[0] in ['./.gitignore', '.gitignore']):
                return False, f'备份目录 {backup_path} 为空或没有需要备份的文件\n请确保：\n1. 服务器文件存在于此目录\n2. 或手动复制服务器文件到此目录\n3. 或重新配置 GIT_BACKUP_PATHS 指向正确的服务器目录'

            # 添加所有文件到暂存区
            subprocess.run(['git', 'add', '.'], check=True, capture_output=True)

            # 检查是否有变更
            status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
            if not status_result.stdout.strip():
                # 再次检查是否是首次提交
                try:
                    subprocess.run(['git', 'rev-parse', 'HEAD'], check=True, capture_output=True)
                    # 如果能成功执行，说明已有提交，确实没有变更
                    return True, '没有检测到变更，无需备份'
                except subprocess.CalledProcessError:
                    # 如果失败，说明是首次提交，应该继续执行
                    pass

            # 步骤3: 创建提交
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_message = f'[{server_name}] 自动备份 - {current_time}'
            if backup_description:
                commit_message += f' - {backup_description}'

            subprocess.run(['git', 'commit', '-m', commit_message], check=True, capture_output=True)

            # 步骤4: 管理备份数量 - 使用 rebase 合并旧提交
            await manage_backup_history(backup_path)

            # 计算备份大小
            total_size = get_directory_size(backup_path)

            # 计算世界存档大小（如果是全服备份）
            world_size = 0
            if GIT_BACKUP_CONFIG['backup_target'].lower() != 'world':
                world_dir = os.path.join(backup_path, 'world')
                if os.path.exists(world_dir):
                    world_size = get_directory_size(world_dir)
            else:
                world_size = total_size

            # 构建结果消息
            size_info = f'总大小: {format_size(total_size)}'
            if world_size > 0 and GIT_BACKUP_CONFIG['backup_target'].lower() != 'world':
                size_info += f' | 存档大小: {format_size(world_size)}'

            return True, f'备份完成: {commit_message}\n📊 {size_info}'

        finally:
            # 恢复原工作目录
            os.chdir(original_cwd)

    except subprocess.CalledProcessError as e:
        return False, f'Git 操作失败: {e.stderr.decode() if e.stderr else str(e)}'
    except Exception as e:
        return False, f'备份过程出错: {str(e)}'


async def manage_backup_history(backup_path: str):
    """
    管理备份历史记录，保持指定数量的备份
    分析仓库大小增长并提供手动清理提示

    Args:
        backup_path: 备份路径
    """
    import subprocess
    import os

    max_backups = GIT_BACKUP_CONFIG['max_backups']
    if max_backups <= 0:
        return

    try:
        # 获取提交数量
        commit_count_result = subprocess.run(
            ['git', 'rev-list', '--count', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=backup_path
        )

        commit_count = int(commit_count_result.stdout.strip())

        # 分析仓库大小
        total_size = get_directory_size(backup_path)
        git_size = get_directory_size(os.path.join(backup_path, '.git'))
        working_size = total_size - git_size

        print(f"🔍 检查备份历史：{backup_path}")
        print(f"📊 提交数量：{commit_count} 个（限制：{max_backups} 个）")
        print(f"📁 总大小：{format_size(total_size)} | Git历史：{format_size(git_size)} | 工作目录：{format_size(working_size)}")

        # 分析增长趋势
        if commit_count > 5:
            # 计算平均每次备份Git增长（排除第一个初始提交）
            effective_commits = commit_count - 1 if commit_count > 1 else 1
            avg_git_size_per_commit = git_size / effective_commits
            print(f"📈 平均每次备份Git增长：{format_size(avg_git_size_per_commit)} (排除初始提交)")

            # 预测节省空间
            if commit_count > max_backups:
                excess_commits = commit_count - max_backups
                potential_savings = excess_commits * avg_git_size_per_commit
                print(f"💾 删除 {excess_commits} 个旧备份可节省约：{format_size(potential_savings)}")

        # 当提交数量超过限制时的处理
        if commit_count > max_backups:
            print(f"⚠️ 备份数量已达到 {commit_count} 个，超过限制 {max_backups} 个")
            print(f"💡 建议手动清理：/backup_clean {os.path.basename(backup_path)}")
            print(f"💡 或查看备份历史：/backup_list {os.path.basename(backup_path)}")
            print(f"💡 或增加限制：调整 GIT_BACKUP_MAX_COUNT 配置")
        else:
            print(f"📊 备份数量正常：{commit_count}/{max_backups}，无需清理")

    except (subprocess.CalledProcessError, ValueError, IndexError) as e:
        # 如果历史管理失败，记录错误但不影响备份主流程
        print(f"⚠️ 备份历史管理出错：{backup_path} - {str(e)}")
        pass


async def execute_backup_rollback(server_name: str, instance_id: str, backup_path: str, version_input: str) -> tuple[bool, str]:
    """
    执行备份回滚操作

    Args:
        server_name: 服务器名称
        instance_id: MCSM实例ID
        backup_path: 备份路径
        version_input: 版本输入（序号或提交hash）

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    import subprocess
    import time

    try:
        # 步骤1: 获取当前服务器状态
        current_status = applications.get_status(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
        was_running = (current_status == 3)  # 3表示运行中

        # 步骤2: 如果服务器正在运行，先停止服务器
        if was_running:
            stop_result = applications.stop_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
            if not stop_result:
                return False, '无法停止服务器'

            # 等待服务器停止
            for _ in range(30):  # 最多等待30秒
                time.sleep(1)
                status = applications.get_status(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
                if status != 3:  # 不是运行状态
                    break
            else:
                return False, '服务器停止超时，请手动检查服务器状态'

        # 步骤3: 解析版本输入，获取目标提交hash
        target_commit = await resolve_version_to_commit(backup_path, version_input)
        if not target_commit:
            return False, f'无效的版本号: {version_input}'

        # 步骤4: 创建安全备份点（当前状态）
        original_cwd = os.getcwd()
        os.chdir(backup_path)

        try:
            # 保存当前状态为临时分支
            subprocess.run(['git', 'branch', 'rollback-backup-temp'], check=True, capture_output=True)

            # 执行回滚
            subprocess.run(['git', 'reset', '--hard', target_commit], check=True, capture_output=True)

            # 获取目标提交的信息
            commit_info_result = subprocess.run(
                ['git', 'log', '-1', '--format=%h - %s (%ci)', target_commit],
                capture_output=True,
                text=True
            )
            commit_info = commit_info_result.stdout.strip() if commit_info_result.returncode == 0 else target_commit

        except subprocess.CalledProcessError as e:
            # 回滚失败，恢复到原状态
            try:
                subprocess.run(['git', 'reset', '--hard', 'rollback-backup-temp'], capture_output=True)
                subprocess.run(['git', 'branch', '-D', 'rollback-backup-temp'], capture_output=True)
            except:
                pass
            return False, f'Git回滚操作失败: {e.stderr.decode() if e.stderr else str(e)}'

        finally:
            os.chdir(original_cwd)

        # 步骤5: 如果原来服务器在运行，重新启动
        if was_running:
            time.sleep(2)  # 短暂等待
            start_result = applications.start_app(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
            if not start_result:
                # 启动失败，但回滚已成功
                message = f'回滚成功: {commit_info}\n⚠️ 但服务器重启失败，请手动启动服务器'
            else:
                message = f'回滚成功: {commit_info}\n✅ 服务器已重新启动'
        else:
            message = f'回滚成功: {commit_info}\n💡 服务器保持停止状态'

        # 清理临时分支
        try:
            os.chdir(backup_path)
            subprocess.run(['git', 'branch', '-D', 'rollback-backup-temp'], capture_output=True)
            os.chdir(original_cwd)
        except:
            pass

        return True, message

    except Exception as e:
        return False, f'回滚过程出错: {str(e)}'


async def resolve_version_to_commit(backup_path: str, version_input: str) -> str:
    """
    解析版本输入为具体的提交hash

    Args:
        backup_path: 备份路径
        version_input: 版本输入（序号或提交hash）

    Returns:
        str: 提交hash，失败返回空字符串
    """
    import subprocess

    try:
        # 如果输入看起来像提交hash（长度为7-40的十六进制字符串）
        if len(version_input) >= 7 and all(c in '0123456789abcdef' for c in version_input.lower()):
            # 验证提交是否存在
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', f'{version_input}^{{commit}}'],
                cwd=backup_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()

        # 如果输入是数字，当作序号处理
        if version_input.isdigit():
            sequence_num = int(version_input)
            if sequence_num < 1:
                return ''

            # 获取第N个提交的hash
            result = subprocess.run(
                ['git', 'rev-list', '--reverse', 'HEAD'],
                cwd=backup_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                commits = result.stdout.strip().split('\n')
                if 1 <= sequence_num <= len(commits):
                    return commits[sequence_num - 1]

        return ''

    except (subprocess.CalledProcessError, ValueError):
        return ''


async def analyze_single_server(command_handler, server_name: str, backup_path: str):
    """分析单个服务器的备份情况"""
    import subprocess
    import os
    from datetime import datetime

    try:
        # 基本信息
        total_size = get_directory_size(backup_path)
        git_size = get_directory_size(os.path.join(backup_path, '.git'))
        working_size = total_size - git_size

        # 获取提交信息
        commit_count_result = subprocess.run(
            ['git', 'rev-list', '--count', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=backup_path
        )
        commit_count = int(commit_count_result.stdout.strip()) if commit_count_result.returncode == 0 else 0

        message = f'📊 服务器 {server_name} 备份分析\n\n'
        message += f'📁 存储分析:\n'
        message += f'• 总大小: {format_size(total_size)}\n'
        message += f'• Git历史: {format_size(git_size)} ({git_size / total_size * 100:.1f}%)\n'
        message += f'• 工作目录: {format_size(working_size)} ({working_size / total_size * 100:.1f}%)\n\n'

        message += f'📝 提交分析:\n'
        message += f'• 总提交数: {commit_count} 个\n'

        if commit_count > 1:
            # 计算平均每次提交Git增长（排除第一个提交）
            effective_commits = commit_count - 1  # 排除第一个初始提交
            if effective_commits > 0:
                avg_git_per_commit = git_size / commit_count  # 总体平均
                effective_avg = git_size / effective_commits if effective_commits > 0 else 0  # 排除初始提交的平均
                message += f'• 平均每次提交Git增长: {format_size(effective_avg)} (排除初始提交)\n'

            # 获取第一次和最后一次提交时间
            try:
                first_commit_result = subprocess.run(
                    ['git', 'log', '--reverse', '--format=%ci', '--max-count=1'],
                    capture_output=True,
                    text=True,
                    cwd=backup_path
                )
                last_commit_result = subprocess.run(
                    ['git', 'log', '--format=%ci', '--max-count=1'],
                    capture_output=True,
                    text=True,
                    cwd=backup_path
                )

                if first_commit_result.returncode == 0 and last_commit_result.returncode == 0:
                    first_time_str = first_commit_result.stdout.strip()
                    last_time_str = last_commit_result.stdout.strip()

                    # 解析时间（ISO格式）
                    first_time = datetime.fromisoformat(first_time_str.replace(' +0800', ''))
                    last_time = datetime.fromisoformat(last_time_str.replace(' +0800', ''))

                    duration = last_time - first_time
                    days = duration.days

                    if days > 0:
                        commits_per_day = commit_count / days
                        git_growth_per_day = git_size / days

                        message += f'• 备份历史跨度: {days} 天\n'
                        message += f'• 平均每天提交: {commits_per_day:.1f} 次\n'
                        message += f'• 平均每天Git增长: {format_size(git_growth_per_day)}\n'
            except Exception:
                pass

        # 配置检查
        max_backups = GIT_BACKUP_CONFIG['max_backups']
        message += f'\n⚙️ 配置状态:\n'
        message += f'• 备份限制: {max_backups} 个\n'

        if commit_count > max_backups:
            excess = commit_count - max_backups
            # 使用排除初始提交的平均值来估算节省空间
            if commit_count > 1:
                effective_avg = git_size / (commit_count - 1) if (commit_count - 1) > 0 else 0
                potential_savings = excess * effective_avg
            else:
                potential_savings = 0
            message += f'• ⚠️ 超出限制: {excess} 个提交\n'
            message += f'• 💾 可节省空间: 约 {format_size(potential_savings)}\n'
            message += f'• 💡 建议手动清理: /backup_clean {server_name}\n'
        else:
            message += f'• ✅ 在限制范围内\n'

        await command_handler.send(message)

    except Exception as e:
        await command_handler.send(f'❌ 分析服务器 {server_name} 时出错: {str(e)}')


async def clean_git_repository(backup_path: str, server_name: str) -> tuple[bool, str]:
    """
    彻底清理Git仓库，删除所有历史记录并重新初始化

    Args:
        backup_path: 备份路径
        server_name: 服务器名称

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    import shutil
    import subprocess
    from datetime import datetime

    try:
        git_path = os.path.join(backup_path, '.git')

        # 删除.git目录
        if os.path.exists(git_path):
            shutil.rmtree(git_path)

        # 重新初始化Git仓库
        subprocess.run(['git', 'init'], cwd=backup_path, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', GIT_BACKUP_CONFIG['git_user_name']], cwd=backup_path, check=True)
        subprocess.run(['git', 'config', 'user.email', GIT_BACKUP_CONFIG['git_user_email']], cwd=backup_path, check=True)

        # 创建 .gitignore 文件
        gitignore_content = """# 临时文件
*.tmp
*.temp
*.log

# 系统文件
Thumbs.db
.DS_Store

# 进程锁文件
*.pid
*.lock
"""
        with open(os.path.join(backup_path, '.gitignore'), 'w', encoding='utf-8') as f:
            f.write(gitignore_content)

        # 添加所有文件并创建初始提交
        subprocess.run(['git', 'add', '.'], cwd=backup_path, check=True, capture_output=True)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_message = f'[{server_name}] 清理后重新初始化 - {current_time}'
        subprocess.run(['git', 'commit', '-m', commit_message], cwd=backup_path, check=True, capture_output=True)

        return True, f'Git仓库已清理并重新初始化，创建新的初始提交'

    except subprocess.CalledProcessError as e:
        return False, f'Git操作失败: {e.stderr.decode() if e.stderr else str(e)}'
    except Exception as e:
        return False, f'清理过程出错: {str(e)}'


class AutoBackupManager:
    """自动备份管理器"""

    def __init__(self):
        self.db = get_database('auto_backup')
        self.collection = self.db.get_db()
        self._scheduler_running = False
        self._scheduler_task = None

    def get_server_config(self, server_name: str) -> dict:
        """获取服务器自动备份配置"""
        return self.collection.find_one({'server_name': server_name}) or {
            'server_name': server_name,
            'enabled': False,
            'interval_minutes': 360,  # 默认6小时=360分钟
            'last_backup': None,
            'next_backup': None
        }

    def set_server_config(self, server_name: str, config: dict):
        """设置服务器自动备份配置"""
        config['server_name'] = server_name
        self.collection.update_one(
            {'server_name': server_name},
            {'$set': config},
            upsert=True
        )

    def get_all_enabled_servers(self) -> list:
        """获取所有启用自动备份的服务器"""
        return list(self.collection.find({'enabled': True}))

    async def check_players_online(self, server_name: str) -> int:
        """检查服务器在线玩家数量"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            instance_id = get_instance_id(server_name)
            print(f'{server_name}: 正在检查玩家在线状态，实例ID: {instance_id}')
            
            result = applications.get_info(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
            print(f'{server_name}: MCSM API响应: {result}')

            if result.get('status') == 200:
                data = result['data']
                print(f'{server_name}: 服务器状态: {data.get("status")}, 详细信息: {data.get("info", {})}')
                
                if data['status'] == 3:  # 运行中
                    if 'info' in data:
                        players = data['info'].get('currentPlayers', 0)
                        print(f'{server_name}: 检测到 {players} 个玩家在线')
                        print(f'{server_name}: 检测到 {players} 个玩家在线')
                        return players
                    else:
                        print(f'{server_name}: 服务器运行中但缺少info字段')
                        print(f'{server_name}: 服务器运行中但缺少info字段')
                else:
                    print(f'{server_name}: 服务器未运行 (状态: {data.get("status")})')
                    print(f'{server_name}: 服务器未运行 (状态: {data.get("status")})')
            else:
                print(f'{server_name}: MCSM API调用失败，状态码: {result.get("status")}')
                print(f'{server_name}: MCSM API调用失败，状态码: {result.get("status")}')
            
            print(f'{server_name}: 返回0个玩家在线')
            print(f'{server_name}: 返回0个玩家在线')
            return 0
        except Exception as e:
            print(f'{server_name}: 检查玩家在线状态时出错: {str(e)}')
            return 0

    async def silent_backup(self, server_name: str) -> tuple[bool, str]:
        """静默备份（不发送QQ消息）"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            print(f'{server_name}: 开始静默备份流程')
            print(f'{server_name}: 开始静默备份流程')
            
            # 检查玩家在线状态
            players_online = await self.check_players_online(server_name)
            print(f'{server_name}: 玩家检查完成，在线玩家数: {players_online}')
            print(f'{server_name}: 玩家检查完成，在线玩家数: {players_online}')
            
            if players_online == 0:
                print(f'{server_name}: 没有玩家在线，跳过备份')
                print(f'{server_name}: 没有玩家在线，跳过备份')
                return True, f'服务器 {server_name} 没有玩家在线，跳过备份'

            print(f'{server_name}: 有 {players_online} 个玩家在线，开始执行备份')
            print(f'{server_name}: 有 {players_online} 个玩家在线，开始执行备份')
            
            # 执行备份
            success, message = await execute_git_backup(server_name, f'定时备份 (在线玩家: {players_online})')
            print(f'{server_name}: 备份执行完成，结果: {"成功" if success else "失败"}, 消息: {message}')

            # 更新最后备份时间
            if success:
                from datetime import datetime
                config = self.get_server_config(server_name)
                config['last_backup'] = datetime.now().isoformat()
                # 计算下次备份时间
                from datetime import timedelta
                next_backup = datetime.now() + timedelta(minutes=config['interval_minutes'])
                config['next_backup'] = next_backup.isoformat()
                self.set_server_config(server_name, config)
                print(f'{server_name}: 备份时间已更新，下次备份: {next_backup.strftime("%Y-%m-%d %H:%M:%S")}')

            return success, message
        except Exception as e:
            print(f'{server_name}: 定时备份出错: {str(e)}')
            return False, f'定时备份出错: {str(e)}'


async def diagnose_git_repository(backup_path: str, server_name: str, progress_callback=None, detailed_mode=False) -> tuple[bool, str, list]:
    """
    诊断Git仓库问题，找出导致"不稳定对象源数据"错误的文件

    Args:
        backup_path: 备份路径
        server_name: 服务器名称
        progress_callback: 进度回调函数

    Returns:
        tuple[bool, str, list]: (是否有问题, 诊断报告, 问题文件列表)
    """
    import subprocess
    import os
    import asyncio
    from pathlib import Path

    problematic_files = []
    diagnostic_report = []

    async def send_progress(message):
        print(f"[诊断进度] {message}")

        return  # 太刷屏了, 看日志就够

        """发送进度消息"""
        if progress_callback:
            await progress_callback(message)

    try:
        # 切换到备份目录
        original_cwd = os.getcwd()
        os.chdir(backup_path)

        try:
            # 步骤1: 检查git仓库状态
            await send_progress(f'🔍 开始诊断服务器 {server_name} 的Git仓库')
            
            # 检查git仓库完整性
            await send_progress(f'🔎 检查Git仓库完整性...')
            try:
                result = subprocess.run(['git', 'fsck', '--full'], capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    await send_progress(f'⚠️ Git仓库完整性检查失败')
                    if result.stderr:
                        diagnostic_report.append(f'   {result.stderr.strip()}')
                else:
                    await send_progress(f'✅ Git仓库完整性检查通过')
            except subprocess.TimeoutExpired:
                await send_progress(f'⚠️ Git完整性检查超时，跳过')
            except Exception as e:
                await send_progress(f'⚠️ Git完整性检查失败: {str(e)}')

            # 步骤2: 重置暂存区并获取文件列表
            await send_progress(f'🔄 重置Git暂存区')
            subprocess.run(['git', 'reset'], capture_output=True)

            await send_progress(f'📁 扫描文件列表...')
            # 获取所有文件并进行智能过滤
            all_files = []
            skipped_files = []
            
            # 定义需要跳过的文件类型（通常不会引起Git问题）
            skip_extensions = {'.log', '.tmp', '.cache', '.bak', '.old', '.lock', '.pid'}
            skip_patterns = {'__pycache__', '.DS_Store', 'Thumbs.db', '.minecraft'}
            
            for root, dirs, files in os.walk('.'):
                # 跳过.git目录
                if '.git' in dirs:
                    dirs.remove('.git')
                    
                # 跳过一些明显的缓存目录
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in skip_patterns)]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    # 转换为相对路径并标准化
                    rel_path = os.path.relpath(file_path, '.')
                    
                    if rel_path.startswith('.git') or rel_path == '.':
                        continue
                        
                    # 检查是否需要跳过
                    file_ext = os.path.splitext(file)[1].lower()
                    if (file_ext in skip_extensions or 
                        any(pattern in file for pattern in skip_patterns)):
                        skipped_files.append(rel_path)
                        continue
                        
                    all_files.append(rel_path)

            await send_progress(f'📊 找到 {len(all_files)} 个文件需要检查 (跳过 {len(skipped_files)} 个临时文件)')
            
            # 如果没有文件需要检查
            if not all_files:
                diagnostic_report.append('ℹ️ 没有找到需要检查的文件')
                return False, '\n'.join(diagnostic_report), []

            # 步骤3: 首先进行快速检测
            await send_progress(f'⚡ 执行快速Git状态检测...')
            quick_problems = await _quick_git_check(send_progress)
            if quick_problems:
                problematic_files.extend(quick_problems)
                await send_progress(f'🚨 快速检测发现 {len(quick_problems)} 个问题')
                
                # 如果快速检测已经发现了问题且非详细模式，可以直接返回结果
                if len(quick_problems) > 0 and not detailed_mode:
                    diagnostic_report.extend([
                        f'📋 快速诊断完成:',
                        f'• 总文件数: {len(all_files)}',
                        f'• 快速检测发现问题: {len(quick_problems)}',
                        f'💡 如需详细检测，请添加 --detailed 参数'
                    ])
                    
                    if quick_problems:
                        diagnostic_report.append(f'\n🚨 快速检测发现的问题:')
                        for file_info in quick_problems[:5]:  # 只显示前5个
                            diagnostic_report.append(f'• {file_info["path"]} - {file_info["error"]}')
                        if len(quick_problems) > 5:
                            diagnostic_report.append(f'• ... 还有 {len(quick_problems) - 5} 个问题')
                    
                    return len(quick_problems) > 0, '\n'.join(diagnostic_report), quick_problems
                elif len(quick_problems) > 0 and detailed_mode:
                    await send_progress(f'🔍 已启用详细模式，继续深度检测...')
            else:
                await send_progress(f'✅ 快速检测未发现明显问题')
                # 如果非详细模式且快速检测没有发现问题，直接返回
                if not detailed_mode:
                    diagnostic_report.extend([
                        f'📋 快速诊断完成:',
                        f'• 总文件数: {len(all_files)}',
                        f'• 快速检测结果: 未发现明显问题',
                        f'💡 如需详细检测，请添加 --detailed 参数'
                    ])
                    return False, '\n'.join(diagnostic_report), []
                else:
                    await send_progress(f'🔍 已启用详细模式，继续深度检测...')
            
            # 在详细模式下，不使用批量检测，直接进行逐个文件检测
            # 如果文件太多且不是详细模式，才使用批量检测策略
            if len(all_files) > 500 and not detailed_mode:
                await send_progress(f'⚡ 文件数量较多 ({len(all_files)} 个)，使用快速批量检测模式')
                return await _fast_batch_diagnose(all_files, problematic_files, diagnostic_report, send_progress)

            # 步骤4: 逐个添加文件并检测问题 (只在详细模式下进行)
            if not detailed_mode:
                await send_progress(f'ℹ️ 跳过详细文件检测，如需要请使用 --detailed 参数')
                # 返回已有的快速检测结果
                diagnostic_report.extend([
                    f'📋 诊断总结:',
                    f'• 总文件数: {len(all_files)}',
                    f'• 问题文件数: {len(problematic_files)}'
                ])
                return len(problematic_files) > 0, '\n'.join(diagnostic_report), problematic_files
            
            await send_progress(f'🔍 开始详细文件检测 (逐个检查 {len(all_files)} 个文件)...')
            check_count = 0
            failed_count = 0
            
            # 先重置git状态确保干净的环境
            subprocess.run(['git', 'reset'], capture_output=True)
            
            for file_path in all_files:
                check_count += 1
                
                # 每检查50个文件发送一次进度
                if check_count % 50 == 0:
                    await send_progress(f'📊 检查进度: {check_count}/{len(all_files)} (发现问题: {failed_count})')
                
                try:
                    # 检查文件是否存在且可读
                    if not os.path.exists(file_path):
                        problematic_files.append({
                            'path': file_path,
                            'error': '文件不存在',
                            'type': 'missing'
                        })
                        failed_count += 1
                        await send_progress(f'❌ 文件不存在: {file_path}')
                        continue

                    # 检查文件大小，跳过超大文件的详细检测  
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > 500 * 1024 * 1024:  # 500MB，提高阈值
                            await send_progress(f'⚠️ 跳过超大文件: {file_path} ({file_size // 1024 // 1024}MB)')
                            continue
                    except:
                        pass

                    # 尝试添加单个文件到git
                    result = subprocess.run(['git', 'add', file_path], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode != 0:
                        error_msg = result.stderr.strip() if result.stderr else '未知添加错误'
                        
                        # 检查是否是"不稳定对象源数据"错误
                        is_corrupt = ('不稳定对象源数据' in error_msg or 
                                     'malformed object' in error_msg.lower() or
                                     'corrupt' in error_msg.lower() or
                                     'bad file' in error_msg.lower())
                        
                        problematic_files.append({
                            'path': file_path,
                            'error': error_msg,
                            'type': 'corrupt_object' if is_corrupt else 'add_error'
                        })
                        
                        if is_corrupt:
                            await send_progress(f'💀 发现损坏文件: {file_path}')
                        else:
                            await send_progress(f'❌ 文件添加失败: {file_path}')
                        
                        failed_count += 1
                        
                        # 重置暂存区，继续检查其他文件
                        subprocess.run(['git', 'reset'], capture_output=True)
                        continue
                    else:
                        # 添加成功，重置暂存区以检查下一个文件
                        subprocess.run(['git', 'reset'], capture_output=True)

                    # 让出控制权，避免阻塞
                    if check_count % 100 == 0:
                        await asyncio.sleep(0.1)

                except subprocess.TimeoutExpired:
                    problematic_files.append({
                        'path': file_path,
                        'error': 'Git操作超时',
                        'type': 'timeout'
                    })
                    await send_progress(f'⏰ 文件检查超时: {file_path}')
                    failed_count += 1
                    subprocess.run(['git', 'reset'], capture_output=True)
                except Exception as e:
                    problematic_files.append({
                        'path': file_path,
                        'error': str(e),
                        'type': 'exception'
                    })
                    await send_progress(f'⚠️ 文件检查异常: {file_path} - {str(e)}')
                    failed_count += 1

            # 步骤5: 生成诊断总结
            await send_progress(f'📋 诊断完成！')
            diagnostic_report.append(f'📋 诊断总结:')
            diagnostic_report.append(f'• 总文件数: {len(all_files)}')
            diagnostic_report.append(f'• 问题文件数: {len(problematic_files)}')

            if problematic_files:
                diagnostic_report.append(f'\n🚨 发现问题文件:')
                for file_info in problematic_files[:10]:  # 只显示前10个
                    diagnostic_report.append(f'• {file_info["path"]} - {file_info["error"]}')
                if len(problematic_files) > 10:
                    diagnostic_report.append(f'• ... 还有 {len(problematic_files) - 10} 个问题文件')

            return len(problematic_files) > 0, '\n'.join(diagnostic_report), problematic_files

        finally:
            # 恢复原工作目录
            os.chdir(original_cwd)

    except Exception as e:
        error_msg = f'诊断过程出错: {str(e)}'
        await send_progress(error_msg)
        diagnostic_report.append(error_msg)
        return True, '\n'.join(diagnostic_report), []


async def _quick_git_check(send_progress):
    """快速Git状态检测"""
    import subprocess
    
    problems = []
    
    try:
        # 1. 检查Git状态
        await send_progress("🔍 检查Git工作区状态...")
        status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, timeout=10)
        
        # 2. 尝试添加所有文件
        await send_progress("🔄 尝试批量添加文件...")
        add_result = subprocess.run(['git', 'add', '.'], capture_output=True, text=True, timeout=30)
        
        if add_result.returncode != 0:
            await send_progress("❌ 批量添加失败，存在问题文件")
            # 解析错误信息，提取问题文件
            for line in add_result.stderr.split('\n'):
                line = line.strip()
                if ('error:' in line.lower() or 'fatal:' in line.lower() or 
                    '不稳定对象源数据' in line or 'malformed' in line.lower()):
                    # 尝试提取文件名
                    import re
                    file_matches = re.findall(r'[\'"]([^\'\"]+)[\'"]', line)
                    if file_matches:
                        for file_path in file_matches:
                            if '/' in file_path or '.' in file_path:
                                problems.append({
                                    'path': file_path,
                                    'error': '快速检测发现问题',
                                    'type': 'quick_check_error'
                                })
                                await send_progress(f"💀 快速检测发现问题文件: {file_path}")
        else:
            await send_progress("✅ 批量添加成功")
            
            # 3. 尝试提交检测
            await send_progress("🔍 检查提交状态...")
            commit_result = subprocess.run(
                ['git', 'commit', '--dry-run', '-m', 'quick_test'], 
                capture_output=True, text=True, timeout=15
            )
            
            if commit_result.returncode != 0:
                if ('不稳定对象源数据' in commit_result.stderr or 
                    'malformed object' in commit_result.stderr.lower() or
                    'corrupt' in commit_result.stderr.lower()):
                    await send_progress("💀 检测到Git对象损坏")
                    problems.append({
                        'path': 'git_objects',
                        'error': 'Git对象损坏',
                        'type': 'git_corruption'
                    })
                    
    except subprocess.TimeoutExpired:
        await send_progress("⏰ 快速检测超时")
    except Exception as e:
        await send_progress(f"⚠️ 快速检测异常: {str(e)}")
        
    return problems


async def _fast_batch_diagnose(all_files, problematic_files, diagnostic_report, send_progress):
    """快速批量诊断模式"""
    import subprocess
    import asyncio
    
    await send_progress(f'🚀 执行快速批量检测...')
    
    # 尝试一次性添加所有文件
    try:
        result = subprocess.run(['git', 'add', '.'], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            await send_progress(f'❌ 批量添加失败，切换到单文件检测模式')
            # 如果批量失败，检测失败的具体文件
            for line in result.stderr.split('\n'):
                if 'error:' in line.lower() or 'fatal:' in line.lower():
                    # 尝试从错误信息中提取文件名
                    parts = line.split()
                    for part in parts:
                        if '/' in part or '.' in part:
                            problematic_files.append({
                                'path': part.strip("'\""),
                                'error': '批量添加时失败',
                                'type': 'batch_error'
                            })
                            break
        else:
            await send_progress(f'✅ 批量添加成功，检查提交状态...')
            # 尝试测试提交
            commit_result = subprocess.run(
                ['git', 'commit', '--dry-run', '-m', 'test'], 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            if commit_result.returncode != 0:
                if ('不稳定对象源数据' in commit_result.stderr or 
                    'malformed object' in commit_result.stderr.lower() or
                    'corrupt' in commit_result.stderr.lower()):
                    await send_progress(f'💀 检测到Git对象损坏，需要进一步分析')
                    # 这里可以添加更精细的检测逻辑
                    
    except subprocess.TimeoutExpired:
        await send_progress(f'⏰ 批量检测超时')
        
    diagnostic_report.extend([
        f'📋 快速批量诊断完成:',
        f'• 总文件数: {len(all_files)}',
        f'• 问题文件数: {len(problematic_files)}'
    ])
    
    return len(problematic_files) > 0, '\n'.join(diagnostic_report), problematic_files


async def fix_git_repository(backup_path: str, server_name: str, problematic_files: list, action: str) -> tuple[bool, str]:
    """
    修复Git仓库问题

    Args:
        backup_path: 备份路径
        server_name: 服务器名称
        problematic_files: 问题文件列表
        action: 修复动作 ('delete', 'backup_and_delete', 'skip')

    Returns:
        tuple[bool, str]: (是否成功, 修复报告)
    """
    import subprocess
    import os
    import shutil
    from datetime import datetime

    fix_report = []

    try:
        # 切换到备份目录
        original_cwd = os.getcwd()
        os.chdir(backup_path)

        try:
            fix_report.append(f'🔧 开始修复服务器 {server_name} 的Git仓库')

            if action == 'delete':
                # 直接删除问题文件
                deleted_count = 0
                for file_info in problematic_files:
                    file_path = file_info['path']
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_count += 1
                            fix_report.append(f'🗑️ 已删除: {file_path}')
                        else:
                            fix_report.append(f'⚠️ 文件不存在，跳过: {file_path}')
                    except Exception as e:
                        fix_report.append(f'❌ 删除失败: {file_path} - {str(e)}')

                fix_report.append(f'📊 删除了 {deleted_count} 个问题文件')

            elif action == 'backup_and_delete':
                # 备份后删除问题文件
                current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = os.path.join(backup_path, f'corrupted_files_backup_{current_time}')
                os.makedirs(backup_dir, exist_ok=True)

                backed_up_count = 0
                deleted_count = 0

                for file_info in problematic_files:
                    file_path = file_info['path']
                    try:
                        if os.path.exists(file_path):
                            # 创建备份目录结构
                            backup_file_path = os.path.join(backup_dir, file_path)
                            backup_file_dir = os.path.dirname(backup_file_path)
                            os.makedirs(backup_file_dir, exist_ok=True)

                            # 复制文件到备份目录
                            shutil.copy2(file_path, backup_file_path)
                            backed_up_count += 1

                            # 删除原文件
                            os.remove(file_path)
                            deleted_count += 1
                            fix_report.append(f'📦 已备份并删除: {file_path}')
                        else:
                            fix_report.append(f'⚠️ 文件不存在，跳过: {file_path}')
                    except Exception as e:
                        fix_report.append(f'❌ 备份删除失败: {file_path} - {str(e)}')

                fix_report.append(f'📊 备份了 {backed_up_count} 个文件，删除了 {deleted_count} 个问题文件')
                fix_report.append(f'📁 备份位置: {backup_dir}')

            elif action == 'skip':
                fix_report.append(f'⏭️ 跳过修复，保留所有问题文件')
                return True, '\n'.join(fix_report)

            # 步骤2: 重新初始化Git暂存区
            fix_report.append(f'🔄 重新添加有效文件到Git')
            subprocess.run(['git', 'reset'], capture_output=True)

            # 添加所有剩余文件
            subprocess.run(['git', 'add', '.'], capture_output=True)

            # 检查是否还有问题
            status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
            if status_result.stdout.strip():
                fix_report.append(f'✅ Git仓库已修复，可以正常添加文件')
            else:
                fix_report.append(f'ℹ️ 没有文件需要添加到Git')

            return True, '\n'.join(fix_report)

        finally:
            # 恢复原工作目录
            os.chdir(original_cwd)

    except Exception as e:
        error_msg = f'修复过程出错: {str(e)}'
        fix_report.append(error_msg)
        return False, '\n'.join(fix_report)
