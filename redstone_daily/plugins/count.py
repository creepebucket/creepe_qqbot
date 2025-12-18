from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event

from redstone_daily.plugins.base.helper import add_info
from redstone_daily.plugins.utils import get_database, get_context, check_command_enabled


add_info(
    'count',
    '简单计数器（别名：计数）\n'
    '/count <key> - 将 key 的计数 +1 并返回当前值\n'
    '/count get <key> - 查看 key 的当前值\n'
    '/count set <key> <value> - 设置 key 的值\n'
    '/count clear <key> - 将 key 清零\n'
    '提示：若提示指令被禁用，请先在目标群使用 /enable_command count'
)

count_cmd = on_command('count', aliases={'计数'})


@count_cmd.handle()
@check_command_enabled('count')
async def handle_count(event: Event):
    user, args, group = get_context(event)

    collection = get_database('counters').get_db()

    # 参数为空 -> 提示用法
    if not args:
        await count_cmd.finish(
            '用法:\n'
            '/count <key>\n'
            '/count get <key>\n'
            '/count set <key> <value>\n'
            '/count clear <key>'
        )

    sub = args[0].lower()

    # 查看
    if sub in {'get', '查看', 'show', 'value'}:
        if len(args) < 2:
            await count_cmd.finish('用法: /count get <key>')
        key = args[1]
        doc = collection.find_one({'group_id': group.id, 'key': key})
        value = (doc or {}).get('count', 0)
        await count_cmd.finish(f'{key} 当前值：{value}')

    # 设置
    if sub in {'set', '设置'}:
        if len(args) < 3:
            await count_cmd.finish('用法: /count set <key> <value>')
        key = args[1]
        try:
            value = int(args[2])
        except ValueError:
            await count_cmd.finish('value 必须是整数')
            return
        collection.update_one(
            {'group_id': group.id, 'key': key},
            {'$set': {'count': value}},
            upsert=True
        )
        await count_cmd.finish(f'{key} 已设置为：{value}')

    # 清除/清零
    if sub in {'clear', '清除', 'reset', '重置'}:
        if len(args) < 2:
            await count_cmd.finish('用法: /count clear <key>')
        key = args[1]
        collection.update_one(
            {'group_id': group.id, 'key': key},
            {'$set': {'count': 0}},
            upsert=True
        )
        await count_cmd.finish(f'{key} 已清零，当前值：0')

    # 默认行为：将 key 计数 +1
    key = args[0]
    collection.update_one(
        {'group_id': group.id, 'key': key},
        {'$inc': {'count': 1}},
        upsert=True
    )
    doc = collection.find_one({'group_id': group.id, 'key': key})
    value = (doc or {}).get('count', 0)
    await count_cmd.finish(f'{key} +1 成功，当前值：{value}')
