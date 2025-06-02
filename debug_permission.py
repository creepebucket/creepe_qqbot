"""
权限调试脚本
用于测试用户权限检查功能
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'redstone_daily', 'plugins'))

from utils.user import User
from utils import get_database

def test_user_permission():
    """测试用户权限"""
    user_id = 3327018890
    server_name = 'slimefun'
    
    # 创建用户对象
    user = User(user_id)
    
    print(f'📋 测试用户权限检查')
    print(f'👤 用户ID: {user_id}')
    print(f'🖥️ 服务器名: {server_name}')
    print()
    
    # 直接查询数据库
    special_permissions = get_database('special_permissions').collection
    
    print('🔍 数据库查询结果:')
    perms = list(special_permissions.find({'user_id': user_id}))
    for perm in perms:
        print(f'  - {perm}')
    print()
    
    # 查询特定权限
    specific_perm = special_permissions.find_one({
        'user_id': user_id,
        'permission_name': server_name,
        'enabled': True
    })
    
    print(f'🎯 特定权限查询 (user_id={user_id}, permission_name="{server_name}", enabled=True):')
    print(f'  结果: {specific_perm}')
    print()
    
    # 测试has_special_permission方法
    try:
        import asyncio
        
        async def test_async():
            result = await user.has_special_permission(server_name)
            print(f'✅ has_special_permission("{server_name}") 结果: {result}')
            return result
        
        # 运行异步测试
        result = asyncio.run(test_async())
        print(f'🎪 最终权限检查结果: {result}')
        
    except Exception as e:
        print(f'❌ 权限检查出错: {str(e)}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_user_permission() 