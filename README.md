# 老灯同学 - 多模态机器人台灯 🤖💡

> 一个集成了语音控制、姿态监测和智能照明的开源机器人台灯项目。



## ✨ 主要特点

### 🎯 语音指令控制
- 通过LLM实现自然语言理解
- 支持多种语音指令：
  - `老灯同学` - 抬头响应
  - `阅读模式` - 切换到阅读照明模式
  - `关灯` - 关闭照明并移动到休息位置

### 🕒 智能久坐提醒
- 基于视觉语言模型(VLM)的人体检测
- 智能计数系统：
  - 检测到连续久坐会触发不同级别的提醒
  - 通过LED灯光颜色变化直观显示久坐时长
  - 到达阈值时会执行摇头和闪烁等提醒动作

### 🎮 交互控制
- 支持手动拖动调节灯光位置
- 实时LED状态反馈


## 项目结构
```bash
.
├── 3D/                  # 3D打印模型文件
├── PCBA/                # 电路板设计文件     
├── esp32/
│   ├── combined_cam/        # ESP32主程序
│   │   └── combined_cam.ino # 下位机程序
│   └── wifi_stream/     # 视觉处理相关程序
│       └── wifi_stream.py
└── monitor_iat.py       # 语音控制程序
```


## 🛠️ 硬件要求

- XIAO ESP32-S3 SENSE开发板
- 转接扩展板
- 3D结构基于[SOARM100](https://github.com/huggingface/lerobot/blob/main/examples/10_use_so100.md)修改


## 📦 软件依赖

### 基础环境
- Python 3.8+
- pip 包管理器

### 主要依赖包
| 包名 | 用途 |
|------|------|
| OpenAI API | LLM接口 |
| OpenCV | 图像处理 |
| PyAudio | 音频处理 |
| Pillow | 图像处理 |
| NumPy | 数值计算 |
| Websocket-client | 网络通信 |

### 安装依赖
```bash
# 安装依赖
pip install -r requirements.txt
```

### 环境配置
1. 确保已安装 Python 3.8 或更高版本
2. 配置 OpenAI API：
   - 在 `monitor_iat.py` 和 `wifi_stream.py` 中设置你的LLM API key可于以下项目中获取免费额度：https://github.com/chatanywhere/GPT_API_free 
   - 在 `iat.py` 中设置你的IAT API key可注册科大讯飞开放平台获得免费额度
3. 配置网络：
   - 确保 ESP32 和运行程序的设备在同一网络下
   - 在代码中更新 ESP32 的 IP 地址

## 使用说明

### 语音控制模式
```bash
python monitor_iat.py
```

### 视觉处理模式
```bash
python esp32/wifi_stream/wifi_stream.py
```

## 📝 许可证

本项目采用 [MIT](LICENSE) 许可证。

## 🙏 致谢

- 感谢所有为本项目做出贡献的开发者
- 感谢shizhe的3D曲面模型设计

<p align="center">
  <a href="#top">返回顶部 ⬆️</a>
</p>
