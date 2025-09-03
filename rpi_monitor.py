#!/usr/bin/env python3

import curses
import time
import os
import psutil
import subprocess
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

class RPiMonitor:
    def __init__(self):
        self.running = True
        self.screen = None
        self.update_interval = 1.0
        self.network_history = defaultdict(lambda: deque(maxlen=60))
        self.disk_history = defaultdict(lambda: deque(maxlen=60))
        
    def get_temperature(self):
        """Get CPU and GPU temperatures"""
        temps = {}
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp = float(f.read().strip()) / 1000
                temps['CPU'] = cpu_temp
        except:
            temps['CPU'] = 0
        
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                gpu_temp_str = result.stdout.strip().replace('temp=', '').replace("'C", '')
                temps['GPU'] = float(gpu_temp_str)
            else:
                temps['GPU'] = 0
        except:
            temps['GPU'] = 0
            
        return temps
    
    def get_network_stats(self):
        """Get network interface statistics"""
        stats = {}
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Skip header lines
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 17:
                        iface = parts[0].rstrip(':')
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        stats[iface] = {'rx': rx_bytes, 'tx': tx_bytes}
        except:
            pass
        return stats
    
    def get_disk_stats(self):
        """Get disk I/O statistics"""
        stats = {}
        try:
            with open('/proc/diskstats', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14 and not parts[2].startswith('ram'):
                        device = parts[2]
                        read_sectors = int(parts[5])
                        write_sectors = int(parts[9])
                        stats[device] = {'read': read_sectors, 'write': write_sectors}
        except:
            pass
        return stats
    
    def get_uptime(self):
        """Get system uptime"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                uptime_delta = timedelta(seconds=uptime_seconds)
                days = uptime_delta.days
                hours, remainder = divmod(uptime_delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        except:
            return "Unknown"
    
    def get_logged_users(self):
        """Get list of logged-in users"""
        users = []
        try:
            result = subprocess.run(['who'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if len(parts) >= 2:
                            users.append(f"{parts[0]} ({parts[1]})")
        except:
            pass
        return users
    
    def get_cpu_usage(self):
        """Get CPU utilization per core"""
        try:
            return psutil.cpu_percent(interval=None, percpu=True)
        except:
            return [0]
    
    def get_memory_usage(self):
        """Get memory utilization"""
        try:
            mem = psutil.virtual_memory()
            return {
                'total': mem.total,
                'used': mem.used,
                'available': mem.available,
                'percent': mem.percent
            }
        except:
            return {'total': 0, 'used': 0, 'available': 0, 'percent': 0}
    
    def get_top_processes(self):
        """Get top 5 processes by CPU usage"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            return processes[:5]
        except:
            return []
    
    def draw_bar(self, y, x, width, percentage, label=""):
        """Draw a horizontal bar chart"""
        try:
            filled = int(width * percentage / 100)
            bar = "█" * filled + "░" * (width - filled)
            self.screen.addstr(y, x, f"{label:<12} [{bar}] {percentage:5.1f}%")
        except:
            pass
    
    def draw_network_bars(self, start_y, net_stats):
        """Draw network activity bars"""
        row = start_y
        self.screen.addstr(row, 0, "Network Activity:", curses.A_BOLD)
        row += 1
        
        for iface, stats in net_stats.items():
            if iface != 'lo':  # Skip loopback
                history = self.network_history[iface]
                if len(history) >= 2:
                    prev_rx, prev_tx = history[-2]['rx'], history[-2]['tx']
                    curr_rx, curr_tx = stats['rx'], stats['tx']
                    
                    rx_rate = max(0, (curr_rx - prev_rx) / 1024)  # KB/s
                    tx_rate = max(0, (curr_tx - prev_tx) / 1024)  # KB/s
                    
                    max_rate = max(rx_rate, tx_rate, 1)
                    rx_pct = min(100, (rx_rate / max_rate) * 100)
                    tx_pct = min(100, (tx_rate / max_rate) * 100)
                    
                    self.screen.addstr(row, 2, f"{iface} RX:")
                    self.draw_bar(row, 12, 20, rx_pct, f"{rx_rate:6.1f} KB/s")
                    row += 1
                    self.screen.addstr(row, 2, f"{iface} TX:")
                    self.draw_bar(row, 12, 20, tx_pct, f"{tx_rate:6.1f} KB/s")
                    row += 1
                
                history.append(stats)
        
        return row
    
    def draw_disk_bars(self, start_y, disk_stats):
        """Draw disk activity bars"""
        row = start_y
        self.screen.addstr(row, 0, "Disk Activity:", curses.A_BOLD)
        row += 1
        
        for device, stats in disk_stats.items():
            if device.startswith(('sd', 'mmcblk', 'nvme')):
                history = self.disk_history[device]
                if len(history) >= 2:
                    prev_read, prev_write = history[-2]['read'], history[-2]['write']
                    curr_read, curr_write = stats['read'], stats['write']
                    
                    read_rate = max(0, (curr_read - prev_read) * 512 / 1024)  # KB/s
                    write_rate = max(0, (curr_write - prev_write) * 512 / 1024)  # KB/s
                    
                    max_rate = max(read_rate, write_rate, 1)
                    read_pct = min(100, (read_rate / max_rate) * 100)
                    write_pct = min(100, (write_rate / max_rate) * 100)
                    
                    self.screen.addstr(row, 2, f"{device} R:")
                    self.draw_bar(row, 12, 20, read_pct, f"{read_rate:6.1f} KB/s")
                    row += 1
                    self.screen.addstr(row, 2, f"{device} W:")
                    self.draw_bar(row, 12, 20, write_pct, f"{write_rate:6.1f} KB/s")
                    row += 1
                
                history.append(stats)
        
        return row
    
    def update_display(self):
        """Update the display with current system information"""
        try:
            self.screen.clear()
            
            # Header
            self.screen.addstr(0, 0, "Raspberry Pi System Monitor", curses.A_BOLD | curses.A_UNDERLINE)
            self.screen.addstr(0, 50, f"Update: {datetime.now().strftime('%H:%M:%S')}")
            
            row = 2
            
            # Temperatures
            temps = self.get_temperature()
            self.screen.addstr(row, 0, "Temperatures:", curses.A_BOLD)
            row += 1
            for name, temp in temps.items():
                color = curses.A_NORMAL
                if temp > 70:
                    color = curses.A_BOLD
                elif temp > 60:
                    color = curses.A_DIM
                self.screen.addstr(row, 2, f"{name}: {temp:5.1f}°C", color)
                row += 1
            
            row += 1
            
            # Network activity
            net_stats = self.get_network_stats()
            row = self.draw_network_bars(row, net_stats)
            row += 1
            
            # Disk activity
            disk_stats = self.get_disk_stats()
            row = self.draw_disk_bars(row, disk_stats)
            row += 1
            
            # Uptime
            uptime = self.get_uptime()
            self.screen.addstr(row, 0, f"Uptime: {uptime}", curses.A_BOLD)
            row += 2
            
            # Logged users
            users = self.get_logged_users()
            self.screen.addstr(row, 0, "Logged Users:", curses.A_BOLD)
            row += 1
            if users:
                for user in users[:5]:  # Limit to 5 users
                    self.screen.addstr(row, 2, user)
                    row += 1
            else:
                self.screen.addstr(row, 2, "None")
                row += 1
            row += 1
            
            # CPU utilization
            cpu_usage = self.get_cpu_usage()
            self.screen.addstr(row, 0, "CPU Utilization:", curses.A_BOLD)
            row += 1
            for i, usage in enumerate(cpu_usage):
                self.draw_bar(row, 2, 20, usage, f"Core {i}")
                row += 1
            
            # Overall CPU
            avg_cpu = sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
            self.draw_bar(row, 2, 20, avg_cpu, "Average")
            row += 2
            
            # Memory utilization
            mem_info = self.get_memory_usage()
            self.screen.addstr(row, 0, "Memory Utilization:", curses.A_BOLD)
            row += 1
            self.draw_bar(row, 2, 20, mem_info['percent'], "RAM")
            row += 1
            total_gb = mem_info['total'] / (1024**3)
            used_gb = mem_info['used'] / (1024**3)
            self.screen.addstr(row, 2, f"Used: {used_gb:.1f}GB / {total_gb:.1f}GB")
            row += 2
            
            # Top processes
            processes = self.get_top_processes()
            self.screen.addstr(row, 0, "Top 5 Processes:", curses.A_BOLD)
            row += 1
            self.screen.addstr(row, 2, "PID    Name                CPU%   MEM%")
            row += 1
            for proc in processes:
                pid = proc.get('pid', 0)
                name = proc.get('name', 'Unknown')[:15]
                cpu_pct = proc.get('cpu_percent', 0) or 0
                mem_pct = proc.get('memory_percent', 0) or 0
                self.screen.addstr(row, 2, f"{pid:<6} {name:<15} {cpu_pct:5.1f}  {mem_pct:5.1f}")
                row += 1
            
            # Instructions
            max_y, max_x = self.screen.getmaxyx()
            self.screen.addstr(max_y - 1, 0, "Press 'q' to quit", curses.A_DIM)
            
            self.screen.refresh()
            
        except Exception as e:
            # Handle any drawing errors gracefully
            pass
    
    def run(self):
        """Main run loop"""
        def main(screen):
            self.screen = screen
            curses.curs_set(0)  # Hide cursor
            screen.nodelay(1)   # Non-blocking input
            screen.timeout(100) # 100ms timeout for getch
            
            while self.running:
                try:
                    # Check for quit command
                    ch = screen.getch()
                    if ch == ord('q') or ch == ord('Q'):
                        break
                    
                    self.update_display()
                    time.sleep(self.update_interval)
                    
                except KeyboardInterrupt:
                    break
                except Exception:
                    # Handle any errors and continue
                    time.sleep(self.update_interval)
        
        curses.wrapper(main)

if __name__ == "__main__":
    monitor = RPiMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")