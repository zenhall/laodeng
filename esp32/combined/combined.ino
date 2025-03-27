#include <Adafruit_NeoPixel.h>
#include <ESP_I2S.h>
#include <WiFi.h>
#include <SCServo.h>
#include <ArduinoJson.h>

// FreeRTOS相关
TaskHandle_t wifiCommandTaskHandle;
TaskHandle_t micTaskHandle;
TaskHandle_t servoTaskHandle;
TaskHandle_t statusTaskHandle;

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

void setup() {
  Serial.begin(115200);
  
  // 初始化LED
  pixels.begin();
  pixels.clear();
  pixels.show();
  
  // 初始化I2S
  I2S.setPinsPdmRx(42, 41);
  if (!I2S.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    Serial.println("I2S初始化失败！");
    while (1);
  }
  
  // 初始化WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi已连接");
  
  // 初始化舵机通信
  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  st.pSerial = &Serial1;
  
  // 初始化舵机参数
  for(int i = 0; i < 5; i++) {
    ID[i] = i + 1;
    Speed[i] = 3400;
    ACC[i] = 50;
  }

  // 创建任务
  xTaskCreate(wifiCommandTask, "Command Task", 4096, NULL, 2, &wifiCommandTaskHandle);
  xTaskCreate(micTask, "Mic Task", 4096, NULL, 2, &micTaskHandle);
  xTaskCreate(statusTask, "Status Task", 4096, NULL, 1, &statusTaskHandle);
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
} 