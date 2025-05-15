from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageEvent, GroupMessageEvent
from nonebot.matcher import Matcher

from redstone_daily.plugins.utils import permission_required, get_context, Group

enable_command = on_command("enable_command", aliases={"启用指令"})
disable_command = on_command("disable_command", aliases={"禁用指令"})


def _validate_group_id(event: MessageEvent, input_group: str = None) -> int:
    """验证并获取目标群号"""
    # 优先使用输入参数
    if input_group and input_group.isdigit():
        return int(input_group)

    # 自动获取当前群号（仅群消息有效）
    if isinstance(event, GroupMessageEvent):
        return event.group_id

    # 私聊必须指定群号
    raise ValueError("私聊使用时必须指定群号参数")


@enable_command.handle()
@permission_required(3)
async def handle_enable_command(event: MessageEvent):
    # 获取上下文
    user, cmd_args, current_group = get_context(event)

    # 解析参数
    params = cmd_args
    if len(params) < 1:
        await enable_command.finish("参数格式：/enable_command <指令名> [群号]")

    try:
        command = params[0]
        target_group = _validate_group_id(event, params[1] if len(params) >= 2 else None)
    except ValueError as e:
        await enable_command.finish(str(e))

    # 权限验证（操作者需在目标群有权限）
    operator_permission = await user.get_permission(Group(target_group))
    if operator_permission < 3:
        await enable_command.finish(f"你在群{target_group}没有操作权限")

    # 执行操作
    target_group_obj = Group(target_group)
    await target_group_obj.add_command(command)
    await enable_command.send(f"已在群 {target_group} 启用指令 {command}")


@disable_command.handle()
@permission_required(3)
async def handle_disable_command(event: MessageEvent,):
    # 获取上下文
    user, cmd_args, current_group = get_context(event)

    # 解析参数
    params = cmd_args
    if len(params) < 1:
        await disable_command.finish("参数格式：/disable_command <指令名> [群号]")

    try:
        command = params[0]
        target_group = _validate_group_id(event, params[1] if len(params) >= 2 else None)
    except ValueError as e:
        await disable_command.finish(str(e))

    # 权限验证
    operator_permission = await user.get_permission(Group(target_group))
    if operator_permission < 3:
        await disable_command.finish(f"你在群{target_group}没有操作权限")

    # 执行操作
    target_group_obj = Group(target_group)
    await target_group_obj.remove_command(command)
    await disable_command.send(f"已在群 {target_group} 禁用指令 {command}")