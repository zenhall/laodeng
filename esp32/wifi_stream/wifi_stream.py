import cv2
import numpy as np
import requests
import time
from threading import Thread
import queue
import socket
import base64
import io
from PIL import Image
from openai import OpenAI
from test import RobotController

FRAME_PROCESS_INTERVAL = 3  # 处理帧之间的间隔时间（秒）3秒用于演示，实际修改为360即为一小时提醒

class ESP32_Camera_Stream:
    def __init__(self, url, socket_host=None, socket_port=None):
        """初始化ESP32相机流处理器
        
        Args:
            url: ESP32摄像头的流地址
            socket_host: Socket服务器地址（可选）
            socket_port: Socket服务器端口（可选）
        """
        self.url = url
        self.frame_queue = queue.Queue(maxsize=2)
        self.is_running = False
        
        # 添加窗口名称并设置为可缩放
        self.window_name = 'ESP32 Camera'
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url="https://api.chatanywhere.tech/v1",  # GPT4O-mini服务器地址
            api_key="sk-CkxIb6MfdTBgZkdm0MtUEGVGk6Q6o5X5BRB1DwE2BdeSLSqB"  # 本地服务不需要API密钥
        )
        
        # 添加舵机位置常量
        self.HEAD_LEFT = [1688, 1816, 2737, 2628, 2878]
        self.HEAD_RIGHT = [2141, 1816, 2737, 2628, 2878]
        self.WARNING_POSITION = [1900, 2100, 2100, 2950, 2878]
        self.REST_POSITION = [1961, 875, 3094, 3152, 2998]  # 添加休息位置
        
        # 添加计数器
        self.human_count = 0
        self.false_count = 0  # 用于跟踪连续False的次数
        
        # 添加RobotController实例
        self.controller = RobotController()
        self.controller.start_servers()
        time.sleep(2)  # 等待连接建立

    def start(self):
        """启动视频流处理"""
        self.is_running = True
        self.thread = Thread(target=self._stream_reader)
        self.thread.daemon = True
        self.thread.start()
        
    def _stream_reader(self):
        """在后台线程中持续读取视频流"""
        stream = requests.get(self.url, stream=True)
        bytes_data = bytes()
        
        for chunk in stream.iter_content(chunk_size=1024):
            bytes_data += chunk
            a = bytes_data.find(b'\xff\xd8')  # JPEG开始标记
            b = bytes_data.find(b'\xff\xd9')  # JPEG结束标记
            
            if a != -1 and b != -1:
                jpg = bytes_data[a:b+2]
                bytes_data = bytes_data[b+2:]
                
                try:
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if not self.frame_queue.full():
                        self.frame_queue.put(frame)
                except:
                    continue
                    
            if not self.is_running:
                break
                
    def detect_human(self, frame):
        """使用GPT4O-mini检测图像中是否有人
        
        Args:
            frame: OpenCV格式的图像帧
        
        Returns:
            bool: 图像中是否检测到人
        """
        # 将OpenCV图像转换为PIL格式并保存为base64
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='JPEG')
        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这张图片中是否有人？请只回答true或false。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=10
            )
            result = response.choices[0].message.content.strip().lower()
            return result == "true"
            
        except Exception as e:
            print(f"GPT4O-mini API调用错误: {e}")
            return False

    def _map_count_to_color(self, count):
        """将计数值(0-20)映射为LED颜色
        
        Args:
            count: 当前计数值(0-20)
        
        Returns:
            tuple: (r, g, b)值
        """
        # 确保count在0-20范围内
        count = max(0, min(20, count))
        
        # 计算红色和绿色分量
        # count越大，红色越强，绿色越弱
        red = int((count / 20.0) * 255)
        green = int(((20 - count) / 20.0) * 255)
        
        return (red, green, 0)  # 不使用蓝色分量

    def shake_head(self):
        """执行两次来回的摇头动作"""
        for _ in range(2):  # 两次来回
            # 向左摇头
            self.controller.set_servo_positions(self.HEAD_LEFT)
            time.sleep(1)  # 等待动作完成
            
            # 向右摇头
            self.controller.set_servo_positions(self.HEAD_RIGHT)
            time.sleep(1)  # 等待动作完成
            
        # 回到中间位置
        middle_position = [
            (self.HEAD_LEFT[0] + self.HEAD_RIGHT[0]) // 2,
            self.HEAD_LEFT[1],
            self.HEAD_LEFT[2],
            self.HEAD_LEFT[3],
            self.HEAD_LEFT[4]
        ]
        self.controller.set_servo_positions(middle_position)

    def warning_action(self):
        """执行警告动作和红白闪烁"""
        # 移动到警告位置
        self.controller.set_servo_positions(self.WARNING_POSITION)
        
        # 红白闪烁5次
        for _ in range(5):
            # 设置为红色
            self.controller.set_all_leds(255, 0, 0)
            time.sleep(1)
            # 设置为白色
            self.controller.set_all_leds(255, 255, 255)
            time.sleep(1)
        
        # 恢复到当前计数对应的颜色
        r, g, b = self._map_count_to_color(self.human_count)
        self.controller.set_all_leds(r, g, b)

    def process_frames(self):
        """每FRAME_PROCESS_INTERVAL秒处理一帧并显示"""
        last_frame_time = time.time()
        
        while True:
            current_time = time.time()
            
            if not self.frame_queue.empty() and (current_time - last_frame_time) >= FRAME_PROCESS_INTERVAL:
                frame = self.frame_queue.get()
                last_frame_time = current_time
                
                # 使用GPT4O-mini检测人
                has_human = self.detect_human(frame)
                
                # 更新计数器并打印状态
                if has_human:
                    self.human_count += 1
                    self.false_count = 0  # 重置false计数
                    print(f"检测到人，当前累计次数: {self.human_count}")
                else:
                    self.false_count += 1
                    print(f"未检测到人，连续{self.false_count}次，当前累计次数: {self.human_count}")
                    if self.false_count >= 2:  # 两次False时重置计数
                        self.human_count = 0
                        self.false_count = 0
                        print("连续两次未检测到人，计数已重置")
                        # 移动到休息位置
                        self.controller.set_servo_positions(self.REST_POSITION)
                
                # 检查累计次数并打印
                if self.human_count == 10:
                    print("达到10次 -> 1H")
                    self.shake_head()  # 执行摇头动作
                elif self.human_count == 20:
                    print("达到20次 -> 2H")
                    self.warning_action()  # 执行警告动作和闪烁
                    # 不再在此处重置计数
                
                # 更新LED颜色
                r, g, b = self._map_count_to_color(self.human_count)
                self.controller.set_all_leds(r, g, b)
                
                # 显示时间戳和检测结果
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(frame, timestamp,
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                          1, (0, 255, 0), 2)
                cv2.putText(frame, f"Has Human: {has_human} (Count: {self.human_count})",
                          (10, 70), cv2.FONT_HERSHEY_SIMPLEX,
                          1, (0, 255, 0), 2)
                
                # 显示处理后的帧
                cv2.imshow(self.window_name, frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        self.stop()
        cv2.destroyAllWindows()
        
    def stop(self):
        """停止视频流处理"""
        self.is_running = False
        # 关闭LED
        self.controller.set_all_leds(0, 0, 0)
        self.controller.stop()

def main():
    # ESP32摄像头流地址和Socket服务器配置
    stream_url = 'http://192.168.5.65:81/stream'
    socket_host = '192.168.5.65'
    socket_port = 1234
    
    print(f"正在连接到 {stream_url}")
    
    # 创建并启动视频流处理器
    camera = ESP32_Camera_Stream(url=stream_url,  # 使用关键字参数
                               socket_host=socket_host,
                               socket_port=socket_port)
    camera.start()
    
    try:
        camera.process_frames()
    except KeyboardInterrupt:
        print("程序被用户中断")
    finally:
        camera.stop()
        print("程序已退出")
        
if __name__ == '__main__':
    main()