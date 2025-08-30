import random
import re

from nonebot.adapters.onebot.v11 import Event
from nonebot.plugin.on import on_command, on_message

from redstone_daily.plugins.base import add_info
from redstone_daily.plugins.utils import check_command_enabled, get_context

dice = on_message()
add_info('dice', '掷骰子, 用法: /xxxdyyy, x为个数, y为面数')

@dice.handle()
@check_command_enabled('dice')
async def dice_handler(event: Event):
    message = event.get_message().extract_plain_text().strip()
    print(message)
    if not re.match('^/[0-9]{1,3}d[0-9]{1,3}$', message):
        return

    args = message.replace('/', '').split('d')
    answer = '['

    for i in range(int(args[0])):
        answer += f' {random.randint(1, int(args[1]))} '

    await dice.send(f'{answer}]')