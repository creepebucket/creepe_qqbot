import random

from nonebot import on_message, on_keyword
from nonebot.adapters.onebot.v11 import Event

from redstone_daily.plugins.utils import check_command_enabled

gtnh = on_keyword({'gtnh'})

@gtnh.handle()
@check_command_enabled('keyword', False)
async def gtnh_handler(event: Event):
    await gtnh.send(random.choice(['你产能不够吧', '这就是gtnh.png', 'gtnh是世界上最好玩的游戏', 'gtnh是工厂的神',
                                   '员工你做出星门了吗, 快去上工', '玩gtnh就不应该加私活']))