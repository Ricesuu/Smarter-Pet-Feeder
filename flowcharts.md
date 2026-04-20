# Smarter Pet Feeder — Flowcharts

All flowcharts are written in **Mermaid syntax**.
To use in draw.io: open draw.io → **Insert → Advanced → Mermaid** → paste the code block.

---

## Table of Contents

### Arduino
1. [System Initialization (setup)](#1-system-initialization-setup)
2. [Main Loop](#2-main-loop)
3. [Send Sensor Data (sendSensorData)](#3-send-sensor-data-sendsensordata)
4. [Humidity Check & Fan Control (checkHumidity)](#4-humidity-check--fan-control-checkhumidity)
5. [RFID Detection (checkRFID)](#5-rfid-detection-checkrfid)
6. [Serial Command Handler (handleSerial)](#6-serial-command-handler-handleserial)
7. [Timed Feed (triggerFeed)](#7-timed-feed-triggerfeed)
8. [Servo Open / Close](#8-servo-open--close)
9. [Precision Dispensing via Load Cell (checkDispensing)](#9-precision-dispensing-via-load-cell-checkdispensing)

### Edge Device (Raspberry Pi)
10. [System Startup (main.py)](#10-system-startup-mainpy)
11. [Serial Bridge Main Loop](#11-serial-bridge-main-loop)
12. [Serial Message Parser (parseMessage)](#12-serial-message-parser-parsemessage)
13. [DATA Message Handler](#13-data-message-handler)
14. [RFID Message Handler](#14-rfid-message-handler)
15. [Automation Rules — Humidity Fan (evaluateRules)](#15-automation-rules--humidity-fan-evaluaterules)
16. [Feeding Session State Machine](#16-feeding-session-state-machine)
17. [Ideal Portion Calculation (calcIdealPortion)](#17-ideal-portion-calculation-calcidealportion)
18. [Scheduled Feeding Checker](#18-scheduled-feeding-checker)
19. [Session Timeout Watcher](#19-session-timeout-watcher)
20. [Command Queue Flow (Dashboard → DB → Arduino)](#20-command-queue-flow-dashboard--db--arduino)
21. [Live Dashboard Data Refresh](#21-live-dashboard-data-refresh)
22. [Analytics API Data Flow](#22-analytics-api-data-flow)
23. [Pet Profile Management (CRUD)](#23-pet-profile-management-crud)
24. [Feed Schedule Management (CRUD)](#24-feed-schedule-management-crud)

---

## Arduino

---

### 1. System Initialization (setup)

Runs once on power-on. Sets up all hardware: serial, SPI bus, RFID reader, DHT11, load cell (HX711), servo, IR sensor pin, and relay pin.

```mermaid
flowchart TD
    A([START]) --> B[Serial.begin 9600]
    B --> C[SPI.begin]
    C --> D[rfid.PCD_Init]
    D --> E[dht.begin]
    E --> F[scale.begin DT=D4 SCK=D5]
    F --> G[scale.set_scale CALIBRATION_FACTOR]
    G --> H[scale.tare — zero bowl weight]
    H --> I[feederServo.attach pin D6]
    I --> J[feederServo.write 0 — servo closed]
    J --> K[pinMode IR D2 INPUT]
    K --> L[pinMode RELAY D7 OUTPUT]
    L --> M[digitalWrite RELAY HIGH — fan OFF at startup]
    M --> N([END — enter loop])
```

---

### 2. Main Loop

The Arduino loop runs continuously at ~500ms intervals. It processes serial commands, checks dispensing progress, reads and broadcasts sensor data, and scans for RFID tags.

```mermaid
flowchart TD
    A([loop begins]) --> B[handleSerial\nread and process any incoming command]
    B --> C[checkDispensing\nstop servo if portion target reached]
    C --> D[sendSensorData\nread all sensors and transmit over serial]
    D --> E[checkRFID\nscan for RFID tag]
    E --> F[delay 500ms]
    F --> A
```

---

### 3. Send Sensor Data (sendSensorData)

Reads all sensors every loop iteration and sends a formatted DATA message over serial to the Raspberry Pi.

```mermaid
flowchart TD
    A([START]) --> B[Read temperature from DHT11]
    B --> C[Read humidity from DHT11]
    C --> D[digitalRead IR pin D2]
    D --> E{irRaw == LOW?}
    E -->|Yes — pet detected| F[irVal = 1]
    E -->|No — clear| G[irVal = 0]
    F --> H[analogRead POT pin A5]
    G --> H
    H --> I[scale.get_units 5 — average 5 load cell readings]
    I --> J{bowlGrams less than 0?}
    J -->|Yes — clamp negative drift| K[bowlGrams = 0]
    J -->|No| L[Keep value]
    K --> M[Serial.print DATA,TEMP=,HUM=,IR=,POT=,FAN=,SERVO=,BOWL=]
    L --> M
    M --> N([END])
```

---

### 4. Humidity Check & Fan Control (checkHumidity)

Compares current humidity against the threshold and controls the relay/fan. Only acts if the state needs to change to avoid sending duplicate commands.

```mermaid
flowchart TD
    A([START]) --> B[Read humidity from DHT11]
    B --> C{humidity greater than HUMIDITY_THRESHOLD 70 percent?}
    C -->|Yes| D[shouldBeOn = true]
    C -->|No| E[shouldBeOn = false]
    D --> F{shouldBeOn == fanState?\nno change needed}
    E --> F
    F -->|Same — no action| G([RETURN])
    F -->|Different — update| H[fanState = shouldBeOn]
    H --> I{fanState true?}
    I -->|Yes| J[digitalWrite RELAY LOW — fan ON]
    I -->|No| K[digitalWrite RELAY HIGH — fan OFF]
    J --> G
    K --> G
```

---

### 5. RFID Detection (checkRFID)

Checks if an RFID tag is present each loop cycle. If a tag is detected, reads its UID and transmits it to the Raspberry Pi.

```mermaid
flowchart TD
    A([START]) --> B{New RFID card present?}
    B -->|No| C([RETURN])
    B -->|Yes| D{PICC_ReadCardSerial success?}
    D -->|No| C
    D -->|Yes| E[Loop through uid.uidByte array]
    E --> F[Append each byte as 2-char hex string]
    F --> G[uid.toUpperCase]
    G --> H[Serial.println RFID comma UID]
    H --> I[rfid.PICC_HaltA — stop card communication]
    I --> C
```

---

### 6. Serial Command Handler (handleSerial)

Reads any incoming command from the Raspberry Pi and routes it to the appropriate action. Supports timed feed, precision gram-based feed, fan control, servo control, tare, and status request.

```mermaid
flowchart TD
    A([START]) --> B{Serial.available?}
    B -->|No| Z([RETURN])
    B -->|Yes| C[Serial.readStringUntil newline]
    C --> D[cmd.trim]
    D --> E{cmd == FEED?}
    E -->|Yes| F[triggerFeed\nopen servo 1.5s then close]
    E -->|No| G{cmd starts with FEED comma?}
    G -->|Yes| H[Parse grams from cmd substring 5]
    H --> I[feedTargetGrams = parsed float]
    I --> J[openServo — start dispensing]
    G -->|No| K{cmd == FAN_ON?}
    K -->|Yes| L[fanState = true\ndigitalWrite RELAY LOW]
    K -->|No| M{cmd == FAN_OFF?}
    M -->|Yes| N[fanState = false\ndigitalWrite RELAY HIGH]
    M -->|No| O{cmd == SERVO_OPEN?}
    O -->|Yes| P[openServo]
    O -->|No| Q{cmd == SERVO_CLOSE?}
    Q -->|Yes| R[closeServo]
    Q -->|No| S{cmd == TARE?}
    S -->|Yes| T[scale.tare — re-zero load cell]
    S -->|No| U{cmd == STATUS?}
    U -->|Yes| V[sendStatus — print FAN and SERVO state]
    U -->|No| Z
    F --> Z
    J --> Z
    L --> Z
    N --> Z
    P --> Z
    R --> Z
    T --> Z
    V --> Z
```

---

### 7. Timed Feed (triggerFeed)

Simple timed dispensing: opens servo for 1.5 seconds then closes. Used when a plain FEED command is received with no gram target.

```mermaid
flowchart TD
    A([START]) --> B[openServo — feederServo.write 90 degrees]
    B --> C[delay 1500ms]
    C --> D[closeServo — feederServo.write 0 degrees]
    D --> E([END])
```

---

### 8. Servo Open / Close

Two helper functions. openServo snapshots the current bowl weight before dispensing begins so the gain can be measured. closeServo resets the servo and state flag.

```mermaid
flowchart TD
    A([openServo START]) --> B[bowlWeightBefore = scale.get_units 5\nsnapshot bowl weight before dispensing]
    B --> C[servoState = true]
    C --> D[feederServo.write 90 degrees — open hatch]
    D --> E([openServo END])

    F([closeServo START]) --> G[servoState = false]
    G --> H[feederServo.write 0 degrees — close hatch]
    H --> I([closeServo END])
```

---

### 9. Precision Dispensing via Load Cell (checkDispensing)

Runs every loop cycle during a precision feed. Continuously reads the bowl weight and closes the servo once the target number of grams has been dispensed.

```mermaid
flowchart TD
    A([START]) --> B{servoState == true\nAND feedTargetGrams >= 0?}
    B -->|No — not dispensing| C([RETURN])
    B -->|Yes| D[currentBowl = scale.get_units 3]
    D --> E[gained = currentBowl minus bowlWeightBefore]
    E --> F{gained >= feedTargetGrams?}
    F -->|No — keep dispensing| C
    F -->|Yes — target reached| G[closeServo]
    G --> H[feedTargetGrams = -1 — reset target]
    H --> I[Serial.println FEED_DONE]
    I --> C
```

---

## Edge Device (Raspberry Pi)

---

### 10. System Startup (main.py)

Entry point for the entire edge system. Launches the serial bridge as a background thread, starts the scheduler threads, then runs the Flask server on the main thread.

```mermaid
flowchart TD
    A([python main.py]) --> B[Create serialBridge thread — daemon=true]
    B --> C[serialThread.start]
    C --> D[startScheduler\nlaunches scheduledFeedChecker and sessionTimeoutWatcher threads]
    D --> E[Print dashboard URL to console]
    E --> F[app.run Flask — blocking call on main thread]
    F --> G([Server running — all threads active])
```

---

### 11. Serial Bridge Main Loop

Core background process. Continuously pulls queued commands from the database and sends them to Arduino, then reads and processes every incoming serial line from Arduino.

```mermaid
flowchart TD
    A([run START]) --> B[serial.Serial open config port at 9600 baud]
    B --> C[time.sleep 2 — wait for Arduino to boot]
    C --> D[Loop forever]
    D --> E[popPendingCommands from DB]
    E --> F{Commands found?}
    F -->|Yes| G[sendCommand each — write to serial]
    G --> H[Read line from serial readline]
    F -->|No| H
    H --> I{Line empty?}
    I -->|Yes — skip| D
    I -->|No| J[handleMessage raw line]
    J --> K{Exception occurred?}
    K -->|Yes| L[Print error — sleep 1s]
    L --> D
    K -->|No| D
```

---

### 12. Serial Message Parser (parseMessage)

Parses raw ASCII strings from the Arduino into structured Python dicts. Handles four message types: DATA, RFID, STATUS, FEED_DONE.

```mermaid
flowchart TD
    A([parseMessage raw]) --> B{raw is empty?}
    B -->|Yes| C([return None])
    B -->|No| D[Split string by comma]
    D --> E[msgType = parts index 0]
    E --> F{msgType?}
    F -->|DATA| G[Loop remaining parts\nparse each key=value pair\nauto-cast int or float]
    G --> H([return type=DATA payload=dict])
    F -->|RFID| I([return type=RFID payload=UID string])
    F -->|STATUS| J[Loop parts\nparse each key=int pair]
    J --> K([return type=STATUS payload=dict])
    F -->|FEED_DONE| L([return type=FEED_DONE payload=empty dict])
    F -->|Unknown| M([return None])
```

---

### 13. DATA Message Handler

Processes every DATA message from Arduino: stores the reading to the database, evaluates automation rules, updates the pot-based weight simulation, and notifies any active feeding session of IR state.

```mermaid
flowchart TD
    A([DATA message received]) --> B[insertSensorReading payload to MariaDB]
    B --> C[evaluateRules payload sendCommand\ncheck humidity threshold]
    C --> D[updateCatWeight POT value\nstore latest simulated weight]
    D --> E{Active feeding session exists?}
    E -->|No| F([END])
    E -->|Yes| G{IR value == 1?\npet at feeder}
    G -->|No| F
    G -->|Yes| H[session.onIrDetected\nadvance session state]
    H --> F
```

---

### 14. RFID Message Handler

Processes RFID scan events: logs the event to the database, looks up which pet owns that tag, and notifies the active feeding session to begin identification and dispensing.

```mermaid
flowchart TD
    A([RFID message received]) --> B[Extract UID string from payload]
    B --> C[getPetByRfid UID — query pets table]
    C --> D{Pet found in DB?}
    D -->|No| E[insertRfidEvent UID petId=None\nunknown tag]
    D -->|Yes| F[insertRfidEvent UID pet id]
    E --> G{Active feeding session?}
    F --> G
    G -->|No| H([Log: RFID scanned outside active session])
    G -->|Yes| I{Pet was found?}
    I -->|No| H
    I -->|Yes| J[session.onPetIdentified pet trigger=RFID]
    J --> K([END])
    H --> K
```

---

### 15. Automation Rules — Humidity Fan (evaluateRules)

Real-time rule that compares current humidity to the configurable threshold. Only sends a command if the fan state needs to change, preventing repeated serial writes.

```mermaid
flowchart TD
    A([evaluateRules data sendCommand]) --> B[getSettings from DB\nfetch humidity_threshold]
    B --> C[humThreshold = setting value or default 70]
    C --> D{data HUM greater than humThreshold?}
    D -->|Yes| E[shouldFanBeOn = true]
    D -->|No| F[shouldFanBeOn = false]
    E --> G{shouldFanBeOn different from _lastFanState?}
    F --> G
    G -->|No change| H([RETURN — no command sent])
    G -->|State changed| I[_lastFanState = shouldFanBeOn]
    I --> J{shouldFanBeOn?}
    J -->|Yes| K[sendCommand FAN_ON]
    J -->|No| L[sendCommand FAN_OFF]
    K --> H
    L --> H
```

---

### 16. Feeding Session State Machine

Full lifecycle of a single feeding window. A session is started by the scheduler or manually. It transitions through states as IR detection and RFID scanning occur, supports multiple pets within one window, and ends on completion or timeout.

```mermaid
flowchart TD
    A([startSession called]) --> B{Session already active?}
    B -->|Yes| C([Return existing session])
    B -->|No| D[Create new FeedingSession object]
    D --> E[state = WAITING_FOR_IR\nrecord startTime]

    E --> F{IR detected?\nonIrDetected called}
    F -->|No| G{Session expired?}
    G -->|Yes| TOUT[state = TIMEOUT\nclearSession]
    G -->|No| F
    F -->|Yes| H{Session expired?}
    H -->|Yes| TOUT
    H -->|No| I[state = WAITING_FOR_PET]

    I --> J{RFID scanned?\nonPetIdentified called}
    J -->|No| K{Session expired?}
    K -->|Yes| TOUT
    K -->|No| J
    J -->|Yes| L{Pet already fed\nthis session?}
    L -->|Yes| M[state = WAITING_FOR_IR\nwait for next pet]
    M --> F
    L -->|No| N[updatePetWeight from POT reading]
    N --> O[calcIdealPortion — calculate target grams]
    O --> P[state = DISPENSING\nsendCommand FEED comma grams\nlogFeedEvent to DB]

    P --> Q{FEED_DONE received?\nonFeedDone called}
    Q -->|Waiting| Q
    Q -->|Yes| R[Read bowl weight after from DB]
    R --> S[Calculate actual portion dispensed\nupdate feed_log with actual measurements]
    S --> T{Session still valid?\nnot expired}
    T -->|Yes| M
    T -->|No| U[state = DONE\nclearSession]

    TOUT --> V([Session ended])
    U --> V
```

---

### 17. Ideal Portion Calculation (calcIdealPortion)

Three-tier priority system for calculating how many grams to dispense for a specific pet. Prioritises the pet's weight profile, then feeding history, then a simple ADC-based fallback.

```mermaid
flowchart TD
    A([calcIdealPortion pet_id cat_weight_sim]) --> B[Query pets table for weight_kg and food_per_kg]
    B --> C{weight_kg AND food_per_kg both set?}
    C -->|Yes| D[portion = weight_kg times food_per_kg\nProfile formula — Priority 1]
    D --> E[Clamp result to range 20–150g]
    E --> F([Return portion])
    C -->|No| G[Query last 5 feed_log entries for this pet\nwhere portion_grams is not null]
    G --> H{3 or more valid historical portions found?}
    H -->|Yes| I[portion = average of up to 5 recent feedings\nRolling historical average — Priority 2]
    H -->|No| J[portion = 30 plus cat_weight_sim divided by 1023 times 50\nADC fallback formula — Priority 3]
    I --> E
    J --> E
```

---

### 18. Scheduled Feeding Checker

Background thread that runs every 15 seconds. Checks if any enabled feed schedule matches the current time and has not already been triggered today. If so, starts a feeding session.

```mermaid
flowchart TD
    A([Thread starts]) --> B[Loop forever]
    B --> C[now = datetime.now]
    C --> D[currentTime = HH:MM string]
    D --> E[todayKey = YYYY-MM-DD string]
    E --> F[getFeedSchedules from DB\nonly enabled=1 schedules]
    F --> G{More schedules to check?}
    G -->|No| H[sleep 15 seconds]
    H --> B
    G -->|Yes| I[Get next schedule from list]
    I --> J{schedule.time_of_day == currentTime?}
    J -->|No| G
    J -->|Yes| K{Key already in _triggeredToday set?}
    K -->|Yes — already fired today| G
    K -->|No| L[Add key to _triggeredToday set]
    L --> M[touchScheduleLastTriggered in DB\nrecord last triggered time]
    M --> N[startSession sendCommand\nbegin feeding window]
    N --> G
```

---

### 19. Session Timeout Watcher

Background thread that runs every 30 seconds. Checks if an active session has exceeded its time window and terminates it if so.

```mermaid
flowchart TD
    A([Thread starts]) --> B[sleep 30 seconds]
    B --> C[session = getSession]
    C --> D{Active session exists?}
    D -->|No| B
    D -->|Yes| E[session.checkTimeout]
    E --> F{State is DONE, TIMEOUT, or IDLE?}
    F -->|Yes — already finished| B
    F -->|No — still running| G{time elapsed greater than windowSeconds?}
    G -->|No — still within window| B
    G -->|Yes — session expired| H[state = TIMEOUT\nclearSession]
    H --> B
```

---

### 20. Command Queue Flow (Dashboard → DB → Arduino)

Shows how a manual command issued from the web dashboard travels through the system: validated and queued in the database by Flask, picked up by the serial bridge, and forwarded to the Arduino.

```mermaid
flowchart TD
    A([User clicks button on web dashboard]) --> B[JS fetch POST /api/command with command string]
    B --> C[Flask apiCommand receives request]
    C --> D{Command in allowed list?\nFEED FAN_ON FAN_OFF SERVO_OPEN SERVO_CLOSE STATUS}
    D -->|No| E([Return 400 Invalid command])
    D -->|Yes| F[queueCommand — INSERT row into pending_commands table]
    F --> G{cmd == FEED?}
    G -->|Yes| H[logFeedEvent petId=None trigger=manual]
    G -->|No| I[Return JSON status=queued]
    H --> I
    I --> J[Serial bridge loop calls popPendingCommands]
    J --> K[SELECT then DELETE rows from pending_commands\nreturn command strings]
    K --> L[sendCommand — write cmd plus newline to serial port]
    L --> M([Arduino receives command and executes])
```

---

### 21. Live Dashboard Data Refresh

The index page polls the /api/latest endpoint every 5 seconds via JavaScript to keep all sensor readings current without a full page reload.

```mermaid
flowchart TD
    A([Browser loads index page]) --> B[index.html rendered by Flask]
    B --> C[JS setInterval every 5000ms]
    C --> D[fetch GET /api/latest]
    D --> E[Flask apiLatest called]
    E --> F[getLatestReading — SELECT from sensor_readings ORDER BY timestamp DESC LIMIT 1]
    F --> G[Build JSON response\ntemp hum IR bowl fan servo timestamp]
    G --> H[Add cat_weight_kg converted from POT ADC value]
    H --> I[Add rfid_today count for today]
    I --> J[Return JSON]
    J --> K[JS updates DOM elements on page]
    K --> C
```

---

### 22. Analytics API Data Flow

The /api/analytics endpoint aggregates sensor and feeding data for a configurable time window and returns statistics used to populate the analytics page charts and summary cards.

```mermaid
flowchart TD
    A([GET /api/analytics?hours=24]) --> B[getAnalyticsExtended hours]
    B --> C[Query sensor_readings\nAVG MIN MAX temperature and humidity\nSUM fan_on rows and COUNT total rows]
    C --> D[Calculate fan_on_pct percentage\nCalculate estimated fan_runtime_min]
    D --> E[Query feed_log COUNT for time window]
    E --> F[getTotalReadings — count of sensor rows in window]
    F --> G[getRfidStats — total RFID scans and avg per day]
    G --> H[getAvgPortion — average portion_grams from feed_log]
    H --> I[Merge all stats into single JSON object]
    I --> J([Return JSON — charts and stat cards update on page])
```

---

### 23. Pet Profile Management (CRUD)

Covers the full create/read/update/delete lifecycle for pet profiles on the Manage page. Pet profiles store the RFID tag UID, body weight, and food-per-kg ratio used to calculate portion targets.

```mermaid
flowchart TD
    A([Manage page loaded]) --> B[GET /api/pets]
    B --> C[getAllPets from DB\nattach calc_portion if weight and food_per_kg are set]
    C --> D[Render pet list on page]
    D --> E{User action?}
    E -->|Add new pet| F[POST /api/pets\nname and optional rfid_uid]
    E -->|Edit existing pet| G[PUT /api/pets/id\nname rfid_uid food_per_kg]
    E -->|Delete pet| H[DELETE /api/pets/id]
    F --> I{Name provided?}
    I -->|No| J([Return 400 Name is required])
    I -->|Yes| K[addPet — INSERT into pets table]
    G --> L[updatePet — UPDATE name rfid food_per_kg fields]
    H --> M[deletePet — DELETE from pets\nfeed_log references SET NULL]
    K --> N[Refresh pet list]
    L --> N
    M --> N
    N --> D
```

---

### 24. Feed Schedule Management (CRUD)

Covers creating and deleting scheduled feeding times from the Manage page. The scheduler thread reads enabled schedules every 15 seconds and triggers sessions automatically at match time.

```mermaid
flowchart TD
    A([Manage page loaded]) --> B[GET /api/schedules]
    B --> C[getAllSchedules from DB\nORDER BY time_of_day ASC]
    C --> D[Render schedule list on page]
    D --> E{User action?}
    E -->|Add new schedule| F[POST /api/schedules\nbody contains time_of_day HH:MM]
    E -->|Delete schedule| G[DELETE /api/schedules/id]
    F --> H{Valid HH:MM format?\nlen == 5}
    H -->|No| I([Return 400 Invalid time format])
    H -->|Yes| J[addSchedule — INSERT into feed_schedules enabled=1]
    G --> K[deleteSchedule — DELETE from feed_schedules]
    J --> L[Refresh schedule list]
    K --> L
    L --> D
```
