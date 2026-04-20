# Smarter Pet Feeder

An IoT-based automatic pet feeder built on an **Arduino Uno** (sensor/actuator node) and a **Raspberry Pi 4** (edge device). The system identifies pets via RFID, dispenses the right portion of food, monitors food storage humidity, and provides a live web dashboard for monitoring and control.

---

## What It Can Do

- Detect pet presence using an IR obstacle sensor
- Identify individual pets by scanning their RFID tag
- Automatically dispense food when a registered pet is detected
- Measure the exact amount of food dispensed using a load cell (grams)
- Calculate the ideal portion per pet based on body weight and feeding history
- Monitor food storage temperature and humidity
- Automatically turn a fan on/off based on humidity thresholds
- Send live sensor data to a Raspberry Pi over serial (USB)
- Store all sensor readings and feeding events in a MariaDB database
- Serve a web dashboard showing live readings, history, analytics, and manual controls
- Schedule automated feedings at set times of day
- Manage pet profiles (name, RFID tag, weight, portion target)
- Accept manual commands from the dashboard (feed, fan on/off, servo open/close)

---

## System Architecture

```
┌─────────────────────────┐        Serial (USB)        ┌──────────────────────────────┐
│      Arduino Uno        │ ─────────────────────────► │      Raspberry Pi 4          │
│   (Sensor/Actuator      │ ◄───────────────────────── │      (Edge Device)           │
│        Node)            │                             │                              │
│                         │                             │  • Stores data in MariaDB    │
│  • Reads all sensors    │                             │  • Runs automation rules     │
│  • Controls servo       │                             │  • Schedules feedings        │
│  • Controls fan (relay) │                             │  • Hosts Flask web dashboard │
│  • RFID detection       │                             │  • Serves analytics & history│
└─────────────────────────┘                             └──────────────────────────────┘
```

---

## Hardware Components

| Component            | Type     | Pin(s)           | Purpose                                         |
|----------------------|----------|------------------|-------------------------------------------------|
| IR Obstacle Sensor   | Digital  | D2               | Detects when a pet approaches the feeder        |
| DHT11                | Digital  | D3               | Measures temperature and humidity               |
| HX711 DT             | Digital  | D4               | Load cell data line (food bowl weight)          |
| HX711 SCK            | Digital  | D5               | Load cell clock line                            |
| Servo Motor          | PWM      | D6               | Opens/closes the food dispensing hatch          |
| Relay Module         | Digital  | D7               | Switches the 5V DC fan on or off                |
| RFID RST             | Digital  | D9               | RFID reader reset pin                           |
| RFID SDA (SS)        | Digital  | D10              | RFID SPI chip select                            |
| RFID MOSI            | SPI      | D11              | SPI data out to RFID reader                     |
| RFID MISO            | SPI      | D12              | SPI data in from RFID reader                    |
| RFID SCK             | SPI      | D13              | SPI clock for RFID reader                       |
| Potentiometer        | Analog   | A5               | Simulates cat body weight (pressure mat input)  |
| 5V DC Fan            | Actuator | Via relay (D7)   | Controls humidity inside the food storage area  |
| 5kg Load Cell        | Analog   | Via HX711 (D4/5) | Measures food weight dispensed into the bowl    |

---

## Project Structure

```
SmarterPetFeeder/
│
├── arduino/
│   ├── smartPetFeeder.ino      # Main Arduino sketch — sensor reading, serial comms, actuator control
│   └── componentTable.md       # Hardware component reference table
│
└── edge/
    ├── main.py                 # Entry point — starts serial bridge, scheduler, and Flask server
    ├── config.py               # Configuration (serial port, DB credentials, Flask settings)
    ├── requirements.txt        # Python dependency list
    │
    ├── serialComm/
    │   ├── __init__.py
    │   └── serialBridge.py     # Reads Arduino serial output, parses messages, dispatches commands
    │
    ├── database/
    │   ├── db.py               # All database queries and helper functions
    │   ├── schema.sql          # MariaDB table definitions (sensor_readings, feed_log, pets, etc.)
    │   └── migration_pet_profiles.sql  # Migration adding pet profile fields
    │
    ├── automation/
    │   ├── rules.py            # Real-time rules (e.g. humidity → fan control)
    │   ├── historicalRules.py  # History-based logic (rolling average for portion sizing)
    │   ├── feedingSession.py   # State machine managing a full feeding session lifecycle
    │   └── scheduler.py       # Time-based feeding scheduler (triggers sessions at set times)
    │
    └── dashboard/
        ├── app.py              # Flask app — all REST API routes and page routes
        ├── templates/
        │   ├── layout.html     # Base HTML layout (navbar, shared structure)
        │   ├── index.html      # Live dashboard (current sensor readings)
        │   ├── analytics.html  # Historical charts and statistics
        │   └── manage.html     # Pet profiles, schedules, settings, and manual controls
        └── static/
            ├── css/            # Stylesheet(s)
            └── js/             # Frontend JavaScript (dashboard updates, API calls)
```

---

## Software & Libraries

### Arduino (C++ / Arduino IDE)

| Library     | Purpose                                                          |
|-------------|------------------------------------------------------------------|
| `Servo.h`   | Controls the servo motor for food dispensing                     |
| `SPI.h`     | SPI bus communication (used by the RFID reader)                  |
| `MFRC522.h` | Reads RFID tags — identifies which pet is at the feeder          |
| `DHT.h`     | Reads temperature and humidity from the DHT11 sensor             |
| `HX711.h`   | Interfaces with the HX711 amplifier to read load cell weight     |

The sketch uses the built-in `Serial` library for two-way communication with the Raspberry Pi over USB.

---

### Edge Device — Raspberry Pi 4 (Python 3)

| Software / Library    | Purpose                                                                      |
|-----------------------|------------------------------------------------------------------------------|
| **Python 3**          | Primary language for all edge-side logic                                     |
| **Flask**             | Lightweight web framework — serves the dashboard and REST API                |
| **pyserial**          | Reads and writes serial data to/from the Arduino over USB                    |
| **mariadb connector** | Connects Python to the MariaDB database                                      |
| **opencv-python-headless** | Computer vision library (available for future camera-based pet detection) |
| **numpy**             | Numerical processing support (used alongside OpenCV)                         |
| **MariaDB**           | Relational database — stores sensor readings, feeding events, pet profiles, schedules, and settings |
| **HTML / CSS / JS**   | Frontend of the web dashboard — live readings, charts, controls, and settings |

#### Python Setup (on Raspberry Pi)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Running the System

```bash
source venv/bin/activate
python main.py
```

The dashboard will be available at `http://<pi-ip-address>:5000`.

---

## Serial Protocol

**Arduino → Raspberry Pi**

```
DATA,TEMP=26.0,HUM=72,IR=1,POT=520,FAN=1,SERVO=0,BOWL=45.3
RFID,04A3BC29
STATUS,FAN=1,SERVO=0
FEED_DONE
```

**Raspberry Pi → Arduino**

```
FEED            # Dispense food (timed open/close)
FEED,<grams>    # Dispense until bowl gains this many grams
FAN_ON          # Turn fan on
FAN_OFF         # Turn fan off
SERVO_OPEN      # Open servo manually
SERVO_CLOSE     # Close servo manually
TARE            # Re-zero the load cell
STATUS          # Request current actuator state
```
