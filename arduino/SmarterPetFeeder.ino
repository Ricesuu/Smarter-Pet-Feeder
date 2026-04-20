/*
=========================================================
 SMARTER PET FEEDER — Arduino Uno
*/

#include <Servo.h>
#include <SPI.h>
#include <MFRC522.h>
#include <DHT.h>
#include "HX711.h"

/*=========================================================
  PIN CONFIGURATION
=========================================================*/
#define PIN_IR          2
#define PIN_DHT         3
#define PIN_HX711_DT    4
#define PIN_HX711_SCK   5
#define PIN_SERVO       6
#define PIN_RELAY       7
#define PIN_RFID_RST    9
#define PIN_RFID_SDA    10
#define PIN_CAT_WT      A5

/*=========================================================
  SENSOR / SYSTEM SETTINGS
=========================================================*/
#define DHT_TYPE DHT11
#define HUMIDITY_THRESHOLD 70

/*
---------------------------------------------------------
 HX711 Calibration
---------------------------------------------------------
 To calibrate:
 1. Set CALIBRATION_FACTOR to 1.0
 2. Place known weight on scale
 3. Record reading
 4. Use:

    calibration = rawReading / knownWeight

 Typical range: 2000 to 3000
---------------------------------------------------------
*/
#define CALIBRATION_FACTOR 650

/*=========================================================
  OBJECT INITIALIZATION
=========================================================*/
HX711 scale;
Servo feederServo;
MFRC522 rfid(PIN_RFID_SDA, PIN_RFID_RST);
DHT dht(PIN_DHT, DHT_TYPE);

/*=========================================================
  GLOBAL VARIABLES
=========================================================*/
bool fanState = false;
bool servoState = false;

float feedTargetGrams = -1;     // -1 means inactive
float bowlWeightBefore = 0;     // Bowl weight before dispensing

/*=========================================================
  FUNCTION DECLARATIONS
=========================================================*/
void handleSerial();
void sendSensorData();
void checkHumidity();
void checkRFID();
void triggerFeed();
void checkDispensing();
void openServo();
void closeServo();
void sendStatus();

/*=========================================================
  SETUP
  Runs once during startup
=========================================================*/
void setup() {
  Serial.begin(9600);

  // Start SPI for RFID
  SPI.begin();
  rfid.PCD_Init();

  // Start DHT sensor
  dht.begin();

  // Start load cell
  scale.begin(PIN_HX711_DT, PIN_HX711_SCK);
  scale.set_scale(CALIBRATION_FACTOR);
  scale.tare();   // Zero bowl weight on startup

  // Servo setup
  feederServo.attach(PIN_SERVO);
  feederServo.write(0);

  // Pin modes
  pinMode(PIN_IR, INPUT);
  pinMode(PIN_RELAY, OUTPUT);

  // Relay is active LOW
  digitalWrite(PIN_RELAY, HIGH);
}

/*=========================================================
  MAIN LOOP
  Runs repeatedly
=========================================================*/
void loop() {
  handleSerial();
  checkDispensing();
  checkHumidity();
  sendSensorData();
  checkRFID();

  delay(500);
}

/*=========================================================
  SENSOR DATA TRANSMISSION
  Sends all sensor readings through Serial
=========================================================*/
void sendSensorData() {
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();

  // IR sensor active LOW
  int irRaw = digitalRead(PIN_IR);
  int irDetected = (irRaw == LOW) ? 1 : 0;

  // Simulated cat weight
  int catWeight = analogRead(PIN_CAT_WT);

  // Bowl food weight
  float bowlGrams = scale.get_units(5);

  if (bowlGrams < 0) {
    bowlGrams = 0;
  }

  Serial.print("DATA,TEMP=");
  Serial.print(temp);

  Serial.print(",HUM=");
  Serial.print(hum);

  Serial.print(",IR=");
  Serial.print(irDetected);

  Serial.print(",POT=");
  Serial.print(catWeight);

  Serial.print(",FAN=");
  Serial.print(fanState ? 1 : 0);

  Serial.print(",SERVO=");
  Serial.print(servoState ? 1 : 0);

  Serial.print(",BOWL=");
  Serial.println(bowlGrams, 1);
}

/*=========================================================
  HUMIDITY CHECK
  Automatically turns fan ON/OFF
=========================================================*/
void checkHumidity() {
  float hum = dht.readHumidity();
  bool shouldBeOn = hum > HUMIDITY_THRESHOLD;

  if (shouldBeOn == fanState) {
    return;
  }

  fanState = shouldBeOn;

  // Relay active LOW
  digitalWrite(PIN_RELAY, fanState ? LOW : HIGH);
}

/*=========================================================
  RFID CHECK
  Reads RFID card UID and sends to Serial
=========================================================*/
void checkRFID() {
  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }

  String uid = "";

  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uid += "0";
    }

    uid += String(rfid.uid.uidByte[i], HEX);
  }

  uid.toUpperCase();

  Serial.println("RFID," + uid);

  rfid.PICC_HaltA();
}

/*=========================================================
  SERIAL COMMAND HANDLER
  Receives commands from dashboard / host system
=========================================================*/
void handleSerial() {
  if (!Serial.available()) {
    return;
  }

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd == "FEED") {
    triggerFeed();
  }
  else if (cmd.startsWith("FEED,")) {
    feedTargetGrams = cmd.substring(5).toFloat();
    openServo();
  }
  else if (cmd == "FAN_ON") {
    fanState = true;
    digitalWrite(PIN_RELAY, LOW);
  }
  else if (cmd == "FAN_OFF") {
    fanState = false;
    digitalWrite(PIN_RELAY, HIGH);
  }
  else if (cmd == "SERVO_OPEN") {
    openServo();
  }
  else if (cmd == "SERVO_CLOSE") {
    closeServo();
  }
  else if (cmd == "TARE") {
    scale.tare();
  }
  else if (cmd == "STATUS") {
    sendStatus();
  }
}

/*=========================================================
  SIMPLE FEED COMMAND
  Opens servo briefly then closes
=========================================================*/
void triggerFeed() {
  openServo();
  delay(1500);
  closeServo();
}

/*=========================================================
  SMART DISPENSING CHECK
  Stops dispensing once target weight reached
=========================================================*/
void checkDispensing() {
  if (!servoState || feedTargetGrams < 0) {
    return;
  }

  float currentBowl = scale.get_units(3);
  float gained = currentBowl - bowlWeightBefore;

  if (gained >= feedTargetGrams) {
    closeServo();
    feedTargetGrams = -1;

    Serial.println("FEED_DONE");
  }
}

/*=========================================================
  OPEN SERVO
  Starts food dispensing
=========================================================*/
void openServo() {
  bowlWeightBefore = scale.get_units(5);
  servoState = true;

  feederServo.write(90);
}

/*=========================================================
  CLOSE SERVO
  Stops food dispensing
=========================================================*/
void closeServo() {
  servoState = false;

  feederServo.write(0);
}

/*=========================================================
  SEND SYSTEM STATUS
=========================================================*/
void sendStatus() {
  Serial.print("STATUS,FAN=");
  Serial.print(fanState ? 1 : 0);

  Serial.print(",SERVO=");
  Serial.println(servoState ? 1 : 0);
}