# -*- coding:utf-8 -*-
#
# 语音检测程序 - 当检测到语音停顿1秒时输出"over"
#

import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import socket
import struct
import numpy as np
import threading

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识


class Ws_Param(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}

    # 生成url
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        return url


# 全局变量
last_result = ""  # 用于存储上一次的识别结果
has_speech_content = False  # 跟踪是否有识别内容
last_update_time = time.time()  # 上次结果更新时间
TIMEOUT = 1.0  # 超时时间为1秒
speech_ended = False  # 标记语音是否结束
last_content_length = 0  # 记录上次内容的长度（不包括标点）

# 检查超时的线程函数
def check_timeout():
    global last_result, has_speech_content, last_update_time, speech_ended
    while True:
        current_time = time.time()
        if has_speech_content:
            time_since_last_update = current_time - last_update_time
            if time_since_last_update > TIMEOUT:
                print("检测到语音超时")
                has_speech_content = False  # 重置状态
                speech_ended = True
                last_update_time = current_time  # 更新时间戳
                # 完全重置状态
                last_result = ""
                last_content_length = 0
        time.sleep(0.1)  # 每0.1秒检查一次

# 移除标点符号的函数
def remove_punctuation(text):
    punctuation = '，。！？、；：""''（）【】《》〈〉…—～,.!?;:\'\"()[]<>…-~'
    return ''.join(char for char in text if char not in punctuation)

# 收到websocket消息的处理
def on_message(ws, message):
    global last_result, has_speech_content, last_update_time, speech_ended, last_content_length
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
            
            # 移除标点符号后比较内容
            result_no_punct = remove_punctuation(result)
            last_result_no_punct = remove_punctuation(last_result)
            
            # 只有当非标点内容有变化时才更新时间戳
            if len(result_no_punct) > len(last_result_no_punct):
                speech_ended = False  # 有新内容，重置语音结束标志
                has_speech_content = True
                print(f"识别结果: {result}")
                last_result = result
                last_update_time = time.time()
                last_content_length = len(result_no_punct)
                
                # 如果检测到语音已结束，主动关闭连接
                if speech_ended and has_speech_content:
                    print(f"检测到语音结束，最终结果: {last_result}")
                    d = {
                        "data": {
                            "status": 2,
                            "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(b''), 'utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    # 在适当的延迟后关闭连接
                    def close_delayed():
                        time.sleep(0.5)
                        ws.close()
                    
                    thread.start_new_thread(close_delayed, ())
                    
                    # 重置状态
                    has_speech_content = False
                    last_result = ""
                    last_content_length = 0
                    speech_ended = False
                
    except Exception as e:
        print("receive msg,but parse exception:", e)


# 收到websocket错误的处理
def on_error(ws, error):
    print("### error:", error)


# 收到websocket关闭的处理
def on_close(ws, a, b):
    ws.is_connected = False  # 标记连接已关闭
    print("### closed ###")
    print("正在尝试重新连接...")
    time.sleep(2)
    main()


# 收到websocket连接建立的处理
def on_open(ws):
    def run(*args):
        frameSize = 8000
        wsParam = ws.wsParam
        
        # 重置所有状态变量
        global last_result, has_speech_content, speech_ended, last_content_length, last_update_time
        last_result = ""
        has_speech_content = False
        speech_ended = False
        last_content_length = 0
        last_update_time = time.time()
        
        # 设置TCP服务器，修改端口为8081以匹配combined.ino的audioPort
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', 8081))  # 修改为8081
        server_socket.listen(1)
        print("等待ESP32连接到音频端口8081...")
        client_socket, addr = server_socket.accept()
        print(f"ESP32已连接，地址: {addr}")
        
        # 添加连接状态标志
        ws.is_connected = True
        first_frame = True

        try:
            while ws.is_connected:
                # 从ESP32读取音频数据
                audio_data = client_socket.recv(frameSize)
                if not audio_data:
                    break
                
                try:
                    if first_frame:
                        d = {
                            "common": wsParam.CommonArgs,
                            "business": wsParam.BusinessArgs,
                            "data": {
                                "status": 0,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                        ws.send(json.dumps(d))
                        first_frame = False
                    else:
                        d = {
                            "data": {
                                "status": 1,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                        ws.send(json.dumps(d))
                except Exception as e:
                    ws.is_connected = False
                    print(f"发送数据时出错: {e}")
                    break
                    
        except Exception as e:
            print(f"接收数据时出错: {e}")
        finally:
            client_socket.close()
            server_socket.close()
            
        # 发送最后一帧
        d = {
            "data": {
                "status": 2,
                "format": "audio/L16;rate=16000",
                "audio": str(base64.b64encode(b''), 'utf-8'),
                "encoding": "raw"
            }
        }
        ws.send(json.dumps(d))
        ws.close()

    # 启动超时检查线程
    timeout_thread = threading.Thread(target=check_timeout)
    timeout_thread.daemon = True
    timeout_thread.start()
    
    thread.start_new_thread(run, ())


def main():
    wsParam = Ws_Param(
        APPID='872c31f2',
        APISecret='NmQyMTA2NmM4NjU5MDA2OTZlM2EwZTcz',
        APIKey='126cb1b4434af61f124e03c4d266b9ea'
    )
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.wsParam = wsParam  # 将wsParam存储在ws对象中
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("\n程序已手动停止")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            print("正在尝试重新连接...")
            time.sleep(2)