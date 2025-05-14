from datetime import datetime, timedelta

import nonebot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    Message,
    MessageSegment,
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
)
from nonebot.plugin import on_notice, on_message
import random

from redstone_daily.plugins.utils import Group, User, check_command_enabled

# 初始化定时任务
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
driver = nonebot.get_driver()


# 启动定时器
@driver.on_startup
async def start_scheduler():
    scheduler.start()


# 更新后的竖向数字模板（每个数字5行）
DIGITS_ART = {
    '0': [
        '█████',
        '█╳╳╳█',
        '█╳╳╳█',
        '█╳╳╳█',
        '█████',
    ],
    '1': [
        '╳╳█╳╳',
        '╳██╳╳',
        '█╳█╳╳',
        '╳╳█╳╳',
        '█████',
    ],
    '2': [
        '█████',
        '╳╳╳██',
        '╳███╳',
        '██╳╳╳',
        '█████',
    ],
    '3': [
        '█████',
        '╳╳╳██',
        '█████',
        '╳╳╳██',
        '█████',
    ],
    '4': [
        '██╳██',
        '██╳██',
        '█████',
        '╳╳╳██',
        '╳╳╳██',
    ],
    '5': [
        '█████',
        '██╳╳╳',
        '╳███╳',
        '╳╳╳██',
        '█████',
    ],
    '6': [
        '█████',
        '██╳╳╳',
        '█████',
        '██╳██',
        '█████',
    ],
    '7': [
        '█████',
        '╳╳╳██',
        '╳╳██╳',
        '╳██╳╳',
        '██╳╳╳',
    ],
    '8': [
        '█████',
        '██╳██',
        '█████',
        '██╳██',
        '█████',
    ],
    '9': [
        '█████',
        '██╳██',
        '█████',
        '╳╳╳██',
        '█████',
    ],
}

pending_verification = {}


def generate_art(code: str) -> str:
    """生成纵向排列的验证码（每个数字显示5行）"""
    art_lines = []

    # 生成数字图形
    for digit in code:
        for row in DIGITS_ART[digit]:
            # 添加随机颜色反转
            line = []
            for c in row:
                if random.random() < 0.05:  # 保持5%反转概率
                    line.append('╳' if c == '█' else '█')
                else:
                    line.append(c)
            art_lines.append(''.join(line))

        # 添加数字间隔
        art_lines.append('')  # 空行分隔

    return '\n'.join(art_lines)  # 严格限制29行


group_increase_handler = on_notice()
message_handler = on_message()


# 新增定时任务检查函数
@scheduler.scheduled_job("interval", minutes=1)
async def check_timeout():
    now = datetime.now()
    expired_users = []

    for (user_id, group_id), info in list(pending_verification.items()):
        elapsed = now - info["join_time"]

        # 超时处理（30分钟）
        if elapsed >= timedelta(minutes=30):
            expired_users.append((user_id, group_id))
            try:
                group = Group(group_id)
                user = User(user_id)
                await group.kick(user)
                bot = nonebot.get_bot()
                await bot.send_group_msg(
                    group_id=group_id,
                    message=Message([
                        MessageSegment.text("用户 "),
                        MessageSegment.at(user_id),
                        MessageSegment.text(" 因超时未验证已被移出")
                    ])
                )
            except Exception as e:
                print(f"踢出失败: {e}")

        # 10分钟剩余提醒（加入后20分钟时提醒）
        elif not info["reminded"] and elapsed >= timedelta(minutes=20):
            try:
                remaining = 30 - elapsed.total_seconds() // 60
                bot = nonebot.get_bot()
                await bot.send_group_msg(
                    group_id=group_id,
                    message=Message([
                        MessageSegment.at(user_id),
                        MessageSegment.text(f" 剩余验证时间：{int(remaining)}分钟，请尽快完成验证！")
                    ])
                )
                info["reminded"] = True
            except Exception as e:
                print(f"提醒失败: {e}")

    # 清理已处理用户
    for key in expired_users:
        pending_verification.pop(key, None)


@group_increase_handler.handle()
@on_command('test').handle()
@check_command_enabled('turing', False)
async def handle_increase(event: GroupIncreaseNoticeEvent):
    bot = nonebot.get_bot()
    user_id = event.user_id
    group_id = event.group_id
    code = ''.join(random.choices('0123456789', k=3))

    pending_verification[(user_id, group_id)] = {
        'code': code,
        'attempts_left': 3,
        'join_time': datetime.now(),
        'reminded': False
    }

    art = generate_art(code)
    message = Message([
        MessageSegment.at(user_id),
        MessageSegment.text(
            f"\n【入群验证】\n请完成图灵测试, 发送3位数字验证码 当前验证码：\n{art}\n"
            f"剩余尝试次数：3次\n请在30分钟内完成验证！\n无法识别？发送“刷新验证码”以更换验证码\n"
            "⚠️ 超时或失败将被移出群组"
        )
    ])

    await bot.send_group_msg(group_id=group_id, message=message)


# 修改后的验证处理函数（保持原有逻辑，在成功/失败时移除记录）
@message_handler.handle()
async def verify_message(event: GroupMessageEvent, bot: Bot):
    key = (event.user_id, event.group_id)
    if key not in pending_verification:
        return

    msg = event.get_plaintext().strip()
    stored_info = pending_verification[key]

    # 处理刷新验证码请求（保持原有逻辑）
    if msg == "刷新验证码":
        new_code = ''.join(random.choices('0123456789', k=3))
        stored_info['code'] = new_code
        art = generate_art(new_code)
        message = Message([
            MessageSegment.at(event.user_id),
            MessageSegment.text(
                f"\n新的验证码已生成（剩余时间：{30 - (datetime.now() - stored_info['join_time']).seconds // 60}分钟）\n{art}\n剩余尝试次数：{stored_info['attempts_left']}\n无法识别？发送“刷新验证码”以更换验证码"),
        ])
        await bot.send_group_msg(group_id=event.group_id, message=message)
        return

    # 验证逻辑（保持原有逻辑）
    code = stored_info['code']
    attempts_left = stored_info['attempts_left']

    if msg == code:
        await bot.send(event, MessageSegment.at(event.user_id) + " 验证成功！")
        pending_verification.pop(key, None)
    else:
        attempts_left -= 1
        if attempts_left > 0:
            stored_info['attempts_left'] = attempts_left
            await bot.send(event, MessageSegment.at(event.user_id) + f" 验证失败，剩余尝试次数：{attempts_left}\n无法识别？发送“刷新验证码”以更换验证码")
        else:
            pending_verification.pop(key, None)
            group = Group(event.group_id)
            user = User(event.user_id)
            await group.kick(user)
            await bot.send_group_msg(
                group_id=event.group_id,
                message=Message([
                    MessageSegment.at(event.user_id),
                    MessageSegment.text(" 验证失败次数过多，已移出群组")
                ])
            )
