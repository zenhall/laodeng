from queue import Queue
import threading
import time
import iat
import json
from chat_with_voice import AIChat

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
                result_queue.put(result)
                print(f"识别结果: {result}", end='\r')
    except Exception as e:
        print("receive msg,but parse exception:", e)

def run_iat():
    iat.on_message = custom_on_message
    while True:
        try:
            iat.main()
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

def monitor_results():
    last_result = ""
    while True:
        try:
            if not result_queue.empty():
                last_result = result_queue.get()
            
            if iat.has_speech_content == False:
                if last_result:
                    print(f"\n检测到语音结束，最终结果: {last_result}")
                    handle_voice_result(last_result)
                    last_result = ""
            
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("\n监控程序已停止")
            break
        except Exception as e:
            print(f"监控发生错误: {e}")

def main():
    print("语音对话系统已启动，请开始说话...")
    
    # 创建并启动AI聊天线程
    ai_chat = AIChat(input_queue)
    ai_chat.start()

    # 创建并启动语音识别线程
    iat_thread = threading.Thread(target=run_iat)
    iat_thread.daemon = True
    iat_thread.start()
    
    # 创建并启动监控线程
    monitor_thread = threading.Thread(target=monitor_results)
    monitor_thread.daemon = True
    monitor_thread.start()
    
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