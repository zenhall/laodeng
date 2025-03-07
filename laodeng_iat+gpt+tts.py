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

def custom_on_message(ws, message):
    try:
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        if code != 0:
            errMsg = json.loads(message)["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
        else:
            data = json.loads(message)["data"]["result"]["ws"]
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
            if any(c.isalnum() or c.isalpha() for c in result):
                iat.has_speech_content = True
                # 更新队列中的最新结果（清空旧结果）
                while not result_queue.empty():
                    result_queue.get()
                result_queue.put(result)
                print(f"识别结果: {result}")
    except Exception as e:
        print("receive msg,but parse exception:", e)

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
            self.buffer += text
            
            # 使用正则表达式匹配独立的"over"单词
            if re.search(r'\bover\b', self.buffer) and (time.time() - self.last_over_time) > 2:
                self.last_over_time = time.time()
                # 检测到over信号，处理最后的识别结果
                if not result_queue.empty():
                    final_result = result_queue.get()
                    print(f"\n检测到语音结束，最终结果: {final_result}")
                    handle_voice_result(final_result)
                # 清空缓冲区，准备下一次检测
                self.buffer = ""
                # 重置iat状态，准备下一次识别
                iat.has_speech_content = False
                iat.last_result = ""
                iat.speech_ended = False
            
            # 保持缓冲区在合理大小
            if len(self.buffer) > 1000:
                self.buffer = self.buffer[-500:]
            
        def flush(self):
            original_stdout.flush()
    
    sys.stdout = OverDetector()

def run_iat():
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