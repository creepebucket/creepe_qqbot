import asyncio

from nonebot import Bot
from nonebot.adapters.onebot.v11 import MessageSegment
from . import database as db
import nonebot, nonebot.adapters.onebot.v11

# 数据库
permissions = db.get_database('permissions').collection
subscribers = db.get_database('subscribers').collection


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

    async def send(self, msg: MessageSegment):
        """
         发送私聊消息
         :param msg: 要发送的消息
         """
        await nonebot.get_bot().send_private_msg(user_id=self.id, message=msg)
