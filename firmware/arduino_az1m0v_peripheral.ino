/*
 * az1m0v Arduino peripheral — CAN I/O node
 *
 * Hardware: Arduino Uno + MCP2515-based CAN shield (common SPI wiring).
 * Libraries: install "mcp_can" (Cory Fowler) or compatible MCP2515 library.
 *
 * Adjust MCP_CS_PIN and CAN_INT_PIN for your shield.
 *
 * IDs must match config.json arduino_can (default status 0x310, command 0x311).
 */

#include <SPI.h>
#include <mcp_can.h>

const unsigned long CAN_BITRATE = CAN_500KBPS;

const unsigned long ID_STATUS = 0x310;
const unsigned long ID_COMMAND = 0x311;

const byte STATUS_MAGIC = 0xA1;
const byte COMMAND_MAGIC = 0xB1;

const int MCP_CS_PIN = 10;
const int CAN_INT_PIN = 2;

MCP_CAN CAN(MCP_CS_PIN);

byte digitalOut = 0;
byte pwmAux = 0;
bool listenOnly = true;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  for (int i = 2; i <= 5; i++) {
    if (i != CAN_INT_PIN) pinMode(i, INPUT_PULLUP);
  }
  for (int o = 6; o <= 9; o++) {
    pinMode(o, OUTPUT);
    digitalWrite(o, LOW);
  }

  while (CAN.begin(MCP_ANY, CAN_BITRATE, MCP_8MHZ) != CAN_OK) {
    delay(100);
  }
  CAN.setMode(MCP_NORMAL);
}

void loop() {
  readCommandIfAny();
  sendStatus();
  applyOutputs();
  delay(50);
}

void readCommandIfAny() {
  if (!digitalRead(CAN_INT_PIN)) {
    unsigned long rxId;
    byte len = 0;
    byte rxBuf[8];
    if (CAN.readMsgBuf(&rxId, &len, rxBuf) == CAN_OK && len >= 4) {
      if (rxId == ID_COMMAND && rxBuf[0] == COMMAND_MAGIC) {
        digitalOut = rxBuf[1];
        pwmAux = rxBuf[2];
        listenOnly = (rxBuf[3] & 0x01) != 0;
      }
    }
  }
}

void sendStatus() {
  byte din = 0;
  for (int b = 0; b < 4; b++) {
    int pin = 2 + b;
    if (pin == CAN_INT_PIN) continue;
    if (digitalRead(pin) == LOW) din |= (1 << b);
  }

  int a0 = analogRead(A0);
  int a1 = analogRead(A1);
  int a2 = analogRead(A2);
  // TODO: map ADC to centi-°C for your thermistor circuit; placeholder uses raw / 4
  int t0 = (int)((a0 / 1023.0) * 5000.0);
  int t1 = (int)((a1 / 1023.0) * 5000.0);
  int t2 = (int)((a2 / 1023.0) * 5000.0);

  byte data[8];
  data[0] = STATUS_MAGIC;
  data[1] = din;
  data[2] = t0 & 0xFF;
  data[3] = (t0 >> 8) & 0xFF;
  data[4] = t1 & 0xFF;
  data[5] = (t1 >> 8) & 0xFF;
  data[6] = t2 & 0xFF;
  data[7] = (t2 >> 8) & 0xFF;

  CAN.sendMsgBuf(ID_STATUS, 0, 8, data);
}

void applyOutputs() {
  if (listenOnly) {
    digitalWrite(LED_BUILTIN, LOW);
    return;
  }
  for (int b = 0; b < 4; b++) {
    digitalWrite(6 + b, (digitalOut >> b) & 1);
  }
  analogWrite(3, pwmAux);
  digitalWrite(LED_BUILTIN, (digitalOut & 1) ? HIGH : LOW);
}
