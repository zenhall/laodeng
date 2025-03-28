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
        
        # 添加计数器
        self.human_count = 0
        self.false_count = 0

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

    def process_frames(self):
        """每3秒处理一帧并显示"""
        last_frame_time = time.time()
        
        while True:
            current_time = time.time()
            
            if not self.frame_queue.empty() and (current_time - last_frame_time) >= 3:
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
                
                # 检查累计次数并打印
                if self.human_count == 10:
                    print("达到10次 -> 1H")
                elif self.human_count == 20:
                    print("达到20次 -> 2H")
                    self.human_count = 0  # 达到20次后重置计数
                    print("计数已重置为0")
                
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