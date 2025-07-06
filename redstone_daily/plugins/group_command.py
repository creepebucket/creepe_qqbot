from typing import Dict, List

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, MessageSegment

from redstone_daily.plugins.base.helper import add_info
from redstone_daily.plugins.utils import permission_required, get_context, Group, User

enable_command = on_command('enable_command', aliases={'启用指令'})
add_info('enable_command', '在群里启用某指令\n需求权限3 参数:\n/enable_command <command> [groupid]')
disable_command = on_command('disable_command', aliases={'禁用指令'})
add_info('disable_command', '在群里禁用某指令\n需求权限3 参数:\n/enable_command <command> [groupid]')


# 预设指令分类（可扩展）
COMMAND_PRESETS: Dict[str, List[str]] = {
    # 示例: '娱乐': ['sing', 'joke', 'game', 'music'],
    '娱乐': ['fish', '速算', '求解速算'],
    '可能打扰聊天的功能': ['keyword'],
    '验证码': ['turing'],
    'mc管理': [
        'whitelist', 'server_command', 'players', 'player_list',
        'mcsm_status', 'server_list', 'server_info', 'server_status',
        'server_start', 'server_stop', 'server_restart', 'server_kill'
    ],
    'mc备份': [
        'server_backup', 'backup_info', 'backup_list', 'backup_rollback', 'auto_backup', 'backup_analyze', 'backup_clean'
    ],
}

def _validate_group_id(event: MessageEvent, input_group: str | None = None) -> int:
    '''验证并获取目标群号'''
    # 优先使用输入参数
    if input_group and input_group.isdigit():
        return int(input_group)

    # 自动获取当前群号（仅群消息有效）
    if isinstance(event, GroupMessageEvent):
        return event.group_id

    # 私聊必须指定群号
    raise ValueError('私聊使用时必须指定群号参数')


@enable_command.handle()
@permission_required(3)
async def handle_enable_command(event: MessageEvent):
    # 获取上下文
    user, cmd_args, current_group = get_context(event)

    # 解析参数
    params = cmd_args
    if len(params) < 1:
        await enable_command.finish('参数格式：/enable_command <指令名> [群号]')

    try:
        command = params[0]
        target_group = _validate_group_id(event, params[1] if len(params) >= 2 else None)
    except ValueError as e:
        await enable_command.finish(str(e))

    # 权限验证（操作者需在目标群有权限）
    operator_permission = await user.get_permission(Group(target_group))
    if operator_permission < 3:
        await enable_command.finish(f'你在群{target_group}没有操作权限')

    # 执行操作
    target_group_obj = Group(target_group)
    await target_group_obj.add_command(command)
    await enable_command.send(f'已在群 {target_group} 启用指令 {command}')


@disable_command.handle()
@permission_required(3)
async def handle_disable_command(event: MessageEvent,):
    # 获取上下文
    user, cmd_args, current_group = get_context(event)

    # 解析参数
    params = cmd_args
    if len(params) < 1:
        await disable_command.finish('参数格式：/disable_command <指令名> [群号]')

    try:
        command = params[0]
        target_group = _validate_group_id(event, params[1] if len(params) >= 2 else None)
    except ValueError as e:
        await disable_command.finish(str(e))

    # 权限验证
    operator_permission = await user.get_permission(Group(target_group))
    if operator_permission < 3:
        await disable_command.finish(f'你在群{target_group}没有操作权限')

    # 执行操作
    target_group_obj = Group(target_group)
    await target_group_obj.remove_command(command)
    await disable_command.send(f'已在群 {target_group} 禁用指令 {command}')


preset_command = on_command('preset_command', aliases={'预设指令'})
add_info('preset_command',
         '批量管理指令预设\n需求权限3 参数:\n/preset_command <enable/disable> <预设名称> [群号]')


async def get_all_commands() -> List[str]:
    '''获取所有指令列表（需要根据实际实现补充）'''
    cmds = []
    for k, v in COMMAND_PRESETS.items():
        cmds += v

    return cmds


@preset_command.handle()
@permission_required(3)
async def handle_preset_command(event: MessageEvent):
    user, cmd_args, current_group = get_context(event)

    if len(cmd_args) < 2:
        await preset_command.finish('参数格式：/preset_command <enable/disable> <预设名称> [群号]')

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
        await preset_command.finish(f'你在群 {target_group} 没有操作权限')

    # 获取目标指令列表
    if preset_name == '全部':
        commands = await get_all_commands()
    elif preset_name in COMMAND_PRESETS:
        commands = COMMAND_PRESETS[preset_name]
    else:
        available_presets = '/'.join(COMMAND_PRESETS.keys())
        await preset_command.finish(
            f'无效预设，可用预设：{available_presets}\n包含指令：{COMMAND_PRESETS.get(preset_name, [])}')

    # 执行批量操作
    target_group_obj = Group(target_group)
    results = []
    for cmd in commands:
        try:
            if operation == 'enable':
                await target_group_obj.add_command(cmd)
                results.append(f'+{cmd}')
            elif operation == 'disable':
                await target_group_obj.remove_command(cmd)
                results.append(f'-{cmd}')
            else:
                await preset_command.finish('无效操作，请使用 enable 或 disable')
        except Exception as e:
            results.append(f'{cmd}❌{str(e)}')

    # 格式化结果
    result_msg = '\n'.join(results)
    await preset_command.send(
        f'在群 {target_group} 执行 {preset_name} 预设({operation})：\n'
        f'操作指令数：{len(commands)}\n'
        f'操作结果：\n{result_msg}'
    )


