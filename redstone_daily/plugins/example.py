# === User类方法演示 ===
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import check_command_enabled, permission_required, get_database, User, Group, \
    get_context, get_all_ops, config_db


# add_info('示例', '给ai看的示例指令')  # 注册帮助信息, 两个参数: name, desc

async def user_demo():
    # 创建用户对象
    user = User(123456789)  # 123456789为用户QQ号

    # 获取用户权限（需要群组对象）
    group = Group(987654321)  # 987654321为群号
    permission_level = await user.get_permission(group)  # 返回int权限等级
    # IO效果：查询MongoDB permissions集合，可能触发网络请求获取群成员信息

    # 设置用户权限
    user.set_permission(3, group)  # 参数：权限等级(int)，群组对象
    # IO效果：更新MongoDB permissions集合，使用upsert操作

    # 发送私聊消息
    msg = MessageSegment.text("测试消息")
    await user.send(msg)  # 参数：MessageSegment对象
    # IO效果：通过QQ机器人API发送私聊消息


# === Group类方法演示 ===
async def group_demo():
    group = Group(987654321)

    # 禁言用户
    user = User(123456789)
    await group.mute(user, 3600)  # 参数：用户对象，禁言时长(秒)
    # IO效果：调用set_group_ban API，禁言用户1小时

    # 解除禁言
    await group.unmute(user)  # 参数：用户对象
    # IO效果：调用set_group_ban API，禁言时长设为0

    # 踢出群成员
    await group.kick(user)  # 参数：用户对象
    # IO效果：调用set_group_kick API，不拒绝加群请求

    # 拉黑群成员
    await group.ban(user)  # 参数：用户对象
    # IO效果：调用set_group_kick API，拒绝加群请求

    # 设置群昵称
    await group.set_nickname(user, "新昵称")  # 参数：用户对象，新昵称(str)
    # IO效果：调用set_group_card API

    # 检查指令是否启用
    is_enabled = group.is_command_enabled("mute")  # 参数：指令名称(str)
    # IO效果：查询MongoDB group_commands集合，返回bool

    # 启用指令
    await group.add_command("mute")  # 参数：指令名称(str)
    # IO效果：更新MongoDB group_commands集合，添加指令

    # 禁用指令
    await group.remove_command("mute")  # 参数：指令名称(str)
    # IO效果：更新MongoDB group_commands集合，移除指令


# === 数据库方法演示 ===
def database_demo():
    # 获取数据库实例
    config_db = get_database('config')  # 参数：集合名称

    # 查询数据
    result = config_db.get({'key': 'value'})  # 参数：查询条件dict
    # 返回值：匹配的文档dict或None

    # 获取集合实例
    collection = config_db.get_db()  # 返回MongoDB集合对象

    # 清空集合
    config_db.clear()  # 无参数，返回None

    # 原生方法调用（通过__getattr__）
    insert_result = config_db.insert_one({'new_key': 'new_value'})  # 参数：文档dict
    # 返回值：MongoDB操作结果对象


# === 装饰器方法演示 ===
from nonebot.adapters.onebot.v11 import Event, MessageSegment


@check_command_enabled("mute")  # 参数：指令名称(str)，是否发送提示(bool)
def mute_handler(event: Event):
    # 处理指令逻辑
    pass


# IO效果：如果是群消息且指令被禁用，自动发送禁用提示消息

@permission_required(3)  # 参数：所需权限等级(int)
def admin_handler(event: Event):
    # 处理需要管理员权限的逻辑
    pass


# IO效果：如果权限不足，自动发送权限不足提示消息

# === get_context方法演示 ===
def context_demo(event: Event):
    user, args, group = get_context(event)
    # 返回值：
    # user: User对象（发送者）
    # args: 参数列表（自动解析文本参数和@用户）
    # group: Group对象或None（如果是私聊）

    # 示例消息解析：
    # 原始消息："/setperm @123456 3"
    # args结果：["123456", "3"]

    # 原始消息："/mute 123456 600"
    # args结果：["123456", "600"]


# === 其他工具方法演示 ===
def get_all_ops_demo():
    ops = get_all_ops()  # 无参数
    # 返回值：所有权限文档的列表
    # 示例结构：[{'id': 123456, 'permission': 3}, ...]


def config_db_demo():
    # 直接访问配置数据库
    config_data = config_db.find_one({'key': 'bot_name'})  # 参数：查询条件
    # 返回值：匹配的配置文档

# 重要: 由于装饰器技术原因, 使用装饰器的指令只能传入一个event参数
