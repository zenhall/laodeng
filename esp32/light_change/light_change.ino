// NeoPixel Ring simple sketch (c) 2013 Shae Erisson
// Released under the GPLv3 license to match the rest of the
// Adafruit NeoPixel library

#include <Adafruit_NeoPixel.h>
#ifdef __AVR__
 #include <avr/power.h> // Required for 16 MHz Adafruit Trinket
#endif

// Which pin on the Arduino is connected to the NeoPixels?
#define PIN        7 // On Trinket or Gemma, suggest changing this to 1

// How many NeoPixels are attached to the Arduino?
#define NUMPIXELS 10 // Popular NeoPixel ring size

// When setting up the NeoPixel library, we tell it how many pixels,
// and which pin to use to send signals. Note that for older NeoPixel
// strips you might need to change the third parameter -- see the
// strandtest example for more information on possible values.
Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

#define DELAYVAL 500 // Time (in milliseconds) to pause between pixels

// 添加舵机控制所需的头文件和定义
#define S_RXD 8
#define S_TXD 9
#include <SCServo.h>

SMS_STS sms_sts;

// 定义舵机位置范围
#define MIN_POS 1800
#define MAX_POS 2200

void setup() {
  // These lines are specifically to support the Adafruit Trinket 5V 16 MHz.
  // Any other board, you can remove this part (but no harm leaving it):
#if defined(__AVR_ATtiny85__) && (F_CPU == 16000000)
  clock_prescale_set(clock_div_1);
#endif
  // END of Trinket-specific code.

  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  Serial.begin(115200);
  sms_sts.pSerial = &Serial1;
  pixels.begin();
  delay(1000);
}

void loop() {
  // 读取三个舵机的位置并映射到RGB值
  int r = map(constrain(sms_sts.ReadPos(1), MIN_POS, MAX_POS), MIN_POS, MAX_POS, 0, 255);
  int g = map(constrain(sms_sts.ReadPos(2), MIN_POS, MAX_POS), MIN_POS, MAX_POS, 0, 255);
  int b = map(constrain(sms_sts.ReadPos(3), MIN_POS, MAX_POS), MIN_POS, MAX_POS, 0, 255);
  
  // 如果读取失败，使用默认值0
  r = (r == -1) ? 0 : r;
  g = (g == -1) ? 0 : g;
  b = (b == -1) ? 0 : b;

  // 设置所有像素的颜色
  for(int i=0; i<NUMPIXELS; i++) {
    pixels.setPixelColor(i, pixels.Color(r, g, b));
  }
  
  pixels.show();
  delay(50); // 降低刷新延迟以获得更流畅的效果
}
