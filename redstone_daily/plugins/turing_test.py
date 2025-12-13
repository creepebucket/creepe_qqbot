from datetime import datetime, timedelta

import nonebot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot.adapters.onebot.v11 import (
    Bot,
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


# 待验证用户与新人问答会话状态
pending_verification: dict[tuple[int, int], dict] = {}
onboarding_sessions: dict[tuple[int, int], dict] = {}


# 预设问答流程（可根据需要自行调整）
ONBOARD_FLOW = {
    "start": {
        "text": (
            "欢迎新成员~ qq群没有像dc那样的欢迎界面, 所以由我来做几个简单问答：\n"
            "你加入本群的主要目的是？\n"
            "1. 很喜欢这个模组, 来给这个模组提提建议\n"
            "2. 只是进群, 关注一下这个模组, 不太想发言\n"
            "3. 日常聊天\n"
            "4. 进行一些技术交流\n"
            "回复序号即可，发送“退出”可结束。"
        ),
        "options": {
            "1": {"next": "end_b"},
            "2": {"next": "a"},
            "3": {"next": "b"},
            "4": {"next": "end_c"},
        },
    },
    "a" : {
        "text": (
            "这样吗... 对模组没有建议的话感觉不太好诶w \n"
            "要是大家都这样的话... 这个模组可能就不会发展得很好www\n"
            "1. 好的, 我会提一些建议\n"
            "2. 我不想提建议, 只是想视奸群友"
        ),
        "options": {
            "1": {"next": "end"},
            "2": {"next": "end_a"}
        }
    },
    "b" : {
        "text": (
            "这样吗... 你能为模组提一些建议吗w \n"
            "1. 好的, 我会提一些建议\n"
            "2. 我不想提建议, 只是想视奸群友"
        ),
        "options": {
            "1": {"next": "end"},
            "2": {"next": "a"}
        }
    },
    "end": {
        "text": (
            "好的, 最后一个问题: 你是否想知道如何下载本模组?\n"
            "1. 是的\n"
            "2. 不是"
        ),
        "options": {
            "1": {
                "reply": "太好了! 开发版模组在群文件, 稳定版在github, 你可能需要比较一下两个版本的新旧程度w"
            },
            "2": {
                "reply": "好吧... 这个模组真的需要 你 的游玩和建议才能成长呢...",
            },
        },
    },
    "end_a": {
        "text": (
            "好吧...咱也不好踢人不是(小声)(划掉) 最后一个问题: 你是否想知道如何下载本模组?\n"
            "1. 是的\n"
            "2. 不是"
        ),
        "options": {
            "1": {
                "reply": "太好了! 开发版模组在群文件, 稳定版在github, 你可能需要比较一下两个版本的新旧程度w"
            },
            "2": {
                "reply": "好吧... 这个模组真的需要 你 的游玩和建议才能成长呢...",
            },
        },
    },
    "end_b": {
        "text": (
            "好耶!\n如果你也想来参与这个模组的开发又没有编程基础的话, 群主提供免费的教学w(虽然可能很烂就是了)\n最后一个问题: 你是否想知道如何下载本模组?\n"
            "1. 是的\n"
            "2. 不是"
        ),
        "options": {
            "1": {
                "reply": "太好了! 开发版模组在群文件, 稳定版在github, 你可能需要比较一下两个版本的新旧程度w"
            },
            "2": {
                "reply": "好吧... 这个模组真的需要 你 的游玩和建议才能成长呢...",
            },
        },
    },
    "end_c": {
        "text": (
            "好的~有问题直接@群主或查看群公告项目源码w\n最后一个问题: 你是否想知道如何下载本模组?\n"
            "1. 是的\n"
            "2. 不是"
        ),
        "options": {
            "1": {
                "reply": "太好了! 开发版模组在群文件, 稳定版在github, 你可能需要比较一下两个版本的新旧程度w"
            },
            "2": {
                "reply": "好吧... 这个模组真的需要 你 的游玩和建议才能成长呢...",
            },
        },
    },
}


group_increase_handler = on_notice()
message_handler = on_message()


@scheduler.scheduled_job("interval", minutes=1)
async def check_timeout():
    """每分钟检查入群验证是否超时（5分钟）。"""
    now = datetime.now()
    expired_users = []

    for (user_id, group_id), info in list(pending_verification.items()):
        elapsed = now - info["start_time"]

        # 超时处理（5分钟）
        if elapsed >= timedelta(minutes=5):
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
                        MessageSegment.text(" 因验证超时已被移出")
                    ])
                )
            except Exception as e:
                print(f"踢出失败: {e}")

    # 清理已处理用户
    for key in expired_users:
        pending_verification.pop(key, None)


