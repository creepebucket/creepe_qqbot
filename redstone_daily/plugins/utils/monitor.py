#!/usr/bin/env python3
import psutil
import shutil
import time
import pynvml  # 用于GPU监控
from collections import defaultdict


def get_system_stats(duration=10):
    """
    收集系统资源使用统计数据
    :param duration: 监控持续时间(秒)
    :return: 包含所有资源统计数据的字典
    """
    # 初始化数据结构
    stats = {
        'cpu': [],
        'memory': [],
        'network': {'sent': [], 'recv': []},
        'disk_io': {'read': [], 'write': []},
        'gpu': defaultdict(lambda: {'gpu_usage': [], 'mem_used': []})
    }

    # 获取初始网络和磁盘IO计数器
    net_start = psutil.net_io_counters()
    disk_io_start = psutil.disk_io_counters()
    gpu_initialized = False

    # 尝试初始化GPU
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        gpu_initialized = True
    except:
        device_count = 0

    # 收集数据
    for _ in range(duration):
        # CPU使用率
        stats['cpu'].append(psutil.cpu_percent(interval=1))

        # 内存使用率
        mem = psutil.virtual_memory()
        stats['memory'].append(mem.percent)

        # 网络IO
        net_end = psutil.net_io_counters()
        stats['network']['sent'].append((net_end.bytes_sent - net_start.bytes_sent) / (1024 ** 2))
        stats['network']['recv'].append((net_end.bytes_recv - net_start.bytes_recv) / (1024 ** 2))
        net_start = net_end

        # 磁盘IO
        disk_io_end = psutil.disk_io_counters()
        stats['disk_io']['read'].append((disk_io_end.read_bytes - disk_io_start.read_bytes) / (1024 ** 2))
        stats['disk_io']['write'].append((disk_io_end.write_bytes - disk_io_start.write_bytes) / (1024 ** 2))
        disk_io_start = disk_io_end

        # GPU使用率
        if gpu_initialized:
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                stats['gpu'][i]['gpu_usage'].append(util.gpu)
                stats['gpu'][i]['mem_used'].append(mem_info.used / (1024 ** 2))

    # 获取静态信息（只执行一次）
    static_info = {
        'memory_total': round(psutil.virtual_memory().total / (1024 ** 3), 2),
        'disks': get_disk_usage(),
        'gpu_info': get_gpu_static_info() if gpu_initialized else []
    }

    # 计算统计数据
    def calculate_stats(values):
        if not values:
            return None
        return {
            'avg': round(sum(values) / len(values), 2),
            'max': round(max(values), 2),
            'min': round(min(values), 2)
        }

    # 处理GPU数据
    gpu_stats = {}
    for idx, data in stats['gpu'].items():
        gpu_stats[idx] = {
            'gpu_usage': calculate_stats(data['gpu_usage']),
            'mem_used': calculate_stats(data['mem_used'])
        }

    # 返回最终结果
    return {
        'cpu': calculate_stats(stats['cpu']),
        'memory': {
            'percent': calculate_stats(stats['memory']),
            'total_gb': static_info['memory_total']
        },
        'network': {
            'sent': calculate_stats(stats['network']['sent']),
            'recv': calculate_stats(stats['network']['recv'])
        },
        'disk_io': {
            'read': calculate_stats(stats['disk_io']['read']),
            'write': calculate_stats(stats['disk_io']['write'])
        },
        'disks': static_info['disks'],
        'gpu': gpu_stats,
        'gpu_info': static_info['gpu_info']
    }


def get_disk_usage():
    """获取物理磁盘使用情况（过滤loop设备）"""
    disks = []
    for part in psutil.disk_partitions(all=False):
        # 过滤掉loop设备和不需要的文件系统
        if part.fstype and not part.device.startswith('/dev/loop'):
            try:
                usage = shutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total": round(usage.total / (1024 ** 3), 2),
                    "used": round(usage.used / (1024 ** 3), 2),
                    "free": round(usage.free / (1024 ** 3), 2),
                    "percent": round(usage.used / usage.total * 100, 1)
                })
            except Exception as e:
                # 忽略无法访问的挂载点
                continue
    return disks


def get_gpu_static_info():
    """获取GPU静态信息"""
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        gpus = []

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            # 处理不同版本的pynvml返回类型
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

            gpus.append({
                "index": i,
                "name": name,
                "memory_total": round(mem_info.total / (1024 ** 2), 2)  # MB
            })
        return gpus
    except Exception as e:
        return f"GPU信息不可用: {str(e)}"


def print_stats(stats):
    """打印统计结果"""
    print("=" * 50)
    print("系统资源使用统计 (10秒平均值/最大/最小值)")
    print("=" * 50)

    # CPU
    cpu = stats['cpu']
    print(f"CPU使用率: {cpu['avg']}% (Min: {cpu['min']}%, Max: {cpu['max']}%)")

    # 内存
    mem = stats['memory']
    print(f"\n内存使用: {mem['percent']['avg']}% (Min: {mem['percent']['min']}%, Max: {mem['percent']['max']}%)")
    print(f"内存总量: {mem['total_gb']}GB")

    # 网络
    net = stats['network']
    print("\n网络流量:")
    print(f"  上传: {net['sent']['avg']}MB/s (Min: {net['sent']['min']}, Max: {net['sent']['max']})")
    print(f"  下载: {net['recv']['avg']}MB/s (Min: {net['recv']['min']}, Max: {net['recv']['max']})")

    # 磁盘IO
    disk_io = stats['disk_io']
    print("\n磁盘IO:")
    print(f"  读取: {disk_io['read']['avg']}MB/s (Min: {disk_io['read']['min']}, Max: {disk_io['read']['max']})")
    print(f"  写入: {disk_io['write']['avg']}MB/s (Min: {disk_io['write']['min']}, Max: {disk_io['write']['max']})")

    # 磁盘使用
    print("\n磁盘使用情况:")
    for disk in stats['disks']:
        print(f"  {disk['device']} ({disk['mountpoint']}): {disk['percent']}% 已用")

    # GPU
    if stats['gpu']:
        print("\nGPU使用情况:")
        for idx, gpu in stats['gpu'].items():
            gpu_info = next((g for g in stats['gpu_info'] if g['index'] == idx), {})
            name = gpu_info.get('name', f"GPU{idx}")
            mem_total = gpu_info.get('memory_total', '?')

            print(f"  {name}:")
            print(
                f"    GPU负载: {gpu['gpu_usage']['avg']}% (Min: {gpu['gpu_usage']['min']}%, Max: {gpu['gpu_usage']['max']}%)")
            print(
                f"    显存使用: {gpu['mem_used']['avg']}MB (Min: {gpu['mem_used']['min']}, Max: {gpu['mem_used']['max']}) / {mem_total}MB")
    else:
        print("\nGPU: 未检测到或不可用")

    print("=" * 50)


if __name__ == "__main__":
    # 收集10秒数据并计算统计
    stats = get_system_stats(duration=10)

    # 打印结果
    print_stats(stats)