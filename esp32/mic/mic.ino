#include <ESP_I2S.h>
#include <WiFi.h>

// WiFi设置
const char* ssid = "2nd-curv";
const char* password = "xbotpark";
const char* host = "192.168.5.24";  // 修改为您电脑的实际IP地址
const uint16_t port = 8080;         // 选择一个端口号

I2SClass I2S;
WiFiClient client;

// 音频缓冲区
const int BUFFER_SIZE = 1024;
char buffer[BUFFER_SIZE];

// 音频增益
const int GAIN = 20;  // 增益倍数

void setup() {
  // Open serial communications and wait for port to open:
  // A baud rate of 115200 is used instead of 9600 for a faster data rate
  // on non-native USB ports
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  Serial.println("初始化I2S...");
  
  // 设置音频输入引脚
  I2S.setPinsPdmRx(42, 41);

  // 以16kHz采样率，16位采样深度启动I2S
  if (!I2S.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    Serial.println("I2S初始化失败！");
    while (1);
  }

  Serial.println("I2S初始化成功");

  // 连接WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi已连接");
  
  // 连接到服务器
  while (!client.connect(host, port)) {
    Serial.println("连接服务器失败，重试中...");
    delay(1000);
  }
  Serial.println("已连接到服务器");

  // 清空缓冲区
  for(int i = 0; i < 10; i++) {
    I2S.read();
  }
}

void loop() {
  if (!client.connected()) {
    Serial.println("连接断开，重新连接中...");
    if (client.connect(host, port)) {
      Serial.println("重新连接成功");
    } else {
      delay(1000);
      return;
    }
  }

  // 使用I2S库的readBytes函数读取音频数据
  size_t bytes_read = I2S.readBytes(buffer, BUFFER_SIZE);
  
  if (bytes_read > 0) {
    // 应用增益
    int16_t* samples = (int16_t*)buffer;
    int num_samples = bytes_read / 2;  // 每个样本2字节
    int16_t max_sample = 0;
    
    // 处理每个样本
    for (int i = 0; i < num_samples; i++) {
      // 应用增益
      int32_t amplified = samples[i] * GAIN;
      
      // 限制在16位范围内
      if (amplified > 32767) amplified = 32767;
      if (amplified < -32768) amplified = -32768;
      
      samples[i] = (int16_t)amplified;
      
      // 跟踪最大值
      if (abs(samples[i]) > max_sample) {
        max_sample = abs(samples[i]);
      }
    }
    
    // 发送处理后的数据
    client.write(buffer, bytes_read);
    
    // 打印调试信息
    Serial.printf("读取字节数: %d, 样本数: %d, 最大值: %d\n", 
                 bytes_read, num_samples, max_sample);
  }
  
  // 小延时以防止数据发送太快
  delay(5);
}