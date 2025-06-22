from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import Event
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import (
    get_context, permission_required, check_command_enabled,
    get_env_str, get_env_list, get_database, User
)
from baimomcsm_api import common, applications
import os

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
server_backup = on_command('server_backup')
backup_info = on_command('backup_info')
backup_list = on_command('backup_list')
backup_rollback = on_command('backup_rollback')
auto_backup = on_command('auto_backup')
backup_analyze = on_command('backup_analyze')
backup_clean = on_command('backup_clean')
# MCSM 配置 - 从环境变量读取
MCSM_CONFIG = {
    'url': get_env_str('MCSM_URL', 'http://localhost:23333'),
    'apikey': get_env_str('MCSM_APIKEY', ''),
    'daemon_id': get_env_str('MCSM_DAEMON_ID', ''),
    'instances': get_env_list('INSTANCES')
}

# Git 备份配置 - 从环境变量读取
GIT_BACKUP_CONFIG = {
    'enabled': get_env_str('GIT_BACKUP_ENABLED', 'false').lower() == 'true',
    'max_backups': int(get_env_str('GIT_BACKUP_MAX_COUNT', '10')),
    'git_user_name': get_env_str('GIT_BACKUP_USER_NAME', 'MCSM Bot'),
    'git_user_email': get_env_str('GIT_BACKUP_USER_EMAIL', 'bot@mcsm.local'),
    'backup_paths': get_env_list('GIT_BACKUP_PATHS', []),  # 服务器路径映射
    'mcsm_base_path': get_env_str('MCSM_BASE_PATH', '/opt/mcsmanager/daemon/data/InstanceData'),
    'backup_target': get_env_str('MCSM_BACKUP_TARGET', 'full'),  # 'full' 或 'world'
}

# 服务器实例映射 - 从环境变量读取
def load_server_instances() -> dict:
    """从环境变量加载服务器实例配置"""

    default_instances = {}
    for i in MCSM_CONFIG['instances']:
        default_instances[i] = get_env_str(f'MCSM_{i.upper()}_ID')

    print(f'检测到mcsm实例: {default_instances}')
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

def check_git_backup_config() -> bool:
    """检查Git备份配置是否完整"""
    if not GIT_BACKUP_CONFIG['enabled']:
        return False
    
    # 如果配置了具体的备份路径，检查路径配置
    if GIT_BACKUP_CONFIG['backup_paths']:
        return True
    
    # 如果没有配置具体路径，检查是否可以使用动态路径生成
    # 检查是否有服务器实例配置
    if SERVER_INSTANCES:
        return True
    
    # 都没有配置，返回False
    return False

def get_server_backup_path(server_name: str) -> str:
    """获取服务器备份路径"""
    import os
    
    # 从配置中获取服务器路径映射
    backup_paths = GIT_BACKUP_CONFIG['backup_paths']
    
    # 如果配置了具体的服务器路径
    for path_config in backup_paths:
        if isinstance(path_config, str) and ':' in path_config:
            name, path = path_config.split(':', 1)
            if name.strip().lower() == server_name.lower():
                # 规范化路径，处理Windows路径分隔符
                normalized_path = os.path.normpath(path.strip())
                return os.path.abspath(normalized_path)
    
    # 动态生成MCSM标准路径
    try:
        # 获取服务器实例ID
        instance_id = get_instance_id(server_name)
        
        # 获取MCSM基础路径配置
        mcsm_base_path = get_env_str('MCSM_BASE_PATH', '/opt/mcsmanager/daemon/data/InstanceData')
        backup_target = get_env_str('MCSM_BACKUP_TARGET', 'full')  # 'full' 或 'world'
        
        # 构建服务器目录路径
        server_dir = os.path.join(mcsm_base_path, instance_id)
        
        # 根据备份目标选择路径
        if backup_target.lower() == 'world':
            # 只备份存档目录
            backup_path = os.path.join(server_dir, 'World')
        else:
            # 备份整个服务器目录
            backup_path = server_dir
        
        # 规范化路径
        normalized_path = os.path.normpath(backup_path)
        return os.path.abspath(normalized_path)
        
    except ValueError:
        # 如果无法获取实例ID，回退到基础路径模式
        pass
    
    # 如果没有具体配置，使用默认路径
    if backup_paths and isinstance(backup_paths[0], str):
        base_path = backup_paths[0]
        # 构建服务器特定路径
        server_path = os.path.join(base_path, server_name)
        # 规范化路径
        normalized_path = os.path.normpath(server_path)
        return os.path.abspath(normalized_path)
    
    raise ValueError(f'未配置服务器 "{server_name}" 的备份路径，请配置 MCSM_BASE_PATH 或 GIT_BACKUP_PATHS')

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
            for root, dirs, files in os.walk('.'):
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

