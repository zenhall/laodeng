from queue import Queue
from chat_with_voice import AIChat

def main():
    input_queue = Queue()
    ai_chat = AIChat(input_queue)
    ai_chat.start()

    try:
        while True:
            user_input = input("请输入消息 (输入'退出'结束): ")
            input_queue.put(user_input)
            
            if user_input.lower() == '退出':
                break
    
    finally:
        # 确保程序结束时正确关闭线程
        ai_chat.stop()
        ai_chat.join()

if __name__ == "__main__":
    main()