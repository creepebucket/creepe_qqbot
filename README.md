# AIbot 轮子使用指南与代码规范

## 🛠️ 核心轮子系统

> 重要: 使用装饰器的指令handle方法, 因为技术原因只能传入一个event参数, 获取其他参数请使用get_context()!

### 数据库轮子 (`utils/database.py`)

#### 基本使用
```python
from redstone_daily.plugins.utils import get_database

# 获取数据库连接
db = get_database('collection_name')
collection = db.get_db()

# 这里的collection就是一个pymongo的集合对象
```

### 上下文解析轮子 (`utils/__init__.py`)

#### get_context() 实现原理
```python
def get_context(event: Event):
    """
    解析事件上下文，返回 [user, args, group]
    
    实现逻辑:
    1. 解析消息中的文本和@信息
    2. 创建User和Group对象
    3. 过滤命令前缀，提取纯参数
    """
    
    def get_args(event: Event):
        args = []
        json_data = json.loads(event.json())
        
        for msg in json_data.get('original_message', ''):
            if msg['type'] == 'text':
                # 分割文本，跳过以/开头的命令
                for text in msg['data']['text'].split(' '):
                    if not text.startswith('/') and text.strip():
                        args.append(text.strip())
                        
            elif msg['type'] == 'at':
                # 提取@的QQ号
                args.append(msg['data']['qq'])
        
        return [arg for arg in args if arg]  # 过滤空字符串
    
    user = User(event.user_id)
    group = Group(event.group_id) if hasattr(event, 'group_id') else None
    args = get_args(event)
    
    return [user, args, group]
```

#### 使用技巧
```python
@your_command.handle()
async def handle_command(event: Event):
    user, args, group = get_context(event)
    
    # 参数解析技巧
    if not args:
        await your_command.send('缺少参数')
        return
    
    # 处理@用户
    if args and args[0].isdigit():
        target_user_id = int(args[0])
        target_user = User(target_user_id)
    
    # 处理多个参数
    if len(args) >= 2:
        action, value = args[0], args[1]
    
    # 处理可选参数
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
```

### 权限管理轮子 (`utils/user.py`)

#### User类详细实现
```python
class User:
    def __init__(self, id: int, nickname: str = ""):
        self.id = id
        self._nickname = nickname
    
    async def get_permission(self, group) -> int:
        """
        权限获取逻辑:
        1. 优先从数据库查询
        2. 数据库无记录时，通过API获取群角色
        3. 根据角色自动分配权限并保存
        """
        # 数据库查询
        permission_doc = permissions.find_one({
            'id': self.id, 
            'group': group.id
        })
        
        if permission_doc:
            return permission_doc['permission']
        
        # API查询群角色
        try:
            bot = nonebot.get_bot()
            member_info = await bot.get_group_member_info(
                group_id=group.id,
                user_id=self.id
            )
            
            # 角色权限映射
            role_permissions = {
                'owner': 5,    # 群主
                'admin': 3,    # 管理员
                'member': 0    # 普通成员
            }
            
            role = member_info.get('role', 'member')
            permission = role_permissions.get(role, 0)
            
            # 保存到数据库
            self.set_permission(permission, group)
            return permission
            
        except Exception as e:
            return 0  # 默认权限
    
    def set_permission(self, permission: int, group):
        """设置用户权限"""
        permissions.update_one(
            {'id': self.id, 'group': group.id},
            {'$set': {'permission': permission}},
            upsert=True
        )
```

#### 权限使用模式
```python
# 手动权限检查
@your_command.handle()
async def handle_command(event: Event):
    user, args, group = get_context(event)
    
    user_permission = await user.get_permission(group)
    if user_permission < 3:
        await your_command.send('权限不足，需要管理员权限')
        return
    
    # 执行管理员操作...

# 批量权限操作
async def batch_set_permissions(user_ids: list, permission: int, group):
    """批量设置权限"""
    for user_id in user_ids:
        user = User(user_id)
        user.set_permission(permission, group)
```

### 装饰器轮子 (`utils/decorators.py`)

