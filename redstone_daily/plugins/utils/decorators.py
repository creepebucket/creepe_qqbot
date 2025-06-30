import json

import nonebot
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent

from .group import Group
from .user import User


def get_context(event: Event):
    """
    获取事件的上下文信息(发送者的utils.user.User对象, 指令参数, 群聊的utils.group.Group对象(如果是群聊消息))
    :param event: 事件对象
    :return: 事件的上下文信息(格式为[user, args, group])
    """

    def get_args(event: Event):
        """
        获取指令参数
        :param event: 事件对象
        :return: 指令参数列表
        """
        args = []
        json_data = json.loads(event.json())
        for msg in json_data.get('original_message', ''):  # 遍历消息列表
            if msg['type'] == 'text':  # 找到文本消息
                for i in msg['data']['text'].split(' '):  # 遍历文本

                    if i.startswith('/'):  # 忽略命令
                        continue

                    args.append(i)
            if msg['type'] == 'at':  # 找到@消息
                args.append(msg['data']['qq'])

        for i in args:  # 去除空白字符
            if i == '':
                args.remove(i)

        return args

    group = Group(event.group_id)

    if isinstance(event, GroupMessageEvent):
        if hasattr(event.sender, 'card') and event.sender.card:
            user = User(event.user_id, event.sender.card)
        else:
            user = User(event.user_id, event.sender.nickname)
    else:
        user = User(event.user_id, '')

    args = get_args(event)

    return [user, args, group]


def permission_required(perm):
    """
    权限检查装饰器
    支持两种权限类型：
    1. 数字权限（int）：检查用户在群组中的权限等级
    2. 字符串权限（str）：检查用户的全局特殊权限
    
    :param perm: 权限等级（int）或特殊权限名称（str）
    :return: 装饰器
    """

    def decorator(func):
        async def wrapper(event: Event):
            sender, arg, group = get_context(event)
            
            # 字符串权限：检查特殊权限
            if isinstance(perm, str):
                if await sender.has_special_permission(perm):
                    return await func(event)  # 有特殊权限，执行函数
                else:
                    # 特殊权限不足
                    bot = nonebot.get_bot()
                    if isinstance(event, GroupMessageEvent):
                        await bot.send_group_msg(group_id=event.group_id,
                                                 message=f'你需要「{perm}」特殊权限才能执行此操作')
                    else:
                        await sender.send(f'你需要「{perm}」特殊权限才能执行此操作')
                    return
            
            # 数字权限：检查群组权限等级
            elif isinstance(perm, int):
                if await sender.get_permission(group) >= perm:  # 判断用户权限是否满足要求
                    return await func(event)  # 执行函数
                else:  # 权限不足
                    bot = nonebot.get_bot()
                    if isinstance(event, GroupMessageEvent):
                        await bot.send_group_msg(group_id=event.group_id,
                                                 message=f'你需要{perm}级权限才能执行此操作')  # 发送权限不足消息
                    else:
                        await sender.send(f'你需要{perm}级权限才能执行此操作')
                    return
            
            else:
                raise ValueError('权限参数必须是整数或字符串')

        return wrapper

    return decorator


def check_command_enabled(command: str, send_disabled_message: bool = True):
    """
    指令启用检查装饰器
    :param command: 指令名称
    :param send_disabled_message: 是否发送指令禁用提示
    :return: 装饰器
    """

    def decorator(func):
        async def wrapper(event: Event):
            sender, arg, group = get_context(event)

            if not group.is_command_enabled(command):
                if not send_disabled_message:
                    return

                bot = nonebot.get_bot()
                await bot.send_group_msg(
                    group_id=group.id,
                    message=f'指令 {command} 在此群组已被禁用'
                )
                return  # 阻止执行被装饰函数

            # 非群消息或指令已启用时正常执行
            return await func(event)

        return wrapper

    return decorator


def check_params(param_configs: list):
    """
    参数检查装饰器
    
    参数配置格式:
    [
        {'str': '参数描述'},           # 必选字符串参数
        {'int': '参数描述'},           # 必选整数参数  
        {'float': '参数描述'},         # 必选浮点数参数
        {'optional_str': '参数描述'},  # 可选字符串参数
        {'optional_int': '参数描述'},  # 可选整数参数
        {'optional_float': '参数描述'} # 可选浮点数参数
    ]
    
    :param param_configs: 参数配置列表
    :return: 装饰器
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
                
                bot = nonebot.get_bot()
                if isinstance(event, GroupMessageEvent):
                    await bot.send_group_msg(group_id=event.group_id, message=error_msg)
                else:
                    await user.send(error_msg)
                return
            
            # 验证参数类型 - 仅做验证，不存储结果
            for i, param_config in enumerate(required_params):
                if i >= len(args):
                    break
                    
                arg_value = args[i]
                param_type = param_config['type']
                param_desc = param_config['description']
                
                try:
                    _validate_param_type(arg_value, param_type, param_desc)
                except ValueError as e:
                    error_msg = f'❌ {str(e)}'
                    
                    bot = nonebot.get_bot()
                    if isinstance(event, GroupMessageEvent):
                        await bot.send_group_msg(group_id=event.group_id, message=error_msg)
                    else:
                        await user.send(error_msg)
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
                    _validate_param_type(arg_value, param_type, param_desc)
                except ValueError as e:
                    error_msg = f'❌ {str(e)}'
                    
                    bot = nonebot.get_bot()
                    if isinstance(event, GroupMessageEvent):
                        await bot.send_group_msg(group_id=event.group_id, message=error_msg)
                    else:
                        await user.send(error_msg)
                    return
            
            # 参数验证通过，执行原函数
            return await func(event)
        
        return wrapper
    return decorator


def _validate_param_type(value: str, param_type: str, param_desc: str):
    """
    验证参数类型
    
    :param value: 参数值
    :param param_type: 参数类型 ('str', 'int', 'float')
    :param param_desc: 参数描述
    :return: 转换后的参数值
    :raises ValueError: 参数类型验证失败
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


def get_validated_args(event: Event) -> list:
    """
    获取经过check_params装饰器验证的参数
    
    :param event: Event对象
    :return: 验证后的参数列表
    """
    return getattr(event, '_validated_args', [])
