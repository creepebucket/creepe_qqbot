import random
from typing import List, Dict, Tuple
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import permission_required, get_context, check_command_enabled

FISHING_LOOT: Dict[str, Dict] = {
    # 鱼类 85%
    "fish": {
        "weight": 85,
        "items": [
            ("生鳕鱼", 60),   # 51.0%
            ("生鲑鱼", 25),   # 21.3%
            ("热带鱼", 2),    # 1.7%
            ("河豚", 13)     # 11.0%
        ]
    },
    # 宝藏 5%
    "treasure": {
        "weight": 5,
        "items": [
            ("附魔弓", 16.7),      # 0.8%
            ("附魔书", 16.7),      # 0.8%
            ("附魔钓鱼竿", 16.7),  # 0.8%
            ("命名牌", 16.7),      # 0.8%
            ("鹦鹉螺壳", 16.7),    # 0.8%
            ("鞍", 16.7)          # 0.8%
        ]
    },
    # 垃圾 10%
    "junk": {
        "weight": 10,
        "items": [
            ("睡莲", 17),        # 1.7%
            ("碗", 10),          # 1.0%
            ("钓鱼竿", 2),       # 0.2%
            ("皮革", 10),        # 1.0%
            ("皮革靴子", 10),     # 1.0%
            ("腐肉", 10),        # 1.0%
            ("木棍", 5),         # 0.5%
            ("线", 5),           # 0.5%
            ("水瓶", 10),        # 1.0%
            ("骨头", 10),        # 1.0%
            ("墨囊", 1),     # 0.1%
            ("绊线钩", 10)       # 1.0%
        ]
    }
}

def get_fishing_result() -> str:
    """根据游戏机制生成钓鱼结果"""
    # 选择战利品类别
    category = random.choices(
        population=list(FISHING_LOOT.keys()),
        weights=[v["weight"] for v in FISHING_LOOT.values()],
        k=1
    )[0]
    
    # 选择具体物品
    items, weights = zip(*FISHING_LOOT[category]["items"])
    return random.choices(items, weights=weights, k=1)[0]

fishing = on_command("钓鱼", aliases={"fish", "cast"})
add_info('钓鱼', '模拟MC钓鱼\n参数: /钓鱼 [次数=1] (最多20次)')

@fishing.handle()
@permission_required(1)
@check_command_enabled('fish')
async def handle_fishing(event: MessageEvent):
    _, args, _ = get_context(event)
    
    # 解析次数参数
    try:
        times = min(int(args[0]) if args else 1, 2000)
        times = max(times, 1)
    except ValueError:
        await fishing.finish("参数错误，请输入1-2000之间的数字")
    
    # 生成钓鱼结果
    results: List[str] = []
    for _ in range(times):
        item = get_fishing_result()
        results.append(item)
    
    # 统计结果
    result_stats = {}
    for item in results:
        result_stats[item] = result_stats.get(item, 0) + 1
    
    # 构建消息
    msg = MessageSegment.text("🎣 钓鱼结果：\n")
    for item, count in result_stats.items():
        msg += MessageSegment.text(f"\n{item} ×{count}")
    
    # 添加提示
    if times > 1:
        msg += MessageSegment.text(f"\n\n共钓得 {len(results)} 件物品")
    
    await fishing.finish(msg)