import threading
import queue
import time
import iat
import json

# 创建一个队列用于线程间通信
result_queue = queue.Queue()

# 修改 iat.py 中的 on_message 函数来存储识别结果
def custom_on_message(ws, message):
    global result_queue
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
            # 检查结果是否包含非标点符号的文字
            if any(c.isalnum() or c.isalpha() for c in result):
                iat.has_speech_content = True
                result_queue.put(result)  # 将结果放入队列
                print(f"识别结果: {result}", end='\r')
    except Exception as e:
        print("receive msg,but parse exception:", e)

def run_iat():
    # 替换原始的 on_message 函数
    iat.on_message = custom_on_message
    
    # 运行 iat 主程序
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

def monitor_results(callback_func=None):
    last_result = ""
    while True:
        try:
            # 检查是否有新的识别结果
            if not result_queue.empty():
                last_result = result_queue.get()
            
            # 当检测到语音结束时，调用回调函数处理结果
            if iat.has_speech_content == False:
                if last_result:
                    print(f"\n检测到语音结束，最终结果: {last_result}")
                    if callback_func:
                        callback_func(last_result)
                    last_result = ""  # 清空最后的结果
            
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("\n监控程序已停止")
            break
        except Exception as e:
            print(f"监控发生错误: {e}")

if __name__ == "__main__":
    # 创建并启动 IAT 线程
    iat_thread = threading.Thread(target=run_iat)
    iat_thread.daemon = True  # 设置为守护线程，主程序结束时自动结束
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