#!/usr/bin/env python3

import time
import psutil
import subprocess
import re
from datetime import datetime, timedelta

class SimpleMacOSMonitor:
    def __init__(self):
        # Track network activity for timeout (5 minutes = 300 seconds)
        self.network_last_activity = {}
        self.network_timeout = 300
        self.network_history = {}
        
        # Temperature monitoring capabilities
        self.sudo_available = False
        self.temperature_mode = 'estimate'
        
    def get_temperature(self):
        """Get CPU temperature using estimation"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            # Rough estimation for M1: idle ~35°C, full load ~80°C
            base_temp = 35
            load_temp = 45
            estimated_temp = base_temp + (cpu_percent / 100.0) * load_temp
            return {'CPU_Est': estimated_temp}
        except:
            return {'CPU_Est': 40}
    
    def get_uptime(self):
        """Get system uptime"""
        try:
            result = subprocess.run(['sysctl', '-n', 'kern.boottime'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                boot_match = re.search(r'sec = (\d+)', result.stdout)
                if boot_match:
                    boot_time = int(boot_match.group(1))
                    current_time = int(time.time())
                    uptime_seconds = current_time - boot_time
                    uptime_delta = timedelta(seconds=uptime_seconds)
                    days = uptime_delta.days
                    hours, remainder = divmod(uptime_delta.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        except:
            pass
        return "Unknown"
    
    def print_stats(self):
        """Print system stats in simple text format"""
        print("\n" + "="*60)
        print("macOS System Monitor (Simple Text Mode)")
        print("="*60)
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Uptime: {self.get_uptime()}")
        
        # CPU Usage
        try:
            cpu_usage = psutil.cpu_percent(interval=1, percpu=True)
            print(f"\nCPU Usage:")
            for i, usage in enumerate(cpu_usage):
                if i < 4:
                    core_type = f"P-Core {i}"
                else:
                    core_type = f"E-Core {i-4}"
                bar = "█" * int(usage/5) + "░" * (20-int(usage/5))
                print(f"  {core_type:8}: [{bar}] {usage:5.1f}%")
            
            avg_cpu = sum(cpu_usage) / len(cpu_usage)
            bar = "█" * int(avg_cpu/5) + "░" * (20-int(avg_cpu/5))
            print(f"  Average : [{bar}] {avg_cpu:5.1f}%")
        except Exception as e:
            print(f"CPU Error: {e}")
        
        # Memory
        try:
            mem = psutil.virtual_memory()
            bar = "█" * int(mem.percent/5) + "░" * (20-int(mem.percent/5))
            print(f"\nMemory:")
            print(f"  RAM      : [{bar}] {mem.percent:5.1f}%")
            print(f"  Used: {mem.used/(1024**3):.1f}GB / {mem.total/(1024**3):.1f}GB")
        except Exception as e:
            print(f"Memory Error: {e}")
        
        # Temperature
        try:
            temps = self.get_temperature()
            print(f"\nTemperature:")
            for name, temp in temps.items():
                temp_f = temp * 9/5 + 32
                print(f"  {name:8}: {temp:5.1f}°C ({temp_f:5.1f}°F)")
        except Exception as e:
            print(f"Temperature Error: {e}")
        
        # Network (only active interfaces)
        try:
            net_io = psutil.net_io_counters(pernic=True)
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            print(f"\nActive Network Interfaces:")
            active_count = 0
            for iface, counters in net_io.items():
                # Skip loopback
                if iface == 'lo0':
                    continue
                
                # Check if interface is up and has an address
                is_up = False
                has_address = False
                
                if iface in net_if_stats:
                    is_up = net_if_stats[iface].isup
                
                if iface in net_if_addrs:
                    for addr in net_if_addrs[iface]:
                        if addr.family == 2:  # AF_INET (IPv4)
                            if not addr.address.startswith('169.254.'):  # Skip link-local
                                has_address = True
                                break
                
                # Only show interfaces that are up and have activity or address
                if is_up and (has_address or counters.bytes_recv > 1024 or counters.bytes_sent > 1024):
                    rx_mb = counters.bytes_recv / (1024*1024)
                    tx_mb = counters.bytes_sent / (1024*1024)
                    status = "🟢" if has_address else "🟡"
                    print(f"  {status} {iface:8}: RX {rx_mb:8.1f}MB  TX {tx_mb:8.1f}MB")
                    active_count += 1
                    if active_count >= 3:  # Limit to 3 active interfaces
                        break
            
            if active_count == 0:
                print("  No active interfaces found")
        except Exception as e:
            print(f"Network Error: {e}")
        
        # Disk
        try:
            disk_usage = psutil.disk_usage('/')
            pct = (disk_usage.used / disk_usage.total) * 100
            bar = "█" * int(pct/5) + "░" * (20-int(pct/5))
            print(f"\nDisk Usage (/):")
            print(f"  Disk     : [{bar}] {pct:5.1f}%")
            print(f"  Used: {disk_usage.used/(1024**3):.1f}GB / {disk_usage.total/(1024**3):.1f}GB")
        except Exception as e:
            print(f"Disk Error: {e}")
        
        # Top processes
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            print(f"\nTop 5 Processes:")
            print(f"  {'PID':<8} {'Name':<20} {'CPU%':<6}")
            print(f"  {'-'*8} {'-'*20} {'-'*6}")
            for proc in processes[:5]:
                pid = proc.get('pid', 0)
                name = proc.get('name', 'Unknown')[:20]
                cpu_pct = proc.get('cpu_percent', 0) or 0
                print(f"  {pid:<8} {name:<20} {cpu_pct:<6.1f}")
        except Exception as e:
            print(f"Processes Error: {e}")

def main():
    print("macOS System Monitor - Simple Mode")
    print("Press Ctrl+C to stop")
    
    monitor = SimpleMacOSMonitor()
    
    try:
        while True:
            monitor.print_stats()
            print(f"\nPress Ctrl+C to stop...")
            time.sleep(3)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")

if __name__ == "__main__":
    main()