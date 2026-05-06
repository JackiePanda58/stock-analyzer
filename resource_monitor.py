"""
系统资源监控脚本

监控API服务器的内存和CPU使用情况

使用方法:
python3 resource_monitor.py --pid PID --duration 300 --interval 5
"""
import argparse
import time
import os
import psutil
import json
from datetime import datetime


def get_process_info(pid: int) -> dict:
    """
    获取进程资源使用情况
    
    参数:
        pid: 进程ID
        
    返回:
        dict: 资源使用信息
    """
    try:
        process = psutil.Process(pid)
        
        # 内存信息
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        # CPU信息
        cpu_percent = process.cpu_percent(interval=0.1)
        cpu_count = process.cpu_num()
        
        # 线程信息
        thread_count = process.num_threads()
        
        return {
            "pid": pid,
            "status": process.status(),
            "memory_rss_mb": memory_info.rss / 1024 / 1024,
            "memory_vms_mb": memory_info.vms / 1024 / 1024,
            "memory_percent": memory_percent,
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "thread_count": thread_count,
            "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
        }
    except psutil.NoSuchProcess:
        return {"pid": pid, "error": "Process not found"}
    except psutil.AccessDenied:
        return {"pid": pid, "error": "Access denied"}


def monitor_process(pid: int, duration: int, interval: int, output_file: str):
    """
    监控进程资源使用
    
    参数:
        pid: 进程ID
        duration: 监控时长（秒）
        interval: 采样间隔（秒）
        output_file: 输出文件
    """
    print(f"开始监控进程 {pid}...")
    print(f"  监控时长: {duration}秒")
    print(f"  采样间隔: {interval}秒")
    print()
    
    samples = []
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        sample = get_process_info(pid)
        sample["timestamp"] = datetime.now().isoformat()
        sample["elapsed"] = time.time() - start_time
        samples.append(sample)
        
        # 打印当前状态
        if "error" not in sample:
            print(f"  [{sample['elapsed']:.0f}s] "
                  f"内存: {sample['memory_rss_mb']:.1f}MB ({sample['memory_percent']:.1f}%) | "
                  f"CPU: {sample['cpu_percent']:.1f}% | "
                  f"线程: {sample['thread_count']}")
        else:
            print(f"  [{sample['elapsed']:.0f}s] 错误: {sample['error']}")
            break
        
        time.sleep(interval)
    
    # 统计结果
    if samples and "error" not in samples[-1]:
        avg_memory = sum(s["memory_rss_mb"] for s in samples if "error" not in s) / len(samples)
        max_memory = max(s["memory_rss_mb"] for s in samples if "error" not in s)
        avg_cpu = sum(s["cpu_percent"] for s in samples if "error" not in s) / len(samples)
        max_cpu = max(s["cpu_percent"] for s in samples if "error" not in s)
        
        print()
        print("=" * 50)
        print("监控结果:")
        print("=" * 50)
        print(f"  样本数: {len(samples)}")
        print(f"  平均内存: {avg_memory:.1f}MB")
        print(f"  最大内存: {max_memory:.1f}MB")
        print(f"  平均CPU: {avg_cpu:.1f}%")
        print(f"  最大CPU: {max_cpu:.1f}%")
        print("=" * 50)
    
    # 保存结果
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "pid": pid,
        "duration": duration,
        "interval": interval,
        "samples": samples
    }
    
    with open(output_file, "w") as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="系统资源监控")
    parser.add_argument("--pid", type=int, required=True, help="进程ID")
    parser.add_argument("--duration", type=int, default=300, help="监控时长（秒）")
    parser.add_argument("--interval", type=int, default=5, help="采样间隔（秒）")
    parser.add_argument("--output", default="resource_monitor_result.json", help="输出文件")
    
    args = parser.parse_args()
    
    monitor_process(args.pid, args.duration, args.interval, args.output)
