import openai
from datetime import datetime
import json
import os
import websocket
import hashlib
import base64
import hmac
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from time import mktime
import _thread as thread
import pyaudio
import threading

# 讯飞 TTS 参数类
class Ws_Param(object):
    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text

        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {"aue": "raw", "auf": "audio/L16;rate=16000", "vcn": "xiaoyan", "tte": "utf8"}
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}

    def create_url(self):
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
        
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                               digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        return url + '?' + urlencode(v)

# 音频播放函数
def play_audio(file_path):
    p = pyaudio.PyAudio()
    with open(file_path, 'rb') as pcm_file:
        pcm_data = pcm_file.read()
    
    stream = p.open(format=pyaudio.paInt16,
                   channels=1,
                   rate=16000,
                   output=True)
    stream.write(pcm_data)
    stream.stop_stream()
    stream.close()
    p.terminate()

# WebSocket回调函数
def on_message(ws, message):
    try:
        message = json.loads(message)
        code = message["code"]
        audio = message["data"]["audio"]
        audio = base64.b64decode(audio)
        status = message["data"]["status"]
        
        if code == 0:
            with open('./response.pcm', 'ab') as f:
                f.write(audio)
        
        if status == 2:
            print("语音合成完成")
            def close_conn():
                time.sleep(0.5)
                print("开始播放...")
                play_audio('./response.pcm')
                print("播放完成")
                ws.close()
            thread.start_new_thread(close_conn, ())
    except Exception as e:
        print("异常:", e)

def on_error(ws, error):
    print("错误:", error)

def on_close(ws, close_status_code, close_msg):
    print("连接已关闭")

def on_open(ws, wsParam):
    def run(*args):
        d = {
            "common": wsParam.CommonArgs,
            "business": wsParam.BusinessArgs,
            "data": wsParam.Data,
        }
        ws.send(json.dumps(d))
        if os.path.exists('./response.pcm'):
            os.remove('./response.pcm')
    thread.start_new_thread(run, ())

def text_to_speech(text, xf_params):
    wsParam = Ws_Param(APPID=xf_params['APPID'],
                      APIKey=xf_params['APIKey'],
                      APISecret=xf_params['APISecret'],
                      Text=text)
    
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.on_open = lambda ws: on_open(ws, wsParam)
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

class AIChat(threading.Thread):
    def __init__(self, input_queue):
        super().__init__()
        self.input_queue = input_queue
        self.running = True
        
        # 配置OpenAI API
        openai.api_base = "https://api.chatanywhere.tech/v1"
        openai.api_key = "sk-CkxIb6MfdTBgZkdm0MtUEGVGk6Q6o5X5BRB1DwE2BdeSLSqB"
        
        # 配置讯飞API参数
        self.xf_params = {
            'APPID': '872c31f2',
            'APIKey': '126cb1b4434af61f124e03c4d266b9ea',
            'APISecret': 'NmQyMTA2NmM4NjU5MDA2OTZlM2EwZTcz'
        }

    def run(self):
        while self.running:
            try:
                user_input = self.input_queue.get()
                if user_input.lower() == '退出':
                    break

                # 调用OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": user_input}]
                )
                
                ai_response = response.choices[0].message.content
                print("AI:", ai_response)
                
                # 将AI回答转换为语音
                text_to_speech(ai_response, self.xf_params)
                
            except Exception as e:
                print("错误:", str(e))

    def stop(self):
        self.running = False 