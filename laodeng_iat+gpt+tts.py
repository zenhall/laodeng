import sys
import os
import time
import threading
import json
from queue import Queue
import iat
import re
import subprocess
from chat_with_voice import AIChat

# 创建队列用于线程间通信
result_queue = Queue()  # 语音识别结果队列
input_queue = Queue()   # AI输入队列

# 使用线程控制变量
iat_running = threading.Event()
iat_running.set()  # 初始状态为运行

# 全局变量，用于追踪最新识别结果
latest_result = ""

# 修改后的custom_on_message函数，更好地跟踪识别结果
def custom_on_message(ws, message):
    global latest_result
    try:
        # 调用原始处理函数
        iat.on_message(ws, message)
        
        # 尝试从消息中提取识别结果
        message_dict = json.loads(message)
        if message_dict.get("code") == 0 and "data" in message_dict:
            data = message_dict["data"]["result"]["ws"]
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
            
            if result:  # 如果有结果，更新最新结果
                latest_result = result
                print(f"更新最新识别结果: {latest_result}")
    except Exception as e:
        # 可能是其他类型的消息，忽略错误
        pass

# iat控制线程
def iat_control_thread():
    while True:
        # 等待运行信号
        iat_running.wait()
        
        try:
            print("IAT启动中...")
            
            # 使用新进程运行IAT
            iat_process = subprocess.Popen([sys.executable, "-c", 
                """
import iat
import sys
sys.stdout = open('iat_output.txt', 'w')
iat.main()
                """], 
                shell=True)
            
            # 循环监控输出文件，检查"over"信号
            while iat_running.is_set() and iat_process.poll() is None:
                try:
                    if os.path.exists('iat_output.txt'):
                        with open('iat_output.txt', 'r') as f:
                            content = f.read()
                            if "over" in content:
                                # 提取最新识别结果
                                matches = re.findall(r'识别结果: (.+)', content)
                                if matches:
                                    latest_result = matches[-1]  # 获取最新的识别结果
                                    print(f"捕获到over信号，最终识别结果: {latest_result}")
                                    
                                    # 停止IAT
                                    iat_running.clear()
                                    iat_process.terminate()
                                    
                                    # 处理语音结果
                                    handle_voice_result(latest_result)
                                    break
                except Exception as e:
                    print(f"读取输出文件错误: {e}")
                
                time.sleep(0.2)  # 每200ms检查一次
            
            # 确保进程已终止
            if iat_process.poll() is None:
                iat_process.terminate()
                
            print("IAT已停止")
            
        except Exception as e:
            print(f"IAT控制线程错误: {e}")
        
        # 如果是正常退出，等待一段时间再重启
        if not iat_running.is_set():
            time.sleep(0.5)
            iat_running.wait()  # 等待恢复信号

def handle_voice_result(text):
    if not text or text.isspace():
        print("语音识别结果为空，忽略")
        # 立即重新恢复语音识别
        iat_running.set()
        return
        
    print("语音识别已暂停，等待AI回复...")
    
    # 将语音识别结果发送给AI处理
    input_queue.put(text)
    print(f"已将文本发送给AI: {text}")

def main():
    global latest_result
    print("语音对话系统已启动，请开始说话...")
    
    # 清除可能存在的旧输出文件
    if os.path.exists('iat_output.txt'):
        os.remove('iat_output.txt')
    
    # 导入AIChat类
    from chat_with_voice import AIChat
    
    # 创建并启动AI聊天线程
    ai_chat = AIChat(input_queue, iat_running)
    ai_chat.start()
    
    # 创建并启动语音识别控制线程
    iat_thread = threading.Thread(target=iat_control_thread)
    iat_thread.daemon = True
    iat_thread.start()
    
    # 主循环
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序已终止")

if __name__ == "__main__":
    main() 