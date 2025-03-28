#include <Adafruit_NeoPixel.h>
#include <ESP_I2S.h>
#include <WiFi.h>
#include <SCServo.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM
#include "camera_pins.h"

// FreeRTOS相关
TaskHandle_t wifiCommandTaskHandle;
TaskHandle_t micTaskHandle;
TaskHandle_t servoTaskHandle;
TaskHandle_t statusTaskHandle;
TaskHandle_t cameraTaskHandle;

// WiFi设置
const char* ssid = "2nd-curv";
const char* password = "xbotpark";
const char* host = "192.168.5.24";
const uint16_t commandPort = 8080;  // 命令端口
const uint16_t audioPort = 8081;    // 音频数据端口
const uint16_t statusPort = 8082;   // 状态反馈端口

// 网络客户端
WiFiClient commandClient;    // 接收命令
WiFiClient audioClient;      // 发送音频
WiFiClient statusClient;     // 发送状态

// NeoPixel设置
#define PIN        7
#define NUMPIXELS 10
Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

// I2S和音频设置
I2SClass I2S;
const int BUFFER_SIZE = 1024;
char audioBuffer[BUFFER_SIZE];
const int GAIN = 20;

// 舵机设置
#define S_RXD 8
#define S_TXD 9
SMS_STS st;
byte ID[5];
u16 Speed[5];
byte ACC[5];

// JSON文档
StaticJsonDocument<200> cmdDoc;
StaticJsonDocument<500> statusDoc;

// 添加TCP服务器对象
WiFiServer ServerPort(1234);

// 添加HTTP流媒体服务器相关声明
void startCameraServer();
void setupLedFlash(int pin);

// 处理接收到的命令
void handleCommand(const char* command) {
  DeserializationError error = deserializeJson(cmdDoc, command);
  if (error) {
    Serial.println("解析JSON失败");
    return;
  }

  const char* type = cmdDoc["type"];
  
  if (strcmp(type, "servo") == 0) {
    // 舵机控制命令格式：
    // {"type":"servo","positions":[1000,2000,3000,4000,5000],"speeds":[3400,3400,3400,3400,3400]}
    JsonArray positions = cmdDoc["positions"];
    JsonArray speeds = cmdDoc["speeds"];
    
    for(int i = 0; i < 5; i++) {
      Speed[i] = speeds[i] | 3400;  // 如果未指定则使用默认值3400
      ACC[i] = 50;
    }
    
    s16 newPositions[5];
    for(int i = 0; i < 5; i++) {
      newPositions[i] = positions[i];
    }
    
    st.SyncWritePosEx(ID, 5, newPositions, Speed, ACC);
  }
  else if (strcmp(type, "led") == 0) {
    // LED控制命令格式：
    // {"type":"led","index":0,"r":255,"g":0,"b":0}
    int index = cmdDoc["index"];
    int r = cmdDoc["r"];
    int g = cmdDoc["g"];
    int b = cmdDoc["b"];
    
    if (index >= 0 && index < NUMPIXELS) {
      pixels.setPixelColor(index, pixels.Color(r, g, b));
      pixels.show();
    }
    else if (index == -1) {  // -1表示设置所有LED
      for(int i = 0; i < NUMPIXELS; i++) {
        pixels.setPixelColor(i, pixels.Color(r, g, b));
      }
      pixels.show();
    }
  }
}

