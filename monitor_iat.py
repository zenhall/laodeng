import threading
import queue
import time
import iat
import json
# 添加 OpenAI 相关导入
import openai
from test import RobotController  # 导入机器人控制器

# 添加 OpenAI 配置
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}

openai.api_key = "sk-CkxIb6MfdTBgZkdm0MtUEGVGk6Q6o5X5BRB1DwE2BdeSLSqB"
openai.api_base = "https://api.chatanywhere.tech/v1"

# 添加简化版的 AI 对话类
class AIChat:
    def __init__(self):
        self.conversation_history = []
        self.current_state = "关闭"
        self.system_prompt = """你是一个台灯机器人助手。你需要理解用户的语音指令并执行相应动作：
        - 当听到"老登同学"时，移动到抬头位置 [1961, 875, 3094, 2800, 2998]，保持当前灯光状态
        - 当听到"阅读模式"时，移动到 [1847, 1977, 1853, 3759, 2996]，并开启照明
        - 当听到"关灯"时，移动到 [1961, 875, 3094, 3152, 2998]，并关闭照明
        请根据用户输入返回相应的位置数组，如果不是这些指令，返回 "no_action"。
        """
        self.conversation_history.append({"role": "system", "content": self.system_prompt})
    
    def get_response(self, user_input):
        self.conversation_history.append({"role": "user", "content": user_input})
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=self.conversation_history,
                temperature=0.3,
                max_tokens=200,
                presence_penalty=0.1,
                frequency_penalty=0.1,
                timeout=30,
                proxies=proxies
            )
            
            content = response.choices[0].message.get('content', '')
            if content and content.strip():
                self.conversation_history.append({"role": "assistant", "content": content})
                # 解析响应，获取位置信息和更新状态
                if "1961, 875, 3094, 2800, 2998" in content:
                    self.current_state = "抬头模式"
                    return {
                        "action": "move", 
                        "position": [1961, 875, 3094, 2800, 2998], 
                        "message": "正在移动到抬头位置",
                        "state": self.current_state,
                        "light": "保持当前状态"
                    }
                elif "1847, 1977, 1853, 3759, 2996" in content:
                    self.current_state = "阅读模式"
                    return {
                        "action": "move", 
                        "position": [1847, 1977, 1853, 3759, 2996], 
                        "message": "正在切换到阅读模式",
                        "state": self.current_state,
                        "light": "开启"
                    }
                elif "1961, 875, 3094, 3152, 2998" in content:
                    self.current_state = "关闭"
                    return {
                        "action": "move", 
                        "position": [1961, 875, 3094, 3152, 2998], 
                        "message": "正在关灯",
                        "state": self.current_state,
                        "light": "关闭"
                    }
                return {
                    "action": "none", 
                    "message": "未识别到有效指令",
                    "state": self.current_state,
                    "light": "保持当前状态"
                }
            return {
                "action": "error", 
                "message": "无法获取有效回答",
                "state": self.current_state,
                "light": "保持当前状态"
            }
        except Exception as e:
            print(f"OpenAI API 错误: {e}")
            return {
                "action": "error", 
                "message": f"API调用错误: {str(e)}",
                "state": self.current_state,
                "light": "保持当前状态"
            }

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
                result_queue.put({"type": "speech", "content": result})  # 修改为发送JSON格式数据
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

class RobotManager:
    def __init__(self, host='0.0.0.0', cmd_port=8080, status_port=8082):
        self.controller = None
        self.host = host
        self.cmd_port = cmd_port
        self.status_port = status_port
        self.current_light_state = False  # 添加灯光状态跟踪
        self.init_robot()

    def init_robot(self):
        try:
            self.controller = RobotController(
                host=self.host,
                cmd_port=self.cmd_port,
                status_port=self.status_port
            )
            self.controller.start_servers()
            print("机器人控制器初始化成功，等待连接...")
            time.sleep(2)  # 等待连接建立
            return True
        except Exception as e:
            print(f"机器人控制器初始化失败: {e}")
            return False

    def move_and_light(self, positions, light_command):
        try:
            if self.controller:
                self.controller.set_servo_positions(positions)
                
                # 根据light_command处理灯光
                if light_command == "开启":
                    self.controller.set_all_leds(255, 255, 255)
                    self.current_light_state = True
                elif light_command == "关闭":
                    self.controller.set_all_leds(0, 0, 0)
                    self.current_light_state = False
                # 如果是"保持当前状态"，则不改变灯光
                
                return True
            return False
        except Exception as e:
            print(f"机器人控制错误: {e}")
            return False

    def stop(self):
        if self.controller:
            self.controller.stop()

def monitor_results(callback_func=None):
    last_result = ""
    speech_active = False
    ai_chat = AIChat()
    robot = RobotManager()
    
    while True:
        try:
            if not result_queue.empty():
                result_data = result_queue.get()
                last_result = result_data["content"]
                speech_active = True
            
            if iat.has_speech_content == False and speech_active:
                if last_result:
                    print(f"\n检测到语音结束，最终结果: {last_result}")
                    
                    response = ai_chat.get_response(last_result)
                    print(f"AI 响应: {response['message']}")
                    print(f"当前状态: {response['state']}")
                    print(f"灯光状态: {response['light']}")
                    
                    if response['action'] == 'move':
                        print(f"移动到位置: {response['position']}")
                        if robot.move_and_light(response['position'], response['light']):
                            print("执行成功")
                        else:
                            print("执行失败")
                    
                    if callback_func:
                        callback_func({
                            "type": "speech", 
                            "content": last_result,
                            "state": response['state'],
                            "light": response['light']
                        })
                    last_result = ""
                    speech_active = False
            
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("\n监控程序已停止")
            robot.stop()
            break
        except Exception as e:
            print(f"监控发生错误: {e}")
            try:
                robot.stop()
            except:
                pass
            break

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