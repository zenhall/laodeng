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
import sounddevice as sd
import numpy as np
import socket
import threading
import wave
import os

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


# 全局变量，用于跟踪最后一次检测到声音的时间
last_sound_time = time.time()
silence_threshold = 100  # 增大声音阈值
silence_duration = 1.0  # 静音持续1秒判定为一句话结束
has_speech_content = False  # 跟踪是否有识别内容

# 收到websocket消息的处理
def on_message(ws, message):
    try:
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        if code != 0:
            errMsg = json.loads(message)["message"]
            print(f"\n识别错误 sid: {sid}, 错误信息: {errMsg}, 错误码: {code}")
        else:
            data = json.loads(message)["data"]["result"]["ws"]
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
            if result.strip():
                print(f"\n识别结果: {result}")
    except Exception as e:
        print("\n解析消息出错:", e)


# 收到websocket错误的处理
def on_error(ws, error):
    print("### error:", error)


# 收到websocket关闭的处理
def on_close(ws, *args):
    print("### closed ###")
    ws.is_connected = False
    time.sleep(2)
    print("正在尝试重新连接...")
    websocket.enableTrace(False)
    wsParam = ws.wsParam
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error,
                               on_close=on_close, on_open=on_open)
    ws.wsParam = wsParam
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})


# 收到websocket连接建立的处理
def on_open(ws):
    def run(*args):
        frameSize = 8000
        intervel = 0.04
        status = STATUS_FIRST_FRAME
        wsParam = ws.wsParam
        
        ws.is_connected = True
        server = None
        client_socket = None

        try:
            # 创建TCP服务器
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 添加socket选项，允许地址重用
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', 8080))
            server.listen(1)
            print("等待ESP32连接...")
            client_socket, addr = server.accept()
            print(f"ESP32已连接: {addr}")

            def process_audio_data():
                first_frame = True
                global has_speech_content, last_sound_time
                silence_threshold = 100  # 声音阈值
                silence_duration = 1.0   # 静音判断时长
                last_sound_time = time.time()
                has_speech_content = False
                
                try:
                    while ws.is_connected:
                        try:
                            audio_data = client_socket.recv(2048)
                            if not audio_data:
                                break

                            # 将字节数据转换为numpy数组用于分析
                            audio_array = np.frombuffer(audio_data, dtype=np.int16)
                            
                            if len(audio_array) == 0:
                                continue
                            
                            # 计算音频电平
                            audio_level = np.abs(audio_array).mean()
                            max_level = np.max(np.abs(audio_array))
                            
                            print(f"\r音频电平: {audio_level:.2f}, 最大值: {max_level}", end='')
                            
                            # 检测声音活动
                            if audio_level > silence_threshold:
                                last_sound_time = time.time()
                                has_speech_content = True
                                
                                try:
                                    if first_frame:
                                        d = {
                                            "common": wsParam.CommonArgs,
                                            "business": wsParam.BusinessArgs,
                                            "data": {
                                                "status": STATUS_FIRST_FRAME,
                                                "format": "audio/L16;rate=16000",
                                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                                "encoding": "raw"
                                            }
                                        }
                                        ws.send(json.dumps(d))
                                        first_frame = False
                                        print("\n开始新的语音识别...")
                                    else:
                                        d = {
                                            "data": {
                                                "status": STATUS_CONTINUE_FRAME,
                                                "format": "audio/L16;rate=16000",
                                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                                "encoding": "raw"
                                            }
                                        }
                                        ws.send(json.dumps(d))
                                except Exception as e:
                                    print(f"\n发送数据时出错: {e}")
                                    break
                            else:
                                # 检查是否需要发送结束帧
                                current_time = time.time()
                                if current_time - last_sound_time > silence_duration and has_speech_content:
                                    try:
                                        d = {
                                            "data": {
                                                "status": STATUS_LAST_FRAME,
                                                "format": "audio/L16;rate=16000",
                                                "audio": str(base64.b64encode(b''), 'utf-8'),
                                                "encoding": "raw"
                                            }
                                        }
                                        ws.send(json.dumps(d))
                                        print("\n检测到语音结束，等待识别结果...")
                                        first_frame = True
                                        has_speech_content = False
                                    except Exception as e:
                                        print(f"\n发送结束帧时出错: {e}")

                        except Exception as e:
                            print(f"\n接收数据时出错: {e}")
                            break

                except Exception as e:
                    print(f"\n音频处理错误: {e}")
                finally:
                    if client_socket:
                        client_socket.close()
                    
                    # 打印最终统计信息
                    print(f"总样本数: {total_samples}")
                    print(f"文件大小: {os.path.getsize('recorded_audio.wav') / 1024:.1f} KB")
                    print(f"录音时长: {total_samples / 16000:.1f} 秒")

            # 在新线程中处理音频数据
            audio_thread = threading.Thread(target=process_audio_data)
            audio_thread.start()

            while ws.is_connected:
                time.sleep(0.1)

        except Exception as e:
            print(f"服务器错误: {e}")
        finally:
            if client_socket:
                client_socket.close()
            if server:
                server.close()
            ws.is_connected = False

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