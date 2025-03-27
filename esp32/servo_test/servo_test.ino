/*
The SyncWritePos example passed the test in ST3215/ST3020/ST3025 Servo, 
and if testing other models of ST series servos
please change the appropriate position, speed and delay parameters.
*/

#include <SCServo.h>
SMS_STS st;

// the uart used to control servos.
// GPIO 18 - S_RXD, GPIO 19 - S_TXD, as default.
#define S_RXD 8
#define S_TXD 9

byte ID[5];          // 改为5个舵机
u16 Speed[5];        // 5个速度值
byte ACC[5];         // 5个加速度值

// 定义两组位置数组
s16 Position1[5] = {1961, 875, 3094, 3152, 2998};  //sleep
s16 Position2[5] = {1847, 1977, 1853, 3759, 2996}; //deng 

void setup()
{
  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  st.pSerial = &Serial1;
  delay(1000);
  
  // 设置5个舵机的ID
  for(int i = 0; i < 5; i++) {
    ID[i] = i + 1;
    Speed[i] = 3400;
    ACC[i] = 50;
  }
}

void loop()
{
  // 第一组位置
  st.SyncWritePosEx(ID, 5, Position1, Speed, ACC);  // 控制5个舵机移动到第一组位置
  delay(2000);

  // 第二组位置
  st.SyncWritePosEx(ID, 5, Position2, Speed, ACC);  // 控制5个舵机移动到第二组位置
  delay(2000);
}
