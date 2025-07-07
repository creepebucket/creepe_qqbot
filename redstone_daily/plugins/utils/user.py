import asyncio
from datetime import datetime

from nonebot import Bot
from nonebot.adapters.onebot.v11 import MessageSegment
from . import database as db
import nonebot, nonebot.adapters.onebot.v11

# 数据库
permissions = db.get_database('permissions').collection
subscribers = db.get_database('subscribers').collection
special_permissions = db.get_database('special_permissions').collection


class User:
    def __init__(self, id: int, nickname: str = ""):
        self.id = id
        self._nickname = nickname

    @property
    def name(self) -> str:
        return self._nickname

    @property
    async def permission(self) -> int:
        """
        获取用户权限
        """
        return await self.get_permission()

    async def get_permission(self, group) -> int:
        """
        获取用户权限（同步安全版）
        :param group: 群对象
        """
        # 先查询数据库
        permission_doc = permissions.find_one({'id': self.id, 'group': group.id})

        if permission_doc is not None:
            return permission_doc['permission']

        # 如果数据库无记录，进行群角色检测
        bot: Bot = nonebot.get_bot()

        try:
            member_info = await bot.get_group_member_info(
                    group_id=group.id,
                    user_id=self.id
                )
        except (TimeoutError, asyncio.TimeoutError):
            # 处理超时情况
            return 0
        except Exception as e:
            # 处理其他异常
            print(f"获取成员信息失败: {str(e)}")
            return 0

        role = member_info.get("role", "member")

        # 根据角色设置权限
        if role == "owner":
            permission = 5
        elif role == "admin":
            permission = 3
        else:
            permission = 0

        # 将权限保存到数据库
        self.set_permission(permission, group)
        return permission

    def set_permission(self, permission: int, group):
        """
        设置用户权限
        :param permission: 权限值
        :param group: 群号
        """

        if type(permission) != int:  # 确保权限值为整数
            raise TypeError('权限值必须为整数')

        permissions.update_one({'id': self.id, 'group': group.id}, {'$set': {'permission': permission}}, upsert=True)

    async def has_special_permission(self, permission_name: str) -> bool:
        """
        检查用户是否拥有特殊权限
        
        Args:
            permission_name: 特殊权限名称
            
        Returns:
            bool: 是否拥有该特殊权限
        """
        # 查询特殊权限数据库
        special_perm_doc = special_permissions.find_one({
            'user_id': self.id, 
            'permission_name': permission_name,
            'enabled': True
        })
        
        return special_perm_doc is not None
    
    def set_special_permission(self, permission_name: str, enabled: bool = True):
        """
        设置用户的特殊权限
        
        Args:
            permission_name: 特殊权限名称
            enabled: 是否启用该权限
        """
        if enabled:
            # 启用特殊权限
            special_permissions.update_one(
                {'user_id': self.id, 'permission_name': permission_name},
                {'$set': {'enabled': True, 'updated_at': datetime.now()}},
                upsert=True
            )
        else:
            # 禁用特殊权限
            special_permissions.update_one(
                {'user_id': self.id, 'permission_name': permission_name},
                {'$set': {'enabled': False, 'updated_at': datetime.now()}},
                upsert=True
            )
    
    def get_special_permissions(self) -> list:
        """
        获取用户的所有特殊权限
        
        Returns:
            list: 特殊权限名称列表
        """
        special_perms = special_permissions.find({
            'user_id': self.id,
            'enabled': True
        })
        
        return [perm['permission_name'] for perm in special_perms]

    async def send(self, msg: MessageSegment):
        """
         发送私聊消息
         :param msg: 要发送的消息
         """
        await nonebot.get_bot().send_private_msg(user_id=self.id, message=msg)


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
