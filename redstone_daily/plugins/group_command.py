from typing import Dict, List

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, GroupMessageEvent, MessageSegment

from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import permission_required, get_context, Group

enable_command = on_command("enable_command", aliases={"启用指令"})
add_info('enable_command', '在群里启用某指令\n需求权限3 参数:\n/enable_command <command> [groupid]')
disable_command = on_command("disable_command", aliases={"禁用指令"})
add_info('disable_command', '在群里禁用某指令\n需求权限3 参数:\n/enable_command <command> [groupid]')


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


# 预设指令分类（可扩展）
COMMAND_PRESETS: Dict[str, List[str]] = {
    "娱乐": ["sing", "joke", "game", "music"],
    "管理": ["ban", "kick", "mute", "warn"],
    "工具": ["weather", "translate", "calc"],
    "全部": []  # 特殊分类，表示所有指令
}

preset_command = on_command("preset_command", aliases={"预设指令"})
add_info('preset_command',
         '批量管理指令预设\n需求权限3 参数:\n/preset_command <enable/disable> <预设名称> [群号]')


async def get_all_commands() -> List[str]:
    """获取所有指令列表（需要根据实际实现补充）"""
    cmds = []
    for k, v in COMMAND_PRESETS.items():
        cmds += v

    return cmds


@preset_command.handle()
@permission_required(3)
async def handle_preset_command(event: MessageEvent):
    user, cmd_args, current_group = get_context(event)

    if len(cmd_args) < 2:
        await preset_command.finish("参数格式：/preset_command <enable/disable> <预设名称> [群号]")

    operation = cmd_args[0].lower()
    preset_name = cmd_args[1]
    group_arg = cmd_args[2] if len(cmd_args) >= 3 else None

    try:
        target_group = _validate_group_id(event, group_arg)
    except ValueError as e:
        await preset_command.finish(str(e))

    # 权限验证
    operator_permission = await user.get_permission(Group(target_group))
    if operator_permission < 3:
        await preset_command.finish(f"你在群 {target_group} 没有操作权限")

    # 获取目标指令列表
    if preset_name == "全部":
        commands = await get_all_commands()
    elif preset_name in COMMAND_PRESETS:
        commands = COMMAND_PRESETS[preset_name]
    else:
        available_presets = "/".join(COMMAND_PRESETS.keys())
        await preset_command.finish(
            f"无效预设，可用预设：{available_presets}\n包含指令：{COMMAND_PRESETS.get(preset_name, [])}")

    # 执行批量操作
    target_group_obj = Group(target_group)
    results = []
    for cmd in commands:
        try:
            if operation == "enable":
                await target_group_obj.add_command(cmd)
                results.append(f"+{cmd}")
            elif operation == "disable":
                await target_group_obj.remove_command(cmd)
                results.append(f"-{cmd}")
            else:
                await preset_command.finish("无效操作，请使用 enable 或 disable")
        except Exception as e:
            results.append(f"{cmd}❌{str(e)}")

    # 格式化结果
    result_msg = "\n".join(results)
    await preset_command.send(
        f"在群 {target_group} 执行 {preset_name} 预设({operation})：\n"
        f"操作指令数：{len(commands)}\n"
        f"操作结果：\n{result_msg}"
    )


list_presets = on_command("list_presets", aliases={"查看预设"})
add_info('list_presets', '查看所有可用指令预设\n参数: /list_presets')


@list_presets.handle()
async def handle_list_presets(event: MessageEvent):
    # 构建预设说明
    presets_info = []
    for preset_name, commands in COMMAND_PRESETS.items():
        # 显示前3个指令+...（避免消息过长）
        preview = ", ".join(commands[:3])
        if len(commands) > 3:
            preview += f" 等{len(commands)}个指令"
        presets_info.append(f"• {preset_name}：{preview}")

    # 添加特殊分类说明
    presets_info.append("\n【特殊分类】\n• 全部：所有可用指令")

    # 格式化为合并消息
    message = MessageSegment.text("可用指令预设：\n")
    message += MessageSegment.text("\n".join(presets_info))

    # 添加使用提示
    message += MessageSegment.text("\n\n使用示例：\n/预设指令 enable 娱乐\n/预设指令 disable 管理 123456")

    await list_presets.finish(message)