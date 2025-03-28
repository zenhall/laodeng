import threading
import json
import queue
import time
from datetime import datetime

class RobotController:
    def __init__(self, host='0.0.0.0', cmd_port=8080, status_port=8082):
        self.host = host
        self.cmd_port = cmd_port
        self.status_port = status_port
        
        # 状态数据存储
        self.latest_status = None
        
        # 命令队列
        self.cmd_queue = queue.Queue()
        
        # 连接状态
        self.cmd_writer = None
        self.running = True
        
        # 启动处理线程
        self.cmd_thread = threading.Thread(target=self._command_processor)
        self.cmd_thread.daemon = True
        self.cmd_thread.start()
    
    def start_servers(self):
        """启动所有服务器"""
        import socket
        
        # 命令服务器
        cmd_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cmd_server.bind((self.host, self.cmd_port))
        cmd_server.listen(1)
        
        # 状态服务器
        status_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        status_server.bind((self.host, self.status_port))
        status_server.listen(1)
        
        print(f"命令服务器运行在 {self.host}:{self.cmd_port}")
        print(f"状态服务器运行在 {self.host}:{self.status_port}")
        
        # 启动服务器处理线程
        cmd_thread = threading.Thread(target=self._handle_command_server, args=(cmd_server,))
        status_thread = threading.Thread(target=self._handle_status_server, args=(status_server,))
        
        cmd_thread.daemon = True
        status_thread.daemon = True
        
        cmd_thread.start()
        status_thread.start()
    
    def _handle_command_server(self, server):
        """处理命令连接"""
        while self.running:
            try:
                client, addr = server.accept()
                print(f"命令客户端连接：{addr}")
                self.cmd_writer = client
            except Exception as e:
                print(f"命令服务器错误：{e}")
                time.sleep(1)
    
    def _handle_status_server(self, server):
        """处理状态数据连接"""
        while self.running:
            try:
                client, addr = server.accept()
                print(f"状态客户端连接：{addr}")
                
                while True:
                    data = client.recv(1024)
                    if not data:
                        break
                    
                    status = json.loads(data.decode())
                    self.latest_status = status
                    ##print("状态更新:", status)
            except Exception as e:
                print(f"状态服务器错误：{e}")
                time.sleep(1)
    
    def _command_processor(self):
        """命令处理线程"""
        while self.running:
            try:
                # 从队列获取命令
                command = self.cmd_queue.get(timeout=1)
                if self.cmd_writer:
                    try:
                        self.cmd_writer.send(f"{json.dumps(command)}\n".encode())
                        # 只打印舵机位置信息
                        if command.get("type") == "servo":
                            print(f"舵机位置更新: {command['positions']}")
                    except Exception as e:
                        print(f"发送命令失败: {e}")
                else:
                    print("命令连接未建立")
            except queue.Empty:
                continue
            except Exception as e:
                print(f"命令处理错误: {e}")
    
    def send_command(self, command):
        """将命令加入队列"""
        self.cmd_queue.put(command)
    
    # 控制函数
    def set_servo_positions(self, positions, speeds=None):
        """设置舵机位置"""
        if speeds is None:
            speeds = [1500] * 5
        
        command = {
            "type": "servo",
            "positions": positions,
            "speeds": speeds
        }
        self.send_command(command)
    
    def set_led(self, index, r, g, b):
        """设置LED颜色"""
        command = {
            "type": "led",
            "index": index,
            "r": r,
            "g": g,
            "b": b
        }
        self.send_command(command)
    
    def set_all_leds(self, r, g, b):
        """设置所有LED颜色"""
        self.set_led(-1, r, g, b)
    
    def stop(self):
        """停止控制器"""
        self.running = False

def main():
    controller = RobotController()
    controller.start_servers()
    
    # 示例控制序列
    time.sleep(2)  # 等待连接建立
    
    try:
        # 设置所有LED为红色
        controller.set_all_leds(255, 0, 0)
        time.sleep(1)
        
        # 设置舵机位置
        controller.set_servo_positions([1961, 875, 3094, 3152, 2998])
        time.sleep(2)
        
        # 设置舵机位置
        controller.set_servo_positions([1847, 1977, 1853, 3759, 2996])
        time.sleep(2)
        
        # 设置所有LED为绿色
        controller.set_all_leds(0, 255, 0)
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("程序终止")
    finally:
        controller.stop()

if __name__ == "__main__":
    main()