#### permission_required 装饰器实现
```python
def permission_required(perm: int):
    """
    权限检查装饰器
    
    实现原理:
    1. 包装原函数
    2. 执行前检查用户权限
    3. 权限不足时发送提示并阻止执行
    """
    def decorator(func):
        async def wrapper(event: Event):
            user, args, group = get_context(event)
            
            # 权限检查
            user_perm = await user.get_permission(group)
            if user_perm < perm:
                # 发送权限不足消息
                bot = nonebot.get_bot()
                if isinstance(event, GroupMessageEvent):
                    await bot.send_group_msg(
                        group_id=event.group_id,
                        message=f'需要 {perm} 级权限才能执行此操作'
                    )
                else:
                    await user.send(f'需要 {perm} 级权限才能执行此操作')
                return
            
            # 权限满足，执行原函数
            return await func(event)
        
        return wrapper
    return decorator
```

#### check_command_enabled 装饰器实现
```python
def check_command_enabled(command: str, send_disabled_message: bool = True):
    """
    命令启用检查装饰器
    
    实现逻辑:
    1. 检查群组配置中命令是否被禁用
    2. 禁用时可选择是否发送提示
    3. 非群聊消息直接通过
    """
    def decorator(func):
        async def wrapper(event: Event):
            user, args, group = get_context(event)
            
            # 非群聊直接执行
            if not group:
                return await func(event)
            
            # 检查命令是否启用
            if not group.is_command_enabled(command):
                if send_disabled_message:
                    bot = nonebot.get_bot()
                    await bot.send_group_msg(
                        group_id=group.id,
                        message=f'命令 {command} 在此群组已被禁用'
                    )
                return
            
            return await func(event)
        
        return wrapper
    return decorator
```

#### 自定义装饰器模式
```python
def cooldown(seconds: int):
    """冷却时间装饰器"""
    last_use = {}
    
    def decorator(func):
        async def wrapper(event: Event):
            user, args, group = get_context(event)
            key = f'{user.id}_{group.id if group else "private"}'
            
            now = time.time()
            if key in last_use and now - last_use[key] < seconds:
                remaining = seconds - (now - last_use[key])
                await func.__self__.send(f'命令冷却中，还需等待 {remaining:.1f} 秒')
                return
            
            last_use[key] = now
            return await func(event)
        
        return wrapper
    return decorator

def rate_limit(max_calls: int, window: int):
    """频率限制装饰器"""
    call_history = {}
    
    def decorator(func):
        async def wrapper(event: Event):
            user, args, group = get_context(event)
            key = f'{user.id}_{group.id if group else "private"}'
            
            now = time.time()
            if key not in call_history:
                call_history[key] = []
            
            # 清理过期记录
            call_history[key] = [
                t for t in call_history[key] 
                if now - t < window
            ]
            
            # 检查频率限制
            if len(call_history[key]) >= max_calls:
                await func.__self__.send(f'调用过于频繁，请 {window} 秒后再试')
                return
            
            call_history[key].append(now)
            return await func(event)
        
        return wrapper
    return decorator
```

## 📋 代码规范

### 插件结构规范

#### 标准插件模板
```python
"""
插件名称: 功能描述
作者: 作者名
版本: 1.0.0
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event, MessageSegment
from redstone_daily.plugins.helper import add_info
from redstone_daily.plugins.utils import (
    check_command_enabled, 
    get_context, 
    get_database,
    permission_required
)

# 帮助信息注册
add_info('命令名', '命令描述和使用方法')

# 命令处理器
plugin_command = on_command('命令名', priority=5, block=True)

# 数据管理器
class PluginDataManager:
    """插件数据管理器"""
    
    def __init__(self):
        self.db = get_database('plugin_data')
        self.collection = self.db.get_db()
    
    def get_user_data(self, user_id: int) -> dict:
        """获取用户数据"""
        return self.collection.find_one({'user_id': user_id}) or {}
    
    def save_user_data(self, user_id: int, data: dict):
        """保存用户数据"""
        self.collection.update_one(
            {'user_id': user_id},
            {'$set': data},
            upsert=True
        )

# 全局数据管理器实例
data_manager = PluginDataManager()

@plugin_command.handle()
@check_command_enabled('命令名')
async def handle_plugin_command(event: Event):
    """
    插件主处理函数
    
    Args:
        event: NoneBot事件对象
    """
    try:
        user, args, group = get_context(event)
        
        # 参数验证
        if not args:
            await plugin_command.send('请提供必要参数')
            return
        
        # 业务逻辑处理
        result = await process_business_logic(user, args, group)
        
        # 发送结果
        await plugin_command.send(result)
        
    except ValueError as e:
        await plugin_command.send(f'参数错误: {str(e)}')
    except PermissionError:
        await plugin_command.send('权限不足')
    except Exception as e:
        # 记录错误日志
        import logging
        logging.error(f'插件执行错误: {str(e)}', exc_info=True)
        await plugin_command.send('系统错误，请稍后重试')

async def process_business_logic(user, args, group):
    """
    业务逻辑处理函数
    
    Args:
        user: User对象
        args: 参数列表
        group: Group对象
        
    Returns:
        str: 处理结果
    """
    # 具体业务逻辑实现
    pass
```

