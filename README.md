# Smarter Pet Feeder

## What it is

Smarter Pet Feeder is an IoT pet-feeding system with two nodes:
- **Arduino Uno**: reads sensors and controls actuators (servo, fan relay, RFID, load cell, potentiometer).
- **Raspberry Pi 4**: runs edge logic, stores data, calculates portions, and hosts a Flask dashboard.

It uses a feeding-session flow (IR detect -> pet identify -> calculate portion -> dispense -> log results) with historical weight-based prediction.

## What it can do

- Detect pet approach (IR) and identify pets by RFID.
- Run scheduled feeding windows and handle one or multiple pets per window.
- Calculate next portion using:
  - latest recorded pet weight/history,
  - `food_per_kg`,
  - optional `ideal_weight_kg` adjustment trend,
  - safety clamp (20-150g).
- Save each feeding session with measured weight-at-feed and dispensed result.
- Monitor temperature/humidity and auto-control fan by humidity threshold.
- Show live data, analytics, schedules, and pet profile management on the web dashboard.
- Accept manual commands from dashboard (feed, fan, servo, status).

## Hardware Components

| Component | Type | Pin(s) | Purpose |
|---|---|---|---|
| IR Obstacle Sensor | Digital | D2 | Detects pet presence near feeder |
| DHT11 | Digital | D3 | Temperature and humidity sensing |
| HX711 DT | Digital | D4 | Load cell data line |
| HX711 SCK | Digital | D5 | Load cell clock line |
| Servo Motor | PWM | D6 | Opens/closes food gate |
| Relay Module | Digital | D7 | Switches fan ON/OFF |
| RFID RST | Digital | D9 | RFID reset pin |
| RFID SDA (SS) | Digital | D10 | RFID SPI select |
| RFID MOSI | SPI | D11 | SPI data to RFID |
| RFID MISO | SPI | D12 | SPI data from RFID |
| RFID SCK | SPI | D13 | SPI clock |
| Potentiometer | Analog | A5 | Simulated cat weight input |
| 5V DC Fan | Actuator | Via relay (D7) | Lowers humidity in storage area |
| 5kg Load Cell | Analog | Via HX711 (D4/D5) | Measures bowl weight/dispensed food |

## Project Structure

```text
SmarterPetFeeder/
├── README.md
├── arduino/
│   ├── smartPetFeeder.ino
│   └── componentTable.md
└── edge/
    ├── main.py
    ├── config.py
    ├── requirements.txt
    ├── serialComm/
    │   ├── __init__.py
    │   └── serialBridge.py
    ├── automation/
    │   ├── rules.py
    │   ├── historicalRules.py
    │   ├── feedingSession.py
    │   └── scheduler.py
    ├── database/
    │   ├── db.py
    │   └── schema.sql
    └── dashboard/
        ├── app.py
        ├── templates/
        └── static/
```

## Setup and Running on Pi

From `SmarterPetFeeder\edge`:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set `config.py` as needed (serial port, DB credentials, Flask host/port).

Initialize DB schema:
Open **phpMyAdmin**, then create or select the `petfeeder` database and run the SQL code from `database/schema.sql` using the **SQL** tab.
```text
1. Open phpMyAdmin in your browser
2. Create or select database: petfeeder
3. Click the SQL tab
4. Copy all contents from database/schema.sql
5. Paste the SQL code
6. Click Run
```

Start the system:

```bash
source venv/bin/activate
python main.py
```

Dashboard: `http://<pi-ip>:5000`

## Serial Protocol

### What the Arduino sends -> Raspberry Pi

```text
DATA,TEMP=26.0,HUM=72,IR=1,POT=520,FAN=1,SERVO=0,BOWL=45.3
RFID,04A3BC29
STATUS,FAN=1,SERVO=0
FEED_DONE
```

- `DATA`: sensor/actuator snapshot.
- `RFID,<uid>`: scanned pet tag.
- `STATUS`: current actuator states.
- `FEED_DONE`: dispensing cycle completed.

### What the Raspberry Pi can instruct -> Arduino

```text
FEED
FEED,<grams>
FAN_ON
FAN_OFF
SERVO_OPEN
SERVO_CLOSE
TARE
STATUS
```

- `FEED`: simple feed trigger.
- `FEED,<grams>`: target-grams dispensing command used by portion prediction.
- `FAN_ON`/`FAN_OFF`: relay control.
- `SERVO_OPEN`/`SERVO_CLOSE`: manual gate control.
- `TARE`: reset load-cell zero.
- `STATUS`: request current state.