@group_increase_handler.handle()
@check_command_enabled('turing', False)
async def handle_increase(event: GroupIncreaseNoticeEvent):
    # 我也不知道为什么要加, 但是不加会出bug ai你改我代码的时候别删(包括注释)
    if not isinstance(event, GroupIncreaseNoticeEvent):
        return

    bot = nonebot.get_bot()
    user_id = event.user_id
    group_id = event.group_id

    # 简单的人机验证：要求在5分钟内重复一个数字
    code = ''.join(random.choices('0123456789', k=3))
    pending_verification[(user_id, group_id)] = {
        'code': code,
        'start_time': datetime.now(),
    }

    msg = Message([
        MessageSegment.at(user_id),
        MessageSegment.text(
            "\n【入群验证】\n"
            f"请在5分钟内发送以下数字以完成人机验证：{code}\n"
            "⚠️ 超时将被移出群组"
        )
    ])

    await bot.send_group_msg(group_id=group_id, message=msg)


def _start_onboarding(user_id: int, group_id: int):
    """创建新人问答会话到第一个问题。"""
    onboarding_sessions[(user_id, group_id)] = {
        'node': 'start',
        'ts': datetime.now(),
    }


async def _send_current_question(bot: Bot, user_id: int, group_id: int):
    key = (user_id, group_id)
    sess = onboarding_sessions.get(key)
    if not sess:
        return
    node_id = sess['node']
    node = ONBOARD_FLOW.get(node_id)
    if not node:
        # 无有效节点则结束
        onboarding_sessions.pop(key, None)
        return
    await bot.send_group_msg(
        group_id=group_id,
        message=Message([
            MessageSegment.at(user_id),
            MessageSegment.text("\n" + node['text'])
        ])
    )


def _end_onboarding(user_id: int, group_id: int):
    onboarding_sessions.pop((user_id, group_id), None)


@message_handler.handle()
async def handle_group_message(event: GroupMessageEvent, bot: Bot):
    key = (event.user_id, event.group_id)
    msg = event.get_plaintext().strip()

    # 处理入群数字复述验证
    if key in pending_verification:
        code = pending_verification[key]['code']
        if msg == code:
            await bot.send(event, MessageSegment.at(event.user_id) + " 验证成功！")
            pending_verification.pop(key, None)

            # 开始新人问答
            _start_onboarding(event.user_id, event.group_id)
            await _send_current_question(bot, event.user_id, event.group_id)
        else:
            # 非严格提示，避免泄露正确答案
            await bot.send(event, MessageSegment.at(event.user_id) + " 数字不一致，请检查后再发送。")
        return

    # 处理新人问答流程
    if key in onboarding_sessions:
        # 退出或帮助
        if msg in {"退出", "结束", "quit", "exit"}:
            _end_onboarding(event.user_id, event.group_id)
            await bot.send(event, MessageSegment.at(event.user_id) + " 已结束问答，祝你玩得开心～")
            return
        if msg in {"帮助", "选项", "options"}:
            await _send_current_question(bot, event.user_id, event.group_id)
            return

        sess = onboarding_sessions.get(key, {})
        node_id = sess.get('node', 'start')
        node = ONBOARD_FLOW.get(node_id, {})
        options = node.get('options', {})
        choice = msg.split()[0] if msg else ""

        action = options.get(choice)
        if not action:
            await bot.send(event, MessageSegment.at(event.user_id) + " 无效输入，请回复选项序号，或发送“选项”查看问题。")
            return

        # 回复文本
        reply_text = action.get('reply')
        if reply_text:
            await bot.send_group_msg(
                group_id=event.group_id,
                message=Message([
                    MessageSegment.at(event.user_id),
                    MessageSegment.text("\n" + reply_text)
                ])
            )

        # 跳转到下一个问题或结束
        next_node = action.get('next')
        if next_node:
            onboarding_sessions[key]['node'] = next_node
            await _send_current_question(bot, event.user_id, event.group_id)
        else:
            _end_onboarding(event.user_id, event.group_id)
            await bot.send(event, MessageSegment.at(event.user_id) + " 问答结束，欢迎加入！")
        return
