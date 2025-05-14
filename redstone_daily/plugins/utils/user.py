import requests
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
    def permission(self) -> int:
        """
        获取用户权限
        """
        return self.get_permission()

    def get_permission(self, group) -> int:
        """
        获取用户权限
        :param group: 群号
        """

        permission_doc = permissions.find_one({'id': self.id, 'group': group.id})  # 获取用户权限

        if permission_doc is None:  # 如果用户没有权限，则默认为0
            return 0

        return permission_doc['permission']  # 返回用户权限

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
