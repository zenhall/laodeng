from queue import Queue
import threading
import time
import iat
import json
from chat_with_voice import AIChat
import re

# 创建队列用于线程间通信
result_queue = Queue()  # 语音识别结果队列
input_queue = Queue()   # AI输入队列

# 保存原始的on_message函数
original_on_message = iat.on_message

def custom_on_message(ws, message):
    try:
        # 首先调用原始的on_message函数，保持iat.py的功能完整
        original_on_message(ws, message)
        
        # 然后处理我们自己的逻辑
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        if code != 0:
            return
        
        data = json.loads(message)["data"]["result"]["ws"]
        result = ""
        for i in data:
            for w in i["cw"]:
                result += w["w"]
        
        if any(c.isalnum() or c.isalpha() for c in result):
            # 更新队列中的最新结果（清空旧结果）
            while not result_queue.empty():
                result_queue.get()
            result_queue.put(result)
    except Exception as e:
        print("custom_on_message exception:", e)

# 监听iat的over信号
def listen_for_over():
    import sys
    original_stdout = sys.stdout
    
    class OverDetector:
        def __init__(self):
            self.buffer = ""
            self.last_over_time = 0
            
        def write(self, text):
            original_stdout.write(text)
            
            # 直接检查当前文本是否包含"over"
            current_time = time.time()
            if "over" in text and (current_time - self.last_over_time) > 2:
                self.last_over_time = current_time
                # 检测到over信号，处理最后的识别结果
                if not result_queue.empty():
                    final_result = result_queue.get()
                    print(f"\n检测到语音结束，最终结果: {final_result}")
                    handle_voice_result(final_result)
            
        def flush(self):
            original_stdout.flush()
    
    sys.stdout = OverDetector()

def run_iat():
    # 设置自定义的on_message函数
    iat.on_message = custom_on_message
    
    while True:
        try:
            iat.main()
            print("IAT主循环结束，正在重新启动...")
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nIAT程序已停止")
            break
        except Exception as e:
            print(f"IAT发生错误: {e}")
            print("正在尝试重新连接...")
            time.sleep(2)

def handle_voice_result(text):
    # 将语音识别结果发送给AI处理
    input_queue.put(text)
    print(f"已将文本发送给AI: {text}")

def main():
    print("语音对话系统已启动，请开始说话...")
    
    # 启动over信号监听
    listen_for_over()
    
    # 创建并启动AI聊天线程
    ai_chat = AIChat(input_queue)
    ai_chat.start()

    # 创建并启动语音识别线程
    iat_thread = threading.Thread(target=run_iat)
    iat_thread.daemon = True
    iat_thread.start()
    
    try:
        # 保持主程序运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序已终止")
    finally:
        # 确保程序结束时正确关闭线程
        ai_chat.stop()
        ai_chat.join()

if __name__ == "__main__":
    main() 