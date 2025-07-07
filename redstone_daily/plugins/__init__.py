from redstone_daily.plugins.utils import User


async def check_server_permission_async(user: User, server_name: str, group) -> bool:
    """
    检查用户是否有指定服务器的特殊权限

    Args:
        user: 用户对象
        server_name: 服务器名称
        group: 群组对象（保留参数以保持接口一致性）

    Returns:
        bool: 是否有权限
    """
    try:
        return await user.has_special_permission(server_name)
    except Exception:
        return False
