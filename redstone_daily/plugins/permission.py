from redstone_daily.plugins.config import config

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Event

from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import get_context, permission_required, get_all_ops, User, Group

perm_matcher = on_command('op')
add_info('op', '获取自己的权限\n群主默认权限5, 管理员默认权限3')
perm_list_matcher = on_command('op_list')
add_info('op_list', '获取当前群数据库中所有人权限\n需求1级权限')
perm_query_matcher = on_command('op_query')
add_info('op_query', '获取自己的权限')
perm_set_matcher = on_command('op_set')
add_info('op_set', '设置某人的权限\n需求5级权限(群主)\n参数:/op_set <qq> <level>')
perm_set_superuser = on_command('op_set_su')
add_info('op_set_su', '超级用户指令: 设置某人在某群的权限\n参数: 3种形式\n/op_set_su <level>\n'
                      '/op_set_su <level> <groupid>\n/op_set_su <qq> <level> <groupid>')

# 特殊权限管理指令
special_perm_set = on_command('special_perm_set')
add_info('special_perm_set', '设置特殊权限\n超级用户专用\n参数: /special_perm_set <qq> <权限名>')

special_perm_remove = on_command('special_perm_remove') 
add_info('special_perm_remove', '移除特殊权限\n超级用户专用\n参数: /special_perm_remove <qq> <权限名>')

special_perm_list = on_command('special_perm_list')
add_info('special_perm_list', '查询用户的特殊权限\n参数: /special_perm_list <qq>')


@perm_matcher.handle()
async def handle_perm(event: Event):
    sender, arg, group = get_context(event)

    await perm_matcher.finish(F'您当前的权限为 {await sender.get_permission(group)} 级。')


@perm_list_matcher.handle()
@permission_required(1)
async def handle_perm_list(event: Event):

    message = '当前的操作权限列表：\n |---用户---|权限|'

    for i in get_all_ops():
        user = i['id']  # 用户
        permission = i['permission']  # 权限等级
        message += f'\n{user}   {permission}'

    await perm_list_matcher.finish(message)


@perm_query_matcher.handle()
async def handle_perm_query(event: Event):
    sender, arg, group = get_context(event)

    if not arg[0].isdigit():  # 若参数不是数字
        await perm_query_matcher.finish('用户 QQ 号格式错误，请重新填写后尝试。')

    user = User(int(arg[0]))  # 实例化用户对象

    await perm_query_matcher.finish(f'用户 {user.id} 的操作权限为 {await user.get_permission(group)} 级。')
    await perm_query_matcher.finish('参数不能为空！')


@perm_set_matcher.handle()
@permission_required(5)
async def handle_perm_set(event: Event):
    sender, arg, group = get_context(event)

    if len(arg) != 2:  # 若参数长度不为 2
        await perm_set_matcher.finish('参数错误，请查看语法然后重新尝试。')

    user_id, permission = arg[-2:]  # 取出参数
    if not (user_id.isdigit() and permission.isdigit()):  # 若参数不是数字
        await perm_set_matcher.finish('用户 QQ 号格式或权限等级格式错误，请重新填写后尝试。')

    permission = int(permission)
    user = User(int(user_id))  # 实例化用户对象

    if not 1 <= permission <= 5:  # 若权限等级不在 1 到 5 之间
        await perm_set_matcher.finish('权限等级只能在 1 到 5 之间。')

    user.set_permission(permission, group)  # 设置用户权限
    await perm_set_matcher.finish(F'用户 {user.id} 的操作权限已设置为 {permission} 级。')

@perm_set_superuser.handle()
async def handle_perm_set_su(event: Event):
    sender, arg, group = get_context(event)

    SUPERUSERS = [3327018890]
    if sender.id not in SUPERUSERS:
        await perm_set_superuser.finish('你不是超级用户! 如何获取超级用户? 前往gtnewhorizons.com获取更多信息')

    if len(arg) == 1:
        sender.set_permission(int(arg[0]), group)
        await perm_set_superuser.finish(f'已将用户{sender.id}在{group.id}的权限设置为{arg[0]}')
    elif len(arg) == 2:
        sender.set_permission(int(arg[0]), Group(int(arg[1])))
        await perm_set_superuser.finish(f'已将用户{sender.id}在{arg[1]}的权限设置为{arg[0]}')
    else:
        User(arg[0]).set_permission(int(arg[1]), Group(int(arg[2])))
        await perm_set_superuser.finish(f'已将用户{arg[0]}在{arg[2]}的权限设置为{arg[1]}')


@special_perm_set.handle()
async def handle_special_perm_set(event: Event):
    """设置特殊权限"""
    sender, arg, group = get_context(event)
    
    SUPERUSERS = [3327018890]
    if sender.id not in SUPERUSERS:
        await special_perm_set.finish('❌ 你不是超级用户，无法执行此操作')
        return
    
    if len(arg) != 2:
        await special_perm_set.finish('❌ 参数错误\n用法: /special_perm_set <QQ号> <权限名>')
        return
    
    user_id_str, permission_name = arg
    
    if not user_id_str.isdigit():
        await special_perm_set.finish('❌ QQ号格式错误')
        return
    
    user_id = int(user_id_str)
    user = User(user_id)
    
    # 设置特殊权限
    user.set_special_permission(permission_name, True)
    
    await special_perm_set.finish(f'✅ 已为用户 {user_id} 设置特殊权限「{permission_name}」')


@special_perm_remove.handle()
async def handle_special_perm_remove(event: Event):
    """移除特殊权限"""
    sender, arg, group = get_context(event)
    
    SUPERUSERS = [3327018890]
    if sender.id not in SUPERUSERS:
        await special_perm_remove.finish('❌ 你不是超级用户，无法执行此操作')
        return
    
    if len(arg) != 2:
        await special_perm_remove.finish('❌ 参数错误\n用法: /special_perm_remove <QQ号> <权限名>')
        return
    
    user_id_str, permission_name = arg
    
    if not user_id_str.isdigit():
        await special_perm_remove.finish('❌ QQ号格式错误')
        return
    
    user_id = int(user_id_str)
    user = User(user_id)
    
    # 移除特殊权限
    user.set_special_permission(permission_name, False)
    
    await special_perm_remove.finish(f'✅ 已移除用户 {user_id} 的特殊权限「{permission_name}」')


@special_perm_list.handle()
async def handle_special_perm_list(event: Event):
    """查询用户特殊权限"""
    sender, arg, group = get_context(event)
    
    # 如果没有参数，查询自己的权限
    if not arg:
        user = sender
    else:
        if not arg[0].isdigit():
            await special_perm_list.finish('❌ QQ号格式错误')
            return
        user = User(int(arg[0]))
    
    # 获取特殊权限列表
    special_perms = user.get_special_permissions()
    
    if not special_perms:
        await special_perm_list.finish(f'用户 {user.id} 暂无特殊权限')
    else:
        perms_str = '、'.join(special_perms)
        await special_perm_list.finish(f'用户 {user.id} 的特殊权限：{perms_str}')


