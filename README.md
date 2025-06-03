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

#### check_params 装饰器实现
```python
def check_params(param_configs: list):
    """
    参数检查装饰器
    
    实现逻辑:
    1. 通过get_context()获取用户输入的参数
    2. 根据配置检查参数类型和必选/可选状态
    3. 参数不符合要求时自动发送错误提示
    
    参数配置格式:
    [
        {'str': '参数描述'},           # 必选字符串参数
        {'int': '参数描述'},           # 必选整数参数  
        {'float': '参数描述'},         # 必选浮点数参数
        {'optional_str': '参数描述'},  # 可选字符串参数
        {'optional_int': '参数描述'},  # 可选整数参数
        {'optional_float': '参数描述'}, # 可选浮点数参数
    ]
    
    使用示例:
    @check_params([
        {'str': '用户名称'},
        {'int': '积分数量'},
        {'optional_int': '倍数'}
    ])
    """
    def decorator(func):
        async def wrapper(event: Event):
            user, args, group = get_context(event)
            
            # 解析参数配置
            required_params = []
            optional_params = []
            
            for config in param_configs:
                for param_type, description in config.items():
                    if param_type.startswith('optional_'):
                        # 可选参数
                        actual_type = param_type.replace('optional_', '')
                        optional_params.append({
                            'type': actual_type,
                            'description': description
                        })
                    else:
                        # 必选参数
                        required_params.append({
                            'type': param_type,
                            'description': description
                        })
            
            # 检查必选参数数量
            total_required = len(required_params)
            if len(args) < total_required:
                missing_params = []
                for i in range(len(args), total_required):
                    missing_params.append(required_params[i]['description'])
                
                error_msg = f'❌ 缺少必要参数: {", ".join(missing_params)}'
                await func.__self__.send(error_msg)
                return
            
            # 验证参数类型
            validated_args = []
            
            # 验证必选参数
            for i, param_config in enumerate(required_params):
                if i >= len(args):
                    break
                    
                arg_value = args[i]
                param_type = param_config['type']
                param_desc = param_config['description']
                
                try:
                    validated_value = _validate_param_type(arg_value, param_type, param_desc)
                    validated_args.append(validated_value)
                except ValueError as e:
                    await func.__self__.send(f'❌ {str(e)}')
                    return
            
            # 验证可选参数
            optional_start_index = total_required
            for i, param_config in enumerate(optional_params):
                arg_index = optional_start_index + i
                if arg_index >= len(args):
                    break
                    
                arg_value = args[arg_index]
                param_type = param_config['type']
                param_desc = param_config['description']
                
                try:
                    validated_value = _validate_param_type(arg_value, param_type, param_desc)
                    validated_args.append(validated_value)
                except ValueError as e:
                    await func.__self__.send(f'❌ {str(e)}')
                    return
            
            # 将验证后的参数添加到event对象中，供下游使用
            event._validated_args = validated_args
            
            return await func(event)
        
        return wrapper
    return decorator

def _validate_param_type(value: str, param_type: str, param_desc: str):
    """
    验证参数类型
    
    Args:
        value: 参数值
        param_type: 参数类型 ('str', 'int', 'float')
        param_desc: 参数描述
        
    Returns:
        转换后的参数值
        
    Raises:
        ValueError: 参数类型验证失败
    """
    if param_type == 'str':
        # 字符串参数直接返回
        if not value.strip():
            raise ValueError(f'参数 "{param_desc}" 不能为空')
        return value.strip()
    
    elif param_type == 'int':
        # 整数参数
        try:
            return int(value)
        except ValueError:
            raise ValueError(f'参数 "{param_desc}" 必须是整数，当前值: {value}')
    
    elif param_type == 'float':
        # 浮点数参数
        try:
            return float(value)
        except ValueError:
            raise ValueError(f'参数 "{param_desc}" 必须是数字，当前值: {value}')
    
    else:
        raise ValueError(f'不支持的参数类型: {param_type}')

# 获取验证后的参数的辅助函数
def get_validated_args(event: Event) -> list:
    """
    获取经过check_params装饰器验证的参数
    
    Args:
        event: Event对象
        
    Returns:
        list: 验证后的参数列表
        
    Example:
        @check_params([{'str': '用户名'}, {'int': '积分'}])
        async def my_command(event: Event):
            args = get_validated_args(event)
            username = args[0]  # str类型
            score = args[1]     # int类型
    """
    return getattr(event, '_validated_args', [])

#### check_params 装饰器

**功能**: 自动验证命令参数类型和必选/可选状态

**输入**: 参数配置列表，定义每个参数的类型和描述
```python
[
    {'str': '参数描述'},           # 必选字符串参数
    {'int': '参数描述'},           # 必选整数参数  
    {'float': '参数描述'},         # 必选浮点数参数
    {'optional_str': '参数描述'},  # 可选字符串参数
    {'optional_int': '参数描述'},  # 可选整数参数
    {'optional_float': '参数描述'} # 可选浮点数参数
]
```

**输出**: 
- 参数验证失败时自动发送错误提示
- 验证成功时将转换后的参数存储到 `event._validated_args` 中

**使用示例**:
```python
from redstone_daily.plugins.utils import check_params, get_validated_args

@your_command.handle()
@check_params([
    {'str': '用户名称'},
    {'int': '积分数量'},
    {'optional_int': '倍数'}
])
async def handle_command(event: Event):
    # 获取验证后的参数
    args = get_validated_args(event)
    username = args[0]    # str类型，已验证非空
    score = args[1]       # int类型，已转换
    multiplier = args[2] if len(args) > 2 else 1  # 可选参数
    
    # 业务逻辑处理...

**错误提示示例**:
- 缺少参数: `❌ 缺少必要参数: 积分数量`
- 类型错误: `❌ 参数 "积分数量" 必须是整数，当前值: abc`
- 空字符串: `❌ 参数 "用户名称" 不能为空`

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
    check_params,
    get_context, 
    get_database,
    permission_required
)

# 帮助信息注册
add_info('命令名', '命令描述和使用方法')

# 命令处理器
plugin_command = on_command('命令名', priority=5, block=True)

@plugin_command.handle()
@check_command_enabled('命令名')
@check_params([
    {'str': '用户名称'},
    {'int': '积分数量'},
    {'optional_int': '倍数'}
])
async def handle_plugin_command(event: Event):
    """
    插件主处理函数
    
    Args:
        event: NoneBot事件对象
    """
    try:
        # 参数已通过验证，正常获取上下文
        user, args, group = get_context(event)
        username = args[0]    # str类型，已验证非空
        score = int(args[1])  # 已验证为整数格式
        multiplier = int(args[2]) if len(args) > 2 else 1  # 可选参数
        
        # 业务逻辑处理
        result = await process_business_logic(username, score, multiplier, user, group)
        
        # 发送结果
        await plugin_command.send(result)
        
    except Exception as e:
        # 记录错误日志
        import logging
        logging.error(f'插件执行错误: {str(e)}', exc_info=True)
        await plugin_command.send('系统错误，请稍后重试')

async def process_business_logic(username: str, score: int, multiplier: int, user, group):
    """
    业务逻辑处理函数
    
    Args:
        username: 用户名称（已验证的字符串）
        score: 积分数量（已验证的整数）
        multiplier: 倍数（已验证的整数）
        user: User对象
        group: Group对象
        
    Returns:
        str: 处理结果
    """
    final_score = score * multiplier
    return f'用户 {username} 获得 {final_score} 积分'