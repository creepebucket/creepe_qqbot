from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event

from redstone_daily.plugins.utils import get_context
from redstone_daily.plugins.utils.monitor import get_system_stats

command_infos = []


def add_info(name: str, desc: str):
    command_infos.append({'name': name, 'desc': desc})


help_matcher = on_command('help')
status_matcher = on_command('status')
add_info('status', '查看服务器性能监控指标')


@help_matcher.handle()
async def help_handler(event: Event):
    context = get_context(event)
    args = context[1]

    items_per_page = 5
    current_page = 1
    commands_to_show = command_infos
    keyword = None

    # 解析参数
    if args:
        try:
            # 尝试将第一个参数解析为页码
            current_page = int(args[0])
            args = args[1:]  # 剩余参数
        except ValueError:
            # 第一个参数是关键词
            keyword = args[0]
            commands_to_show = [cmd for cmd in command_infos if keyword.lower() in cmd['name'].lower()]
            args = args[1:]

            # 尝试解析第二个参数为页码
            if args:
                try:
                    current_page = int(args[0])
                except ValueError:
                    await help_matcher.finish('⚠️ 页码参数必须是数字')
                    return

    # 处理空命令列表的情况
    if not commands_to_show:
        msg = f'⚠️ 没有找到与 "{keyword}" 相关的命令' if keyword else '⚠️ 当前没有可用命令'
        await help_matcher.finish(msg)
        return

    # 计算分页信息
    total_commands = len(commands_to_show)
    total_pages = (total_commands + items_per_page - 1) // items_per_page

    # 校验页码有效性
    if current_page < 1 or current_page > total_pages:
        await help_matcher.finish(f'⚠️ 无效页码（有效范围：1-{total_pages}）')
        return

    # 构建帮助信息
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_commands = commands_to_show[start_index:end_index]

    help_msg = []
    if keyword:
        help_msg.append(f'🔍 搜索 "{keyword}" 结果（共 {total_commands} 条）：')
    else:
        help_msg.append('📚 可用命令列表：')

    for cmd in page_commands:
        help_msg.append(f'▪ /{cmd['name']} - {cmd['desc']}')

    help_msg.append(f'📖 页码：{current_page}/{total_pages}')

    # 添加翻页提示
    if total_pages > 1:
        help_msg.append('\n使用 /help [页码] 查看其他页面')
        if keyword:
            help_msg.append(f'使用 /help {keyword} [页码] 查看特定搜索结果的页面')

    await help_matcher.finish('\n'.join(help_msg))

@status_matcher.handle()
async def status_handler(event: Event):
    # user, args, group = get_context(event)
    
    await status_matcher.send('正在收集数据, 请等待10秒...')
    
    stats = get_system_stats()
    
    msg = ('=====服务器状态=====\n'
           '项目 | Avg | Min | Max')

    cpu = stats['cpu']
    msg += f'\nCPU/% > {cpu['avg']} | {cpu['min']} | {cpu['max']}\n'

    # 内存
    mem = stats['memory']
    msg += f'\nRAM/% > {mem['percent']['avg']} | {mem['percent']['min']} | {mem['percent']['max']}%'
    msg += f'\nRAM/GB > {mem['total_gb']}\n'

    # 网络
    net = stats['network']
    msg += f'\n↑NETWORK/MB > {net['sent']['avg']} | {net['sent']['min']} | {net['sent']['max']}'
    msg += f'\n↓NETWORK/MB > {net['recv']['avg']} | {net['recv']['min']} | {net['recv']['max']}\n'

    # 磁盘IO
    disk_io = stats['disk_io']
    msg += f'\n↑DISKIO/MB > {disk_io['read']['avg']} | {disk_io['read']['min']} | {disk_io['read']['max']}'
    msg += f'\n↓DISKIO/MB > {disk_io['write']['avg']} | {disk_io['write']['min']} | {disk_io['write']['max']}'

    # 磁盘使用
    for disk in stats['disks']:
        msg += f'\nSTORAGE[{disk['device']}] : [{disk['mountpoint']}]/% > {disk['percent']}\n'
        
    msg += '\n'

    # GPU
    if stats['gpu']:
        for idx, gpu in stats['gpu'].items():
            gpu_info = next((g for g in stats['gpu_info'] if g['index'] == idx), {})
            name = gpu_info.get('name', f'GPU{idx}')
            mem_total = gpu_info.get('memory_total', '?')

            msg += f'\nGPU[{idx}]/% > {gpu['gpu_usage']['avg']} | {gpu['gpu_usage']['min']} | {gpu['gpu_usage']['max']}'
            msg += f'\nVRAM[{idx}]:USED/MB {gpu['mem_used']['avg']} | {gpu['mem_used']['min']} | {gpu['mem_used']['max']} \nVRAM[{idx}]:TOTAL/MB > {mem_total}'

    await status_matcher.finish(msg)