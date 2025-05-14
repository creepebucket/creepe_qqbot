from redstone_daily.plugins.config import config

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Event

from redstone_daily.plugins.utils import get_context, permission_required, get_all_ops, User

perm_matcher = on_command(
    'op', force_whitespace=True, priority=15)
perm_list_matcher = on_command(
    'op list', force_whitespace=True, priority=10, block=True)
perm_query_matcher = on_command(
    'op query', force_whitespace=True, priority=10, block=True)
perm_set_matcher = on_command(
    'op set', force_whitespace=True, priority=10, block=True)


@perm_matcher.handle()
async def handle_perm(event: Event):
    sender, arg, group = get_context(event)

    await perm_matcher.finish(F'您当前的权限为 {sender.get_permission(group)} 级。')


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

    if not arg[1].isdigit():  # 若参数不是数字
        await perm_query_matcher.finish('用户 QQ 号格式错误，请重新填写后尝试。')

    user = User(int(arg[1]))  # 实例化用户对象

    await perm_query_matcher.finish(f'用户 {user.id} 的操作权限为 {user.get_permission(group)} 级。')
    await perm_query_matcher.finish('参数不能为空！')


@perm_set_matcher.handle()
@permission_required(10)
async def handle_perm_set(event: Event):
    sender, arg, group = get_context(event)

    if len(arg) != 3:  # 若参数长度不为 2
        await perm_set_matcher.finish('参数错误，请查看语法然后重新尝试。')

    user_id, permission = arg[-2:]  # 取出参数
    if not (user_id.isdigit() and permission.isdigit()):  # 若参数不是数字
        await perm_set_matcher.finish('用户 QQ 号格式或权限等级格式错误，请重新填写后尝试。')

    permission = int(permission)
    user = User(int(user_id))  # 实例化用户对象

    if not 1 <= permission <= 10:  # 若权限等级不在 1 到 10 之间
        await perm_set_matcher.finish('权限等级只能在 1 到 10 之间。')

    user.set_permission(permission, group)  # 设置用户权限
    await perm_set_matcher.finish(F'用户 {user.id} 的操作权限已设置为 {permission} 级。')