def get_directory_size(path: str) -> int:
    """
    计算目录大小（字节）
    
    Args:
        path: 目录路径
        
    Returns:
        int: 目录大小（字节）
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    # 文件可能被删除或无法访问，跳过
                    continue
    except (OSError, PermissionError):
        pass
    return total_size

def format_size(size_bytes: int) -> str:
    """
    将字节数格式化为人类可读的大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        str: 格式化的大小字符串
    """
    if size_bytes == 0:
        return '0 B'
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f'{int(size_bytes)} {unit}'
            else:
                return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024.0
    
    return f'{size_bytes:.1f} PB'

async def check_server_permission_async(user: User, server_name: str, group) -> bool:
    """
    检查用户是否有指定服务器的特殊权限
    
    Args:
        user: 用户对象
        server_name: 服务器名称
        group: 群组对象（保留参数以保持接口一致性）
        
    Returns:
        bool: 是否有权限
    """
    try:
        return await user.has_special_permission(server_name)
    except Exception:
        return False

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

# 定时备份数据管理器
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
        try:
            instance_id = get_instance_id(server_name)
            result = applications.get_info(MCSM_CONFIG['url'], instance_id, MCSM_CONFIG['daemon_id'], MCSM_CONFIG['apikey'])
            
            if result.get('status') == 200:
                data = result['data']
                if data['status'] == 3:  # 运行中
                    if 'info' in data:
                        return data['info'].get('currentPlayers', 0)
            return 0
        except Exception:
            return 0
    
    async def silent_backup(self, server_name: str) -> tuple[bool, str]:
        """静默备份（不发送QQ消息）"""
        try:
            # 检查玩家在线状态
            players_online = await self.check_players_online(server_name)
            if players_online == 0:
                return True, f'服务器 {server_name} 没有玩家在线，跳过备份'
            
            # 执行备份
            success, message = await execute_git_backup(server_name, f'定时备份 (在线玩家: {players_online})')
            
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
            
            return success, message
        except Exception as e:
            return False, f'定时备份出错: {str(e)}'

# 全局自动备份管理器实例
auto_backup_manager = AutoBackupManager()

# 定时备份调度器
async def backup_scheduler():
    """定时备份调度器"""
    import asyncio
    from datetime import datetime, timedelta
    import logging
    
    logging.info('自动备份调度器已启动')
    
    while True:
        try:
            # 检查所有启用的服务器
            enabled_servers = auto_backup_manager.get_all_enabled_servers()
            
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
                    success, message = await auto_backup_manager.silent_backup(server_name)
                    logging.info(f'定时备份 {server_name}: {"成功" if success else "失败"} - {message}')
        
        except Exception as e:
            logging.error(f'定时备份调度器出错: {str(e)}')
        
        # 每1分钟检查一次
        await asyncio.sleep(60)

# 启动调度器
import asyncio
import nonebot

@nonebot.get_driver().on_startup
async def start_backup_scheduler():
    """启动时自动启动备份调度器"""
    try:
        if not auto_backup_manager._scheduler_running:
            auto_backup_manager._scheduler_running = True
            auto_backup_manager._scheduler_task = asyncio.create_task(backup_scheduler())
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
    try:
        if auto_backup_manager._scheduler_task:
            auto_backup_manager._scheduler_task.cancel()
            auto_backup_manager._scheduler_running = False
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
        scheduler_status = "✅ 运行中" if auto_backup_manager._scheduler_running else "❌ 已停止"
        message += f'📡 调度器: {scheduler_status}\n\n'
        
        # 显示各服务器状态
        for server_name in SERVER_INSTANCES.keys():
            config = auto_backup_manager.get_server_config(server_name)
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
        
        # 保存配置
        config = auto_backup_manager.get_server_config(server_name)
        config['enabled'] = True
        config['interval_minutes'] = interval_minutes
        auto_backup_manager.set_server_config(server_name, config)
        
        # 确保调度器运行
        if not auto_backup_manager._scheduler_running:
            import asyncio
            auto_backup_manager._scheduler_running = True
            auto_backup_manager._scheduler_task = asyncio.create_task(backup_scheduler())
        
        await auto_backup.send(f'✅ 已启用服务器 {server_name} 的自动备份\n⏰ 备份间隔: {interval_minutes}分钟\n💡 只在有玩家在线时备份，不会发送QQ消息')
    
    elif action == 'off':
        # 禁用自动备份
        config = auto_backup_manager.get_server_config(server_name)
        config['enabled'] = False
        auto_backup_manager.set_server_config(server_name, config)
        
        await auto_backup.send(f'✅ 已禁用服务器 {server_name} 的自动备份')
    
    else:
        await auto_backup.send('❌ 无效操作，请使用 on、off 或 status')

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

async def analyze_single_server(command_handler, server_name: str, backup_path: str):
    """分析单个服务器的备份情况"""
    import subprocess
    import os
    from datetime import datetime, timedelta
    
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
        message += f'• Git历史: {format_size(git_size)} ({git_size/total_size*100:.1f}%)\n'
        message += f'• 工作目录: {format_size(working_size)} ({working_size/total_size*100:.1f}%)\n\n'
        
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

bind = on_command('bind')
add_info('bind', '绑定此群消息到服务器')

@bind.handle()
@check_command_enabled('bind')
async def bind_handler(event: Event):
    user, args, group = get_context(event)

    server_name = args[0]

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await bind.finish(f'❌ 权限不足，需要 "{server_name}" 服务器权限')

    db = get_database('chat_bind').get_db()

    # 查绑定服务器列表并修改

    doc = db.find_one({'groupid': group.id})
    print(doc['servers']) if doc else ''
    if not doc:
        db.insert_one({'groupid': group.id, 'servers': [args[0]]})
        await bind.send(f'已绑定本群到服务器{args[0]}')
    elif args[0] not in doc['servers']:
        s = doc['servers']
        s.append(args[0])
        db.update_one({'groupid': group.id}, {'$set': {'servers': s}})
        await bind.send(f'已绑定本群到服务器{args[0]}')
    else:
        s = doc['servers']
        s.remove(args[0])
        db.update_one({'groupid': group.id}, {'$set': {'servers': s}})
        await bind.send(f'已取消绑定本群到服务器{args[0]}')

@on_message().handle()
def send_qq_to_server(event: Event):
    user, args, group = get_context(event)
    db = get_database('chat_bind').get_db()

    # 查绑定服务器列表
    doc = db.find_one({'groupid': group.id})

    if not doc:
        return

    # 发送服务器消息
    try:
        for server_name in doc['servers']:
            # 获取服务器实例ID和备份路径
            instance_id = get_instance_id(server_name)

            applications.send_command(
                MCSM_CONFIG['url'],
                instance_id,
                MCSM_CONFIG['daemon_id'],
                MCSM_CONFIG['apikey'],
                f'say qq[{user.name}/{user.id}]: {event.get_plaintext()}'
            )
    except:
        pass