### 命名规范

#### 变量命名
```python
# 好的命名
user_id = 123
game_score = 100
is_admin = True
user_data_list = []
max_retry_count = 3

# 避免的命名
uid = 123          # 不够明确
s = 100           # 无意义
flag = True       # 不明确
data = []         # 太泛化
MAX = 3           # 不明确
```

#### 函数命名
```python
# 好的命名
def get_user_permission(user_id: int, group_id: int) -> int:
    """获取用户在群组中的权限"""
    pass

def validate_game_answer(answer: str, correct_answer: str) -> bool:
    """验证游戏答案是否正确"""
    pass

def send_welcome_message(user_id: int):
    """发送欢迎消息"""
    pass

# 避免的命名
def get_perm():        # 缩写不明确
def check():           # 太泛化
def do_something():    # 无意义
```

#### 类命名
```python
# 好的命名
class GameDataManager:
    """游戏数据管理器"""
    pass

class UserPermissionChecker:
    """用户权限检查器"""
    pass

class MessageFormatter:
    """消息格式化器"""
    pass
```

### 注释规范

#### 函数注释
```python
def calculate_game_score(base_score: int, multiplier: float, bonus: int = 0) -> int:
    """
    计算游戏得分
    
    Args:
        base_score: 基础分数
        multiplier: 倍数
        bonus: 奖励分数，默认为0
        
    Returns:
        int: 计算后的总分数
        
    Raises:
        ValueError: 当base_score为负数时
        
    Example:
        >>> calculate_game_score(100, 1.5, 50)
        200
    """
    if base_score < 0:
        raise ValueError('基础分数不能为负数')
    
    return int(base_score * multiplier) + bonus
```

#### 类注释
```python
class GameSession:
    """
    游戏会话管理器
    
    负责管理单个游戏会话的状态，包括:
    - 游戏数据的存储和读取
    - 游戏状态的更新
    - 游戏结果的计算
    
    Attributes:
        session_id: 会话ID
        user_id: 用户ID
        game_data: 游戏数据字典
        
    Example:
        session = GameSession(123, 456)
        session.start_game()
        session.update_score(100)
    """
    
    def __init__(self, session_id: int, user_id: int):
        """
        初始化游戏会话
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
        """
        self.session_id = session_id
        self.user_id = user_id
        self.game_data = {}
```

### 错误处理规范

#### 异常处理模式
```python
@your_command.handle()
async def handle_command(event: Event):
    """命令处理函数"""
    try:
        user, args, group = get_context(event)
        
        # 参数验证
        if not args:
            raise ValueError('缺少必要参数')
        
        if not args[0].isdigit():
            raise ValueError('参数必须是数字')
        
        # 权限检查
        if await user.get_permission(group) < 3:
            raise PermissionError('权限不足')
        
        # 业务逻辑
        result = await process_logic(args)
        await your_command.send(f'处理成功: {result}')
        
    except ValueError as e:
        await your_command.send(f'❌ 参数错误: {str(e)}')
    except PermissionError as e:
        await your_command.send(f'❌ {str(e)}')
    except DatabaseError as e:
        await your_command.send('❌ 数据库错误，请稍后重试')
        logging.error(f'数据库错误: {str(e)}')
    except Exception as e:
        await your_command.send('❌ 系统错误，请联系管理员')
        logging.error(f'未知错误: {str(e)}', exc_info=True)
```

