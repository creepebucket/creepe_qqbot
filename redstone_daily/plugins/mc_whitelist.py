"""
MC服务器白名单管理插件
作者: AI Assistant
版本: 1.0.0
功能: 管理MC服务器的白名单
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import (
    get_context, 
    permission_required, 
    check_command_enabled,
    get_file_manager,
    FileManagerError
)
import logging

logger = logging.getLogger(__name__)

# 注册帮助信息
add_info('whitelist_add', 'MC服务器白名单管理 - 添加玩家\n需要mc_server特殊权限\n用法: /whitelist_add <服务器名> <玩家名>')
add_info('whitelist_remove', 'MC服务器白名单管理 - 移除玩家\n需要mc_server特殊权限\n用法: /whitelist_remove <服务器名> <玩家名>')
add_info('whitelist_list', 'MC服务器白名单管理 - 查看白名单\n需要mc_server特殊权限\n用法: /whitelist_list <服务器名>')

# 命令处理器
whitelist_add = on_command('whitelist_add')
whitelist_remove = on_command('whitelist_remove')
whitelist_list = on_command('whitelist_list')


class MCWhitelistManager:
    """MC服务器白名单管理器"""
    
    def __init__(self):
        # 使用文件管理器，设置MCSManager基础路径
        self.file_manager = get_file_manager('/opt/mcsmanager')
        
        # 服务器配置映射：服务器名 -> whitelist.json文件路径
        # 基于MCSManager的实例ID结构
        self.server_configs = {
            'slimefun': 'daemon/data/InstanceData/f645c80e421f4fea8997ba6eb53644b7/whitelist.json',
            'survival': 'daemon/data/InstanceData/survival-instance-id/whitelist.json',
            'creative': 'daemon/data/InstanceData/creative-instance-id/whitelist.json',
            'skyblock': 'daemon/data/InstanceData/skyblock-instance-id/whitelist.json',
            'main': 'daemon/data/InstanceData/main-instance-id/whitelist.json',
            'test': 'daemon/data/InstanceData/test-instance-id/whitelist.json'
        }
    
    def get_whitelist_path(self, server_name: str) -> str:
        """
        根据服务器名获取白名单文件路径
        
        Args:
            server_name: 服务器名称
            
        Returns:
            str: 白名单文件路径
            
        Raises:
            ValueError: 服务器名不存在时
        """
        if server_name.lower() not in self.server_configs:
            available_servers = ', '.join(self.server_configs.keys())
            raise ValueError(f'服务器名 "{server_name}" 不存在。可用服务器: {available_servers}')
        
        return self.server_configs[server_name.lower()]
    
    def load_whitelist(self, server_name: str) -> list:
        """
        加载服务器白名单
        
        Args:
            server_name: 服务器名称
            
        Returns:
            list: 白名单列表
        """
        try:
            whitelist_path = self.get_whitelist_path(server_name)
            
            # 如果文件不存在，创建空白名单
            if not self.file_manager.file_exists(whitelist_path):
                logger.info(f'白名单文件不存在，创建新文件: {whitelist_path}')
                self.file_manager.write_json(whitelist_path, [], backup=False)
                return []
            
            # 读取白名单文件
            whitelist_data = self.file_manager.read_json(whitelist_path)
            
            # 确保返回的是列表格式
            if not isinstance(whitelist_data, list):
                logger.warning(f'白名单文件格式错误，重置为空列表: {whitelist_path}')
                return []
            
            return whitelist_data
            
        except FileManagerError as e:
            logger.error(f'加载白名单失败: {str(e)}')
            raise
    
    def save_whitelist(self, server_name: str, whitelist: list) -> bool:
        """
        保存服务器白名单
        
        Args:
            server_name: 服务器名称
            whitelist: 白名单列表
            
        Returns:
            bool: 是否保存成功
        """
        try:
            whitelist_path = self.get_whitelist_path(server_name)
            self.file_manager.write_json(whitelist_path, whitelist, backup=True)
            logger.info(f'白名单保存成功: {whitelist_path}')
            return True
            
        except FileManagerError as e:
            logger.error(f'保存白名单失败: {str(e)}')
            return False
    
    def add_player(self, server_name: str, player_name: str) -> bool:
        """
        添加玩家到白名单
        
        Args:
            server_name: 服务器名称
            player_name: 玩家名称
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 加载当前白名单
            whitelist = self.load_whitelist(server_name)
            
            # 检查玩家是否已在白名单中
            for entry in whitelist:
                if entry.get('name', '').lower() == player_name.lower():
                    return False  # 玩家已存在
            
            # 添加新玩家
            whitelist.append({'name': player_name})
            
            # 保存白名单
            return self.save_whitelist(server_name, whitelist)
            
        except Exception as e:
            logger.error(f'添加玩家失败: {str(e)}')
            return False
    
    def remove_player(self, server_name: str, player_name: str) -> bool:
        """
        从白名单中移除玩家
        
        Args:
            server_name: 服务器名称
            player_name: 玩家名称
            
        Returns:
            bool: 是否移除成功
        """
        try:
            # 加载当前白名单
            whitelist = self.load_whitelist(server_name)
            
            # 查找并移除玩家
            original_length = len(whitelist)
            whitelist = [entry for entry in whitelist 
                        if entry.get('name', '').lower() != player_name.lower()]
            
            # 检查是否找到并移除了玩家
            if len(whitelist) == original_length:
                return False  # 玩家不在白名单中
            
            # 保存白名单
            return self.save_whitelist(server_name, whitelist)
            
        except Exception as e:
            logger.error(f'移除玩家失败: {str(e)}')
            return False
    
    def get_player_list(self, server_name: str) -> list:
        """
        获取服务器白名单玩家列表
        
        Args:
            server_name: 服务器名称
            
        Returns:
            list: 玩家名称列表
        """
        try:
            whitelist = self.load_whitelist(server_name)
            return [entry.get('name', '') for entry in whitelist if entry.get('name')]
            
        except Exception as e:
            logger.error(f'获取玩家列表失败: {str(e)}')
            return []


