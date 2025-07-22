import asyncio
import re
import time

import nonebot
from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import Event

from baimomcsm_api import applications
from redstone_daily.plugins.mc_management.config import get_instance_id, MCSM_CONFIG

from redstone_daily.plugins.utils import check_command_enabled, get_context, get_database, check_server_permission_async

bind = on_command('bind')


@bind.handle()
@check_command_enabled('bind')
async def bind_handler(event: Event):
    user, args, group = get_context(event)

    server_name = args[0]

    # 检查用户是否有该服务器的特殊权限
    if not await check_server_permission_async(user, server_name, group):
        await bind.finish(f'❌ 权限不足，需要 "{server_name}" 服务器权限')

    db = get_database('chat_bind').get_db()

    # 查绑定服务器列表并修改

    doc = db.find_one({'groupid': group.id})
    print(doc['servers']) if doc else ''
    if not doc:
        db.insert_one({'groupid': group.id, 'servers': [args[0]]})
        await bind.send(f'已绑定本群到服务器{args[0]}')
    elif args[0] not in doc['servers']:
        s = doc['servers']
        s.append(args[0])
        db.update_one({'groupid': group.id}, {'$set': {'servers': s}})
        await bind.send(f'已绑定本群到服务器{args[0]}')
    else:
        s = doc['servers']
        s.remove(args[0])
        db.update_one({'groupid': group.id}, {'$set': {'servers': s}})
        await bind.send(f'已取消绑定本群到服务器{args[0]}')


@on_message().handle()
def send_qq_to_server(event: Event):
    user, args, group = get_context(event)
    db = get_database('chat_bind').get_db()

    # 查绑定服务器列表
    doc = db.find_one({'groupid': group.id})

    if not doc:
        return

    # 发送服务器消息
    try:
        for server_name in doc['servers']:
            # 获取服务器实例ID和备份路径
            instance_id = get_instance_id(server_name)

            applications.send_command(
                MCSM_CONFIG['url'],
                instance_id,
                MCSM_CONFIG['daemon_id'],
                MCSM_CONFIG['apikey'],
                f'say qq[{user.name}/{user.id}]: {event.get_plaintext()}'
            )
    except:
        pass


async def check_server_messages():
    """定时检查服务器消息并转发到QQ"""
    last = {}
    initialized = {}
    while True:
        db = get_database('chat_bind').get_db()

        # 获取所有绑定的群组
        bindings = db.find({})

        for binding in bindings:
            group_id = binding['groupid']
            servers = binding['servers']

            for server_name in servers:
                instance_id = get_instance_id(server_name)

                # 获取服务器日志
                log_content = applications.get_outputlog(
                    MCSM_CONFIG['url'],
                    instance_id,
                    MCSM_CONFIG['daemon_id'],
                    MCSM_CONFIG['apikey']
                )

                if not log_content:
                    continue

                # 解析日志中的聊天消息
                lines = log_content.split('\n')
                new_messages = []

                for line in lines:
                    # 匹配Minecraft聊天消息格式
                    # 例如: [12:34:56] [Server thread/INFO]: <玩家名> 消息内容
                    chat_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\] \[Server thread/INFO]: <([^>]+)> (.+)', line)
                    if chat_match:
                        time_str = chat_match.group(1)
                        player_name = chat_match.group(2)
                        message = chat_match.group(3)

                        # 定义黑名单关键词列表
                        blacklist = ['Still Generating Crop Plugin Cache']

                        # 检查是否以QQ消息开头 或 包含黑名单中的任何关键词
                        if message.startswith('qq[') or any(blocked_word in message for blocked_word in blacklist):
                            continue

                        new_messages.append(f'服务器[{server_name}/{player_name}]: {message}标记标记qwertyuiop{time_str}')  #加个时间防止去重bug

                # 发送新消息到QQ群
                if new_messages and initialized.get(server_name):
                    from nonebot import get_bot

                    try:
                        bot = get_bot()

                        for message in new_messages:
                            if message not in last[server_name]:

                                await bot.send_group_msg(group_id=int(group_id), message=message.replace('\n', '').split('标记标记qwertyuiop')[0])

                        last[server_name] = new_messages
                    except ValueError:
                        pass

                # 第一次运行初始化
                if not initialized.get(server_name):
                    initialized[server_name] = True
                    last[server_name] = new_messages

        # 每秒检查一次
        await asyncio.sleep(1)


@nonebot.get_driver().on_startup
async def start_server_message_checker():
    """启动时启动服务器消息检查器"""
    try:
        asyncio.create_task(check_server_messages())
        import logging
        logging.info('✅ 服务器消息检查器已启动')
    except Exception as e:
        import logging
        logging.error(f'❌ 启动服务器消息检查器失败: {str(e)}')


server_log_positions = {}
