import nonebot
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent

from . import get_context


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
