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
import os

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
add_info('server_backup', 'Git备份服务器存档\n需要mc_server特殊权限\n用法: /server_backup <服务器名> [备份描述]')
add_info('backup_info', '查看备份配置信息\n需要mc_server特殊权限\n用法: /backup_info [服务器名]')

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

# MCSM 配置 - 从环境变量读取
MCSM_CONFIG = {
    'url': get_env_str('MCSM_URL', 'http://localhost:23333'),
    'apikey': get_env_str('MCSM_APIKEY', ''),
    'daemon_id': get_env_str('MCSM_DAEMON_ID', ''),
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
            backup_path = os.path.join(server_dir, 'world')
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
        time.sleep(3)
        
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
            
            return True, f'备份完成: {commit_message}'
            
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
        
        # 如果提交数量超过限制，进行 rebase 合并
        if commit_count > max_backups:
            # 计算需要保留的提交数
            commits_to_keep = max_backups - 1  # 保留最近的几个提交
            
            # 获取要保留的最老提交的 hash
            oldest_to_keep_result = subprocess.run(
                ['git', 'rev-list', '--reverse', 'HEAD', f'--max-count={commits_to_keep}'],
                capture_output=True,
                text=True,
                cwd=backup_path
            )
            
            if oldest_to_keep_result.stdout.strip():
                oldest_hash = oldest_to_keep_result.stdout.strip().split('\n')[0]
                
                # 使用 rebase 将旧提交合并为一个
                # 首先创建一个临时分支
                subprocess.run(['git', 'branch', 'temp-backup'], cwd=backup_path, capture_output=True)
                
                try:
                    # 重置到最老的保留提交
                    subprocess.run(['git', 'reset', '--soft', f'{oldest_hash}~1'], cwd=backup_path, check=True)
                    
                    # 创建一个合并提交
                    subprocess.run([
                        'git', 'commit', '-m', f'[{os.path.basename(backup_path)}] 历史备份合并 - 保留最近{max_backups}个备份'
                    ], cwd=backup_path, check=True, capture_output=True)
                    
                    # 删除临时分支
                    subprocess.run(['git', 'branch', '-D', 'temp-backup'], cwd=backup_path, capture_output=True)
                    
                except subprocess.CalledProcessError:
                    # 如果 rebase 失败，恢复到临时分支
                    subprocess.run(['git', 'reset', '--hard', 'temp-backup'], cwd=backup_path, capture_output=True)
                    subprocess.run(['git', 'branch', '-D', 'temp-backup'], cwd=backup_path, capture_output=True)
        
    except (subprocess.CalledProcessError, ValueError, IndexError):
        # 如果历史管理失败，不影响备份主流程
        pass

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

@server_backup.handle()
@check_command_enabled('server_backup')
@permission_required('mc_server')
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
@permission_required('mc_server')
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