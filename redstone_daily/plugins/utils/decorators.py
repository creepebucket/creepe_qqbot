import json

import nonebot
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent

from .group import Group
from .user import User


def get_context(event: Event):
    """
    获取事件的上下文信息(发送者的utils.user.User对象, 指令参数, 群聊的utils.group.Group对象(如果是群聊消息))
    :param event: 事件对象
    :return: 事件的上下文信息(格式为[user, args, group])
    """

    def get_args(event: Event):
        """
        获取指令参数
        :param event: 事件对象
        :return: 指令参数列表
        """
        args = []
        json_data = json.loads(event.json())
        for msg in json_data.get('original_message', ''):  # 遍历消息列表
            if msg['type'] == 'text':  # 找到文本消息
                for i in msg['data']['text'].split(' '):  # 遍历文本

                    if i.startswith('/'):  # 忽略命令
                        continue

                    args.append(i)
            if msg['type'] == 'at':  # 找到@消息
                args.append(msg['data']['qq'])

        for i in args:  # 去除空白字符
            if i == '':
                args.remove(i)

        return args

    if isinstance(event, GroupMessageEvent):
        group = Group(event.group_id)
    else:
        group = None

    user = User(event.user_id)
    args = get_args(event)

    return [user, args, group]


def permission_required(perm: int):
    """
    权限检查装饰器
    :param perm: 权限等级
    :return: 装饰器
    """

    def decorator(func):
        async def wrapper(event: Event):
            sender, arg, group = get_context(event)
            if await sender.get_permission(group) >= perm:  # 判断用户权限是否满足要求
                return await func(event)  # 执行函数
            else:  # 权限不足
                bot = nonebot.get_bot()
                if isinstance(event, GroupMessageEvent):
                    await bot.send_group_msg(group_id=event.group_id,
                                             message=f'你需要{perm}级权限才能执行此操作')  # 发送权限不足消息
                else:
                    await sender.send(f'你需要{perm}级权限才能执行此操作')

        return wrapper

    return decorator


def check_command_enabled(command: str, send_disabled_message: bool = True):
    """
    指令启用检查装饰器
    :param command: 指令名称
    :param send_disabled_message: 是否发送指令禁用提示
    :return: 装饰器
    """

    def decorator(func):
        async def wrapper(event: Event):
            sender, arg, group = get_context(event)

            # 仅群消息需要检查指令状态
            if isinstance(event, GroupMessageEvent):
                if not group.is_command_enabled(command):
                    if not send_disabled_message:
                        return

                    bot = nonebot.get_bot()
                    await bot.send_group_msg(
                        group_id=group.id,
                        message=f'指令 {command} 在此群组已被禁用'
                    )
                    return  # 阻止执行被装饰函数

            # 非群消息或指令已启用时正常执行
            return await func(event)

        return wrapper

    return decorator
