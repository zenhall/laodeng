import cv2
import numpy as np
from ultralytics import YOLO
import requests
import time
from threading import Thread
import queue
import socket

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
        
        # 加载YOLO模型
        self.model = YOLO('best.pt')
        self.model.conf = 0.4
        
        # 初始化socket连接
        self.socket_client = None
        if socket_host and socket_port:
            try:
                self.socket_client = socket.socket()
                self.socket_client.connect((socket_host, socket_port))
                print("成功连接到Socket服务器")
            except Exception as e:
                print(f"Socket连接失败: {e}")
                self.socket_client = None
        
        # 添加颜色映射
        self.colors = {
            # 为每个类别随机生成一个颜色
            i: tuple(map(int, np.random.randint(0, 255, size=3)))
            for i in range(len(self.model.names))
        }
        
        # 添加窗口名称并设置为可缩放
        self.window_name = 'ESP32 YOLO Detection'
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        
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
                
    def process_frames(self):
        """处理视频帧并进行目标检测"""
        fps_time = time.time()
        frames_count = 0
        
        while True:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                
                # 运行YOLO检测
                results = self.model(frame, stream=True)
                
                # 在图像上绘制检测结果并发送到ESP32
                detection_results = []  # 存储检测结果
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        # 获取类别和置信度
                        cls = int(box.cls)
                        conf = float(box.conf)
                        name = self.model.names[cls]
                        
                        # 只在置信度大于0.5时处理
                        if conf > 0.5:
                            # 只将类别号添加到列表
                            detection_results.append(str(cls))
                        
                        # 获取边界框坐标
                        x1, y1, x2, y2 = box.xyxy[0]
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                        
                        # 获取该类别对应的颜色
                        color = self.colors[cls]
                        
                        # 使用对应颜色绘制边界框和标签
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(frame, f'{name} {conf:.2f}', 
                                  (x1, y1 - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 
                                  0.5, color, 2)
                
                # 如果有检测结果且socket连接可用，发送到ESP32
                if detection_results and self.socket_client:
                    try:
                        # 将所有类别号组合成一个字符串，用分号分隔
                        message = ";".join(detection_results) + "\n"
                        self.socket_client.send(message.encode())
                    except Exception as e:
                        print(f"发送数据失败: {e}")
                
                # 计算并显示FPS
                frames_count += 1
                if time.time() - fps_time > 1.0:
                    fps = frames_count / (time.time() - fps_time)
                    cv2.putText(frame, f'FPS: {fps:.1f}',
                              (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                              1, (0, 255, 0), 2)
                    frames_count = 0
                    fps_time = time.time()
                
                # 显示处理后的帧（使用类中定义的窗口名称）
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