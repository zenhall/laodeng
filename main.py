import threading
import time
from monitor_iat import run_iat, monitor_results
from test import RobotController

class IntegratedSystem:
    def __init__(self):
        # 初始化机器人控制器
        self.robot = RobotController()
        
        # 定义预设的动作组合
        self.actions = {
            "动作一": {
                "positions": [1961, 875, 3094, 3152, 2998],
                "led": {"r": 255, "g": 0, "b": 0}
            },
            "动作二": {
                "positions": [1847, 1977, 1853, 3759, 2996],
                "led": {"r": 0, "g": 255, "b": 0}
            }
        }
    
    def handle_speech_result(self, result):
        """处理语音识别结果"""
        if result["type"] == "speech":
            content = result["content"]
            print(f"收到语音命令: {content}")
            
            try:
                # 简单的命令处理逻辑
                if "动作一" in content:
                    print("执行动作一")
                    action = self.actions["动作一"]
                    self.robot.set_servo_positions(action["positions"])
                    time.sleep(0.5)  # 添加短暂延时
                    self.robot.set_all_leds(**action["led"])
                    print("动作一执行完成")
                elif "动作二" in content:
                    print("执行动作二")
                    action = self.actions["动作二"]
                    self.robot.set_servo_positions(action["positions"])
                    time.sleep(0.5)  # 添加短暂延时
                    self.robot.set_all_leds(**action["led"])
                    print("动作二执行完成")
                elif "测试" in content:
                    print("执行测试命令")
                    # 添加一个简单的测试命令
                    self.robot.set_all_leds(255, 0, 0)  # 红色
                    time.sleep(1)
                    self.robot.set_all_leds(0, 255, 0)  # 绿色
                    time.sleep(1)
                    self.robot.set_all_leds(0, 0, 255)  # 蓝色
                    print("测试命令执行完成")
            except Exception as e:
                print(f"执行命令时出错: {e}")
    
    def start(self):
        try:
            # 启动机器人服务器
            self.robot.start_servers()
            print("机器人控制器已启动")
            
            # 等待连接建立
            time.sleep(2)
            
            # 执行一个简单的测试
            print("执行初始化测试...")
            self.robot.set_all_leds(0, 0, 255)  # 蓝色表示系统就绪
            print("初始化测试完成")
            
            # 启动语音识别线程
            iat_thread = threading.Thread(target=run_iat)
            iat_thread.daemon = True
            iat_thread.start()
            print("语音识别系统已启动")
            
            # 启动语音监控线程，传入回调函数
            monitor_thread = threading.Thread(
                target=monitor_results,
                args=(self.handle_speech_result,)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            print("语音监控系统已启动")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n系统正在关闭...")
                self.robot.stop()
                print("系统已关闭")
        except Exception as e:
            print(f"系统启动时出错: {e}")
            self.robot.stop()

if __name__ == "__main__":
    system = IntegratedSystem()
    system.start() 