# 全局白名单管理器实例
whitelist_manager = MCWhitelistManager()


@whitelist_add.handle()
@check_command_enabled('whitelist_add')
@permission_required('mc_server')
async def handle_whitelist_add(event: Event):
    """
    添加玩家到MC服务器白名单
    
    Args:
        event: NoneBot事件对象
    """
    try:
        user, args, group = get_context(event)
        
        # 参数验证
        if len(args) != 2:
            await whitelist_add.send('❌ 参数错误\n用法: /whitelist_add <服务器名> <玩家名>')
            return
        
        server_name, player_name = args
        
        # 验证玩家名格式（MC玩家名规则：3-16字符，只允许字母数字下划线）
        if not (3 <= len(player_name) <= 16 and player_name.replace('_', '').isalnum()):
            await whitelist_add.send('❌ 玩家名格式错误\nMC玩家名必须是3-16个字符，只能包含字母、数字和下划线')
            return
        
        # 添加玩家到白名单
        success = whitelist_manager.add_player(server_name, player_name)
        
        if success:
            await whitelist_add.send(f'✅ 成功将玩家 {player_name} 添加到服务器 {server_name} 的白名单')
            logger.info(f'用户 {user.id} 添加玩家 {player_name} 到服务器 {server_name} 白名单')
        else:
            # 检查是否是玩家已存在的问题
            current_players = whitelist_manager.get_player_list(server_name)
            if player_name.lower() in [p.lower() for p in current_players]:
                await whitelist_add.send(f'⚠️ 玩家 {player_name} 已在服务器 {server_name} 的白名单中')
            else:
                await whitelist_add.send(f'❌ 添加失败，请检查服务器名称或联系管理员')
        
    except ValueError as e:
        await whitelist_add.send(f'❌ {str(e)}')
    except Exception as e:
        logger.error(f'添加白名单错误: {str(e)}', exc_info=True)
        await whitelist_add.send('❌ 系统错误，请稍后重试')


@whitelist_remove.handle()
@check_command_enabled('whitelist_remove')
@permission_required('mc_server')
async def handle_whitelist_remove(event: Event):
    """
    从MC服务器白名单中移除玩家
    
    Args:
        event: NoneBot事件对象
    """
    try:
        user, args, group = get_context(event)
        
        # 参数验证
        if len(args) != 2:
            await whitelist_remove.send('❌ 参数错误\n用法: /whitelist_remove <服务器名> <玩家名>')
            return
        
        server_name, player_name = args
        
        # 移除玩家
        success = whitelist_manager.remove_player(server_name, player_name)
        
        if success:
            await whitelist_remove.send(f'✅ 成功将玩家 {player_name} 从服务器 {server_name} 的白名单中移除')
            logger.info(f'用户 {user.id} 从服务器 {server_name} 白名单移除玩家 {player_name}')
        else:
            await whitelist_remove.send(f'⚠️ 玩家 {player_name} 不在服务器 {server_name} 的白名单中')
        
    except ValueError as e:
        await whitelist_remove.send(f'❌ {str(e)}')
    except Exception as e:
        logger.error(f'移除白名单错误: {str(e)}', exc_info=True)
        await whitelist_remove.send('❌ 系统错误，请稍后重试')


@whitelist_list.handle()
@check_command_enabled('whitelist_list')
@permission_required('mc_server')
async def handle_whitelist_list(event: Event):
    """
    查看MC服务器白名单
    
    Args:
        event: NoneBot事件对象
    """
    try:
        user, args, group = get_context(event)
        
        # 参数验证
        if len(args) != 1:
            await whitelist_list.send('❌ 参数错误\n用法: /whitelist_list <服务器名>')
            return
        
        server_name = args[0]
        
        # 获取白名单
        players = whitelist_manager.get_player_list(server_name)
        
        if not players:
            await whitelist_list.send(f'📝 服务器 {server_name} 的白名单为空')
        else:
            players_str = '\n'.join([f'• {player}' for player in sorted(players)])
            message = f'📝 服务器 {server_name} 的白名单 ({len(players)} 人):\n{players_str}'
            await whitelist_list.send(message)
        
    except ValueError as e:
        await whitelist_list.send(f'❌ {str(e)}')
    except Exception as e:
        logger.error(f'查看白名单错误: {str(e)}', exc_info=True)
        await whitelist_list.send('❌ 系统错误，请稍后重试') 