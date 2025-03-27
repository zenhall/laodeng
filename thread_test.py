import threading
import queue
import time

class ThreadCommunication:
    def __init__(self):
        # 创建两个队列用于双向通信
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
    def producer(self):
        """生产者线程：发送数据并等待响应"""
        for i in range(5):
            request = f"请求-{i}"
            print(f"生产者发送: {request}")
            # 发送请求
            self.request_queue.put(request)
            # 等待响应
            response = self.response_queue.get()
            print(f"生产者收到响应: {response}")
            time.sleep(1)
            
        # 发送结束信号
        self.request_queue.put("END")
            
    def consumer(self):
        """消费者线程：处理数据并返回响应"""
        while True:
            # 获取请求
            request = self.request_queue.get()
            if request == "END":
                break
                
            print(f"消费者接收: {request}")
            # 处理请求并发送响应
            response = f"响应: {request}已处理"
            self.response_queue.put(response)

def main():
    # 创建通信实例
    comm = ThreadCommunication()
    
    # 创建线程
    producer_thread = threading.Thread(target=comm.producer)
    consumer_thread = threading.Thread(target=comm.consumer)
    
    # 启动线程
    print("开始线程间通信测试...")
    producer_thread.start()
    consumer_thread.start()
    
    # 等待线程完成
    producer_thread.join()
    consumer_thread.join()
    
    print("线程通信测试完成！")

if __name__ == "__main__":
    main()