list_presets = on_command('list_presets', aliases={'查看预设'})
add_info('list_presets', '查看所有可用指令预设\n参数: /list_presets')


@list_presets.handle()
async def handle_list_presets(event: MessageEvent):
    # 构建预设说明
    presets_info = []
    for preset_name, commands in COMMAND_PRESETS.items():
        # 显示前3个指令+...（避免消息过长）
        preview = ', '.join(commands[:3])
        if len(commands) > 3:
            preview += f' 等{len(commands)}个指令'
        presets_info.append(f'• {preset_name}：{preview}')

    # 添加特殊分类说明
    presets_info.append('\n【特殊分类】\n• 全部：所有可用指令')

    # 格式化为合并消息
    message = MessageSegment.text('可用指令预设：\n')
    message += MessageSegment.text('\n'.join(presets_info))

    # 添加使用提示
    message += MessageSegment.text('\n\n使用示例：\n/预设指令 enable 娱乐\n/预设指令 disable 管理 123456')

    await list_presets.finish(message)

# 新增群管理指令
mute = on_command('mute', aliases={'禁言'})
add_info('mute', '禁言群成员\n需求权限2 参数:\n/mute @用户 <分钟> [理由]')
unmute = on_command('unmute', aliases={'解禁'})
add_info('unmute', '解除禁言\n需求权限2 参数:\n/unmute @用户')
set_nick = on_command('set_nick', aliases={'更改昵称'})
add_info('set_nick', '修改群成员昵称\n需求权限1 参数:\n/set_nick @用户 <新昵称>')
kick = on_command('kick', aliases={'踢人'})
add_info('kick', '踢出群成员\n需求权限4 参数:\n/kick @用户 [理由]')
block = on_command('block', aliases={'拉黑'})
add_info('block', '拉黑用户\n需求权限5 参数:\n/block @用户 [理由]')

@mute.handle()
@permission_required(2)
async def handle_mute(event: GroupMessageEvent):
    user, cmd_args, group = get_context(event)
    
    if len(cmd_args) < 1:
        await mute.finish('参数格式：/mute @用户 分钟 [理由]')
    
    try:
        target_id = int(cmd_args[0])
        minutes = int(cmd_args[1])
        reason = ' '.join(cmd_args[2:]) if len(cmd_args) > 2 else None
        target_user = User(target_id)
        
        await group.mute(target_user, minutes*60)
        msg = f'已禁言用户 {target_id} {minutes}分钟'
        if reason:
            msg += f'，理由：{reason}'
        await mute.send(msg)
    except Exception as e:
        await mute.send(f'禁言失败：{str(e)}')
        raise e

@unmute.handle()
@permission_required(2)
async def handle_unmute(event: GroupMessageEvent):
    user, cmd_args, group = get_context(event)
    
    if not cmd_args:
        await unmute.finish('参数格式：/unmute @用户')
    
    try:
        target_id = int(cmd_args[0])
        target_user = User(target_id)
        
        await group.unmute(target_user)
        await unmute.send(f'已解除用户 {target_id} 的禁言')
    except Exception as e:
        await unmute.send(f'解禁失败：{str(e)}')
        raise e

@set_nick.handle()
@permission_required(1)
async def handle_set_nick(event: GroupMessageEvent):
    user, cmd_args, group = get_context(event)

    if len(cmd_args) < 2:
        await set_nick.finish('参数格式：/set_nick @用户 新昵称')
    
    try:
        target_id = int(cmd_args[0])
        new_nick = ' '.join(cmd_args[1:])
        target_user = User(target_id)
        
        await group.set_nickname(target_user, new_nick)
        await set_nick.send(f'已修改用户 {target_id} 的群昵称为：{new_nick}')
    except Exception as e:
        await set_nick.send(f'修改昵称失败：{str(e)}')
        raise e

@kick.handle()
@permission_required(4)
async def handle_kick(event: GroupMessageEvent):
    user, cmd_args, group = get_context(event)
    
    if not cmd_args:
        await kick.finish('参数格式：/kick @用户 [理由]')
    
    try:
        target_id = int(cmd_args[0])
        reason = ' '.join(cmd_args[1:]) if len(cmd_args) > 1 else None
        target_user = User(target_id)
        
        await group.kick(target_user)
        msg = f'已踢出用户 {target_id}'
        if reason:
            msg += f'，理由：{reason}'
        await kick.send(msg)
    except Exception as e:
        await kick.send(f'踢出失败：{str(e)}')
        raise e

@block.handle()
@permission_required(5)
async def handle_block(event: GroupMessageEvent):
    user, cmd_args, group = get_context(event)
    
    if not cmd_args:
        await block.finish('参数格式：/block @用户 [理由]')
    
    try:
        target_id = int(cmd_args[0])
        reason = ' '.join(cmd_args[1:]) if len(cmd_args) > 1 else None
        target_user = User(target_id)
        
        await group.ban(target_user)
        msg = f'已拉黑用户 {target_id}'
        if reason:
            msg += f'，理由：{reason}'
        await block.send(msg)
    except Exception as e:
        await block.send(f'拉黑失败：{str(e)}')
        raise e