#### 自定义异常
```python
class PluginError(Exception):
    """插件基础异常"""
    pass

class GameError(PluginError):
    """游戏相关异常"""
    pass

class UserNotFoundError(PluginError):
    """用户未找到异常"""
    pass

class InvalidGameStateError(GameError):
    """无效游戏状态异常"""
    pass

# 使用示例
def start_game(user_id: int):
    """开始游戏"""
    user_data = get_user_data(user_id)
    if not user_data:
        raise UserNotFoundError(f'用户 {user_id} 不存在')
    
    if user_data.get('in_game'):
        raise InvalidGameStateError('用户已在游戏中')
```

### 数据库操作规范

#### 查询优化
```python
# 好的做法：使用索引字段查询
def get_user_by_id(user_id: int):
    """通过用户ID查询（user_id应建立索引）"""
    return collection.find_one({'user_id': user_id})

# 好的做法：限制返回字段
def get_user_scores():
    """只获取需要的字段"""
    return collection.find({}, {'user_id': 1, 'score': 1, '_id': 0})

# 好的做法：使用批量操作
def update_multiple_users(updates: list):
    """批量更新用户数据"""
    bulk_ops = [
        UpdateOne({'user_id': update['user_id']}, {'$set': update['data']})
        for update in updates
    ]
    collection.bulk_write(bulk_ops)

# 避免：全表扫描
def bad_query():
    """避免这种查询方式"""
    return collection.find({'nickname': {'$regex': 'test'}})  # 未建索引的模糊查询
```

#### 数据验证
```python
def save_user_data(user_id: int, data: dict):
    """
    保存用户数据（带验证）
    
    Args:
        user_id: 用户ID
        data: 用户数据
        
    Raises:
        ValueError: 数据验证失败
    """
    # 数据验证
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError('用户ID必须是正整数')
    
    if not isinstance(data, dict):
        raise ValueError('数据必须是字典类型')
    
    # 字段验证
    required_fields = ['score', 'level']
    for field in required_fields:
        if field not in data:
            raise ValueError(f'缺少必要字段: {field}')
    
    # 数据类型验证
    if not isinstance(data['score'], int) or data['score'] < 0:
        raise ValueError('分数必须是非负整数')
    
    # 保存数据
    collection.update_one(
        {'user_id': user_id},
        {'$set': {**data, 'updated_at': datetime.now()}},
        upsert=True
    )
```

### 性能优化规范

#### 缓存使用
```python
from functools import lru_cache
import time

class CachedDataManager:
    """带缓存的数据管理器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存
    
    def get_user_data(self, user_id: int) -> dict:
        """获取用户数据（带缓存）"""
        cache_key = f'user_{user_id}'
        now = time.time()
        
        # 检查缓存
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if now - timestamp < self.cache_ttl:
                return data
        
        # 从数据库获取
        data = collection.find_one({'user_id': user_id}) or {}
        
        # 更新缓存
        self.cache[cache_key] = (data, now)
        
        return data
    
    def invalidate_cache(self, user_id: int):
        """清除用户缓存"""
        cache_key = f'user_{user_id}'
        self.cache.pop(cache_key, None)

# 使用装饰器缓存
@lru_cache(maxsize=128)
def get_game_config(game_type: str) -> dict:
    """获取游戏配置（内存缓存）"""
    return collection.find_one({'type': 'config', 'game': game_type}) or {}
```

#### 异步操作
```python
import asyncio

async def batch_process_users(user_ids: list):
    """批量处理用户数据"""
    
    async def process_single_user(user_id: int):
        """处理单个用户"""
        try:
            # 模拟耗时操作
            await asyncio.sleep(0.1)
            return f'处理用户 {user_id} 完成'
        except Exception as e:
            return f'处理用户 {user_id} 失败: {str(e)}'
    
    # 并发处理，限制并发数
    semaphore = asyncio.Semaphore(10)  # 最多10个并发
    
    async def limited_process(user_id: int):
        async with semaphore:
            return await process_single_user(user_id)
    
    # 执行批量处理
    tasks = [limited_process(uid) for uid in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```