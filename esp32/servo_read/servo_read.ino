/*
回读所有舵机反馈参数:位置、速度、负载、电压、温度、移动状态、电流；
FeedBack函数回读舵机参数于缓冲区，Readxxx(-1)函数返回缓冲区中相应的舵机状态；
函数Readxxx(ID)，ID=-1返回FeedBack缓冲区参数；ID>=0，通过读指令直接返回指定ID舵机状态,
无需调用FeedBack函数。
Read back all feedback parameters: position, speed, load, voltage, temperature, movement status;
The FeedBack function reads back the servo parameters in the buffer, and the Readxxx (-1) function returns the corresponding servo state in the buffer;
Function Readxxx (ID), ID=1 returns the FeedBack buffer parameter; ID > 0, and directly returns the specified ID rudder state by reading the instruction.
There is no need to call the FeedBack function.
*/

// the uart used to control servos.
// GPIO 18 - S_RXD, GPIO 19 - S_TXD, as default.
#define S_RXD 8
#define S_TXD 9
#include <SCServo.h>

SMS_STS sms_sts;

void setup()
{
  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  Serial.begin(115200);
  sms_sts.pSerial = &Serial1;
  delay(1000);
}

void loop()
{
  int Pos;
  
  // 读取1-5号舵机的位置
  for(int id = 1; id <= 5; id++) {
    Pos = sms_sts.ReadPos(id);
    if(Pos != -1) {
      Serial.print("舵机 ");
      Serial.print(id);
      Serial.print(" 位置: ");
      Serial.println(Pos, DEC);
      delay(10);
    } else {
      Serial.print("读取舵机 ");
      Serial.print(id);
      Serial.println(" 位置失败");
      delay(500);
    }
  }
  
  Serial.println(); // 打印空行作为分隔
  delay(1000);     // 每组数据之间延时1秒
}
