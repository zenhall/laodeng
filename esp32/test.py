import asyncio
import json
import wave
import numpy as np
from datetime import datetime

class RobotController:
    def __init__(self, host='0.0.0.0', cmd_port=8080, audio_port=8081, status_port=8082):
        self.host = host
        self.cmd_port = cmd_port
        self.audio_port = audio_port
        self.status_port = status_port
        
        # 音频文件设置
        self.audio_file = None
        self.is_recording = False
        
        # 状态数据存储
        self.latest_status = None
        
    async def start_servers(self):
        """启动所有服务器"""
        cmd_server = await asyncio.start_server(
            self.handle_command_client, self.host, self.cmd_port)
        audio_server = await asyncio.start_server(
            self.handle_audio_client, self.host, self.audio_port)
        status_server = await asyncio.start_server(
            self.handle_status_client, self.host, self.status_port)
        
        print(f"命令服务器运行在 {self.host}:{self.cmd_port}")
        print(f"音频服务器运行在 {self.host}:{self.audio_port}")
        print(f"状态服务器运行在 {self.host}:{self.status_port}")
        
        async with cmd_server, audio_server, status_server:
            await asyncio.gather(
                cmd_server.serve_forever(),
                audio_server.serve_forever(),
                status_server.serve_forever()
            )
    
    async def handle_command_client(self, reader, writer):
        """处理命令连接"""
        addr = writer.get_extra_info('peername')
        print(f"命令客户端连接：{addr}")
        self.cmd_writer = writer
        
        try:
            while True:
                await asyncio.sleep(0.1)  # 保持连接
        except Exception as e:
            print(f"命令客户端断开：{addr}, 原因：{e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def handle_audio_client(self, reader, writer):
        """处理音频数据连接"""
        addr = writer.get_extra_info('peername')
        print(f"音频客户端连接：{addr}")
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                    
                if self.is_recording and self.audio_file:
                    self.audio_file.writeframes(data)
        except Exception as e:
            print(f"音频客户端断开：{addr}, 原因：{e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def handle_status_client(self, reader, writer):
        """处理状态数据连接"""
        addr = writer.get_extra_info('peername')
        print(f"状态客户端连接：{addr}")
        
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                    
                status = json.loads(data.decode())
                self.latest_status = status
                print("状态更新:", status)
        except Exception as e:
            print(f"状态客户端断开：{addr}, 原因：{e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def send_command(self, command):
        """发送命令到设备"""
        if hasattr(self, 'cmd_writer'):
            try:
                self.cmd_writer.write(f"{json.dumps(command)}\n".encode())
                await self.cmd_writer.drain()
                print(f"已发送命令: {command}")
            except Exception as e:
                print(f"发送命令失败: {e}")
        else:
            print("命令连接未建立")
    
    def start_recording(self):
        """开始录制音频"""
        if not self.is_recording:
            filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            self.audio_file = wave.open(filename, 'wb')
            self.audio_file.setnchannels(1)
            self.audio_file.setsampwidth(2)
            self.audio_file.setframerate(16000)
            self.is_recording = True
            print(f"开始录制音频到: {filename}")
    
    def stop_recording(self):
        """停止录制音频"""
        if self.is_recording:
            self.audio_file.close()
            self.audio_file = None
            self.is_recording = False
            print("停止录制音频")
    
    # 控制函数
    async def set_servo_positions(self, positions, speeds=None):
        """设置舵机位置"""
        if speeds is None:
            speeds = [3400] * 5
        
        command = {
            "type": "servo",
            "positions": positions,
            "speeds": speeds
        }
        await self.send_command(command)
    
    async def set_led(self, index, r, g, b):
        """设置LED颜色"""
        command = {
            "type": "led",
            "index": index,
            "r": r,
            "g": g,
            "b": b
        }
        await self.send_command(command)
    
    async def set_all_leds(self, r, g, b):
        """设置所有LED颜色"""
        await self.set_led(-1, r, g, b)

# 使用示例
async def main():
    controller = RobotController()
    
    # 创建控制任务
    control_task = asyncio.create_task(controller.start_servers())
    
    # 示例控制序列
    await asyncio.sleep(2)  # 等待连接建立
    
    # 开始录音
    controller.start_recording()
    
    # 控制示例
    try:
        # 设置所有LED为红色
        await controller.set_all_leds(255, 0, 0)
        await asyncio.sleep(1)
        
        # 设置舵机位置
        await controller.set_servo_positions([1961, 875, 3094, 3152, 2998])
        await asyncio.sleep(2)
        
        # 设置舵机位置
        await controller.set_servo_positions([1847, 1977, 1853, 3759, 2996])
        await asyncio.sleep(2)
        
        # 设置所有LED为绿色
        await controller.set_all_leds(0, 255, 0)
        await asyncio.sleep(1)
        
    except KeyboardInterrupt:
        print("程序终止")
    finally:
        # 停止录音
        controller.stop_recording()
        
        # 取消服务器任务
        control_task.cancel()
        try:
            await control_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())