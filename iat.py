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
silence_threshold = 0.01  # 声音阈值，低于此值视为静音
silence_duration = 1.0  # 静音持续1秒判定为一句话结束
has_speech_content = False  # 跟踪是否有识别内容

# 收到websocket消息的处理
def on_message(ws, message):
    global has_speech_content
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
            if any(c.isalnum() or c.isalpha() for c in result):  # 检查是否包含字母或数字
                has_speech_content = True
                print(f"识别结果: {result}", end='\r')
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
        intervel = 0.04
        status = STATUS_FIRST_FRAME
        wsParam = ws.wsParam
        
        # 定义音频参数
        samplerate = 16000  # 采样率
        channels = 1  # 单声道
        
        # 添加连接状态标志
        ws.is_connected = True

        def audio_callback(indata, frames, time_info, status):
            global last_sound_time, has_speech_content
            
            # 如果连接已关闭，不再发送数据
            if not ws.is_connected:
                return
            
            if status:
                print(status)
            
            audio_data = indata.copy()
            audio_level = np.abs(audio_data).mean()
            
            if audio_level > silence_threshold:
                last_sound_time = time.time()
            else:
                current_time = time.time()
                if current_time - last_sound_time > silence_duration and has_speech_content:
                    print("\nover")
                    last_sound_time = current_time
                    has_speech_content = False
            
            audio_data = (audio_data * 32767).astype(np.int16).tobytes()
            
            try:
                nonlocal first_frame
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

        print("开始录音，请说话...")
        first_frame = True
        
        # 开始录音
        with sd.InputStream(samplerate=samplerate, 
                          channels=channels,
                          blocksize=frameSize,
                          callback=audio_callback):
            try:
                while True:
                    time.sleep(0.1)  # 保持麦克风开启
            except KeyboardInterrupt:
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
                print("\n录音结束")
                ws.close()

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