// WiFi命令处理任务
void wifiCommandTask(void *parameter) {
  Serial.println("命令任务已启动");
  char commandBuffer[256];
  int bufferIndex = 0;
  
  while(1) {
    if (!commandClient.connected()) {
      commandClient.stop();
      if (commandClient.connect(host, commandPort)) {
        Serial.println("命令通道已连接");
      } else {
        vTaskDelay(pdMS_TO_TICKS(1000));
        continue;
      }
    }

    while (commandClient.available()) {
      char c = commandClient.read();
      if (c == '\n') {
        commandBuffer[bufferIndex] = '\0';
        handleCommand(commandBuffer);
        bufferIndex = 0;
      } else if (bufferIndex < 255) {
        commandBuffer[bufferIndex++] = c;
      }
    }
    
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// 麦克风采集任务
void micTask(void *parameter) {
  Serial.println("麦克风任务已启动");
  while(1) {
    if (!audioClient.connected()) {
      audioClient.stop();
      if (audioClient.connect(host, audioPort)) {
        Serial.println("音频通道已连接");
      } else {
        vTaskDelay(pdMS_TO_TICKS(1000));
        continue;
      }
    }

    size_t bytes_read = I2S.readBytes(audioBuffer, BUFFER_SIZE);
    if (bytes_read > 0) {
      int16_t* samples = (int16_t*)audioBuffer;
      int num_samples = bytes_read / 2;
      
      for (int i = 0; i < num_samples; i++) {
        int32_t amplified = samples[i] * GAIN;
        if (amplified > 32767) amplified = 32767;
        if (amplified < -32768) amplified = -32768;
        samples[i] = (int16_t)amplified;
      }
      
      audioClient.write(audioBuffer, bytes_read);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

// 状态反馈任务
void statusTask(void *parameter) {
  Serial.println("状态任务已启动");
  while(1) {
    if (!statusClient.connected()) {
      statusClient.stop();
      if (statusClient.connect(host, statusPort)) {
        Serial.println("状态通道已连接");
      } else {
        vTaskDelay(pdMS_TO_TICKS(1000));
        continue;
      }
    }

    // 构建状态JSON
    statusDoc.clear();
    JsonArray servoPositions = statusDoc.createNestedArray("servo_positions");
    JsonArray ledStates = statusDoc.createNestedArray("led_states");

    // 读取舵机位置
    for(int id = 1; id <= 5; id++) {
      int pos = st.ReadPos(id);
      servoPositions.add(pos);
    }

    // 读取LED状态
    for(int i = 0; i < NUMPIXELS; i++) {
      uint32_t color = pixels.getPixelColor(i);
      JsonObject led = ledStates.createNestedObject();
      led["index"] = i;
      led["r"] = (color >> 16) & 0xFF;
      led["g"] = (color >> 8) & 0xFF;
      led["b"] = color & 0xFF;
    }

    // 发送状态
    String statusString;
    serializeJson(statusDoc, statusString);
    statusString += "\n";  // 添加换行符作为消息分隔
    statusClient.print(statusString);

    vTaskDelay(pdMS_TO_TICKS(100));  // 每100ms发送一次状态
  }
}

// 添加摄像头任务处理函数
void cameraTask(void *parameter) {
  Serial.println("摄像头任务已启动");
  while(1) {
    WiFiClient client = ServerPort.available();
    if (client) {
      Serial.println("新客户端连接");
      
      while (client.connected()) {
        if (client.available()) {
          // 读取检测结果
          String data = client.readStringUntil('\n');
          
          // 解析并显示每个检测结果
          Serial.println("检测结果:");
          
          // 按分号分割字符串
          int prevIndex = 0;
          int colonIndex = -1;
          
          while ((colonIndex = data.indexOf(';', prevIndex)) != -1) {
            String detection = data.substring(prevIndex, colonIndex);
            Serial.println(detection);
            prevIndex = colonIndex + 1;
          }
          
          if (prevIndex < data.length()) {
            Serial.println(data.substring(prevIndex));
          }
          
          client.println("Data received");
        }
      }
      
      client.stop();
      Serial.println("客户端断开连接");
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("程序启动");
  
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;  // 改为UXGA
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  
  // 添加PSRAM检查和相应配置
  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // 如果没有PSRAM，限制帧大小
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("摄像头初始化失败，错误代码: 0x%x\n", err);
    return;
  }

  // 初始化后配置传感器
  sensor_t * s = esp_camera_sensor_get();
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
    s->set_brightness(s, 1);
    s->set_saturation(s, -2);
  }
  // 降低帧大小以获得更高的初始帧率
  if (config.pixel_format == PIXFORMAT_JPEG) {
    s->set_framesize(s, FRAMESIZE_QVGA);
  }

  // 初始化LED
  pixels.begin();
  pixels.clear();
  pixels.show();
  Serial.println("LED初始化完成");  // 添加LED初始化信息
  
  // 初始化I2S
  I2S.setPinsPdmRx(42, 41);
  if (!I2S.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    Serial.println("I2S初始化失败！");
    while (1);
  }
  Serial.println("I2S初始化成功");  // 添加I2S初始化信息
  
  // 初始化WiFi
  Serial.print("正在连接WiFi");
  WiFi.begin(ssid, password);
  WiFi.setSleep(false);  // 禁用WiFi睡眠模式以提高性能
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi已连接");
  Serial.print("IP地址: ");
  Serial.println(WiFi.localIP());

  // 启动摄像头HTTP服务器
  startCameraServer();
  Serial.print("摄像头服务器就绪! 使用 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("/stream' 进行连接");  // 添加/stream路径
  
  // 初始化舵机通信
  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  st.pSerial = &Serial1;
  Serial.println("舵机通信初始化完成");  // 添加舵机初始化信息
  
  // 初始化舵机参数
  for(int i = 0; i < 5; i++) {
    ID[i] = i + 1;
    Speed[i] = 3400;
    ACC[i] = 50;
  }

  // 启动TCP服务器
  ServerPort.begin();
  Serial.println("TCP服务器已启动");
  
  // 创建任务
  Serial.println("开始创建任务");  // 添加任务创建信息
  xTaskCreate(wifiCommandTask, "Command Task", 8192, NULL, 2, &wifiCommandTaskHandle);  // 增加堆栈大小
  xTaskCreate(micTask, "Mic Task", 8192, NULL, 2, &micTaskHandle);
  xTaskCreate(statusTask, "Status Task", 8192, NULL, 1, &statusTaskHandle);
  xTaskCreate(cameraTask, "Camera Task", 8192, NULL, 1, &cameraTaskHandle);
  Serial.println("所有任务创建完成");  // 添加任务创建完成信息
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
} 