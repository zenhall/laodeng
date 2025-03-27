import speech_recognition as sr
import openai
import pygame
from gtts import gTTS
import os
import time
from playsound import playsound  # 添加新的音频播放库
import requests

# 设置代理配置
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}

# 设置OpenAI API配置
openai.api_key = "sk-CkxIb6MfdTBgZkdm0MtUEGVGk6Q6o5X5BRB1DwE2BdeSLSqB"
openai.api_base = "https://api.chatanywhere.tech/v1"

class VoiceAssistant:
    def __init__(self, api_key):
        # 初始化OpenAI API

        self.recognizer = sr.Recognizer()
        
        # 初始化对话历史
        self.conversation_history = []
    
    def listen(self):
        with sr.Microphone() as source:
            print("正在听......")
            self.recognizer.adjust_for_ambient_noise(source)
            audio = self.recognizer.listen(source)
            
        try:
            text = self.recognizer.recognize_google(audio, language='zh-CN')
            print(f"你说: {text}")
            return text
        except sr.UnknownValueError:
            print("无法识别语音")
            return None
        except sr.RequestError:
            print("语音识别服务出错")
            return None

    def get_ai_response(self, user_input):
        # 添加用户输入到对话历史
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            # 使用代理发送请求
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",  # 使用与 olm_test2_v0.py 相同的模型
                messages=self.conversation_history,
                temperature=0.3,      # 降低温度以获得更稳定的回答
                max_tokens=200,       # 设置最大输出长度
                presence_penalty=0.1,
                frequency_penalty=0.1,
                timeout=30,            # 设置超时时间
                proxies=proxies        # 添加代理设置
            )
            
            if response.choices[0].finish_reason == "content_filter":
                return "回答被内容过滤，请换个方式提问"
            
            if hasattr(response.choices[0], 'message'):
                message = response.choices[0].message
                if isinstance(message, dict):
                    content = message.get('content')
                    if content and content.strip():
                        # 添加AI回复到对话历史
                        self.conversation_history.append({"role": "assistant", "content": content})
                        return content
                elif hasattr(message, 'content'):
                    if message.content and message.content.strip():
                        # 添加AI回复到对话历史
                        self.conversation_history.append({"role": "assistant", "content": message.content})
                        return message.content
                    
            return "无法获取有效回答"
        except Exception as e:
            print(f"OpenAI API 错误: {e}")
            return "抱歉，我现在无法回答，请检查网络连接或稍后再试。"

    def speak(self, text):
        try:
            # 使用代理设置创建 TTS
            session = requests.Session()
            session.proxies = proxies
            tts = gTTS(text=text, lang='zh-cn', session=session)
            
            # 保存音频文件
            filename = "response.mp3"
            tts.save(filename)
            
            try:
                # 首先尝试使用 playsound
                playsound(filename)
            except Exception as e:
                print(f"playsound 播放失败，尝试使用 pygame: {e}")
                try:
                    # 如果 playsound 失败，使用 pygame 作为备选
                    pygame.mixer.init()
                    pygame.mixer.music.load(filename)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    pygame.mixer.quit()
                except Exception as e:
                    print(f"pygame 播放也失败了: {e}")
            
            # 删除临时文件
            try:
                os.remove(filename)
            except:
                pass
                
        except Exception as e:
            print(f"语音合成或播放出错: {e}")
            # 如果语音失败，至少打印文本
            print(f"AI 回复文本: {text}")

    def run(self):
        print("语音助手已启动（按Ctrl+C退出）")
        while True:
            try:
                user_input = self.listen()
                if user_input:
                    ai_response = self.get_ai_response(user_input)
                    if ai_response:
                        print(f"AI: {ai_response}")
                        self.speak(ai_response)
            except KeyboardInterrupt:
                print("\n感谢使用！再见！")
                break

# 使用示例
if __name__ == "__main__":
    # 创建 VoiceAssistant 实例，使用已经在文件顶部定义的 API 密钥
    assistant = VoiceAssistant(openai.api_key)
    assistant.run()