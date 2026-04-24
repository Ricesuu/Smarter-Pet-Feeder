"""
db.py - Data access layer for Smarter Pet Feeder

Contains all database operations for:
  - Sensor/RFID/feed logging
  - Analytics and dashboard queries
  - Pet profile and schedule management
  - Portion prediction support and command queue
"""

# ==========Import Statements==========
import pymysql
import config

# ===========Connection Helper===========
# Returns a new DB connection for each operation
def getConnection():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.Cursor
    )

# ===========Insert Operations===========
# Inserts one sensor DATA packet row

def insertSensorReading(data):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sensor_readings (temperature, humidity, ir_state, pot_value, fan_state, servo_state, bowl_weight) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (data.get('TEMP'), data.get('HUM'), data.get('IR'), data.get('POT'), data.get('FAN'), data.get('SERVO'), data.get('BOWL'))
    )
    conn.commit()
    conn.close()

# Inserts one RFID scan event, optionally linked to a known pet
def insertRfidEvent(uid, petId=None):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO rfid_events (uid, pet_id) VALUES (%s, %s)", (uid, petId))
    conn.commit()
    conn.close()

# Inserts a feed event row (created at feed start; finalized later with actuals)
def logFeedEvent(petId, trigger, portion_grams=None, bowl_before=None, bowl_after=None, weight_kg_at_feed=None):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feed_log (pet_id, `trigger`, portion_grams, bowl_before, bowl_after, weight_kg_at_feed) VALUES (%s, %s, %s, %s, %s, %s)",
        (petId, trigger, portion_grams, bowl_before, bowl_after, weight_kg_at_feed)
    )
    conn.commit()
    conn.close()

# ===========Sensor and Analytics Queries===========
# Returns most recent sensor reading row

def getLatestReading():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sensor_readings ORDER BY `timestamp` DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row

# Returns sensor readings for last N hours, optionally limited
def getHistoryByHours(hours=24, limit=None):
    conn = getConnection()
    cur = conn.cursor()
    sql = "SELECT * FROM sensor_readings WHERE `timestamp` >= NOW() - INTERVAL %s HOUR ORDER BY `timestamp` ASC"
    params = [hours]
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows

# Returns latest sensor readings ordered by id descending
def getLatestReadings(limit=10):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sensor_readings ORDER BY id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

# Returns count of readings in selected window
def getTotalReadings(hours=24):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sensor_readings WHERE `timestamp` >= NOW() - INTERVAL %s HOUR",
        (hours,)
    )
    count = cur.fetchone()[0]
    conn.close()
    return int(count)

# Returns min/max/avg temp/humidity summary
def getAnalyticsSummary(hours=24):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            ROUND(AVG(temperature), 2), MIN(temperature), MAX(temperature),
            ROUND(AVG(humidity), 2),    MIN(humidity),    MAX(humidity)
        FROM sensor_readings
        WHERE `timestamp` >= NOW() - INTERVAL %s HOUR
    """, (hours,))
    row = cur.fetchone()
    conn.close()
    keys = ['temp_avg','temp_min','temp_max','hum_avg','hum_min','hum_max']
    return dict(zip(keys, row)) if row else {}

# Returns extended analytics for dashboard cards
def getAnalyticsExtended(hours=24):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            ROUND(AVG(temperature), 1), MIN(temperature), MAX(temperature),
            ROUND(AVG(humidity), 1),    MIN(humidity),    MAX(humidity),
            SUM(CASE WHEN fan_state = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM sensor_readings
        WHERE `timestamp` >= NOW() - INTERVAL %s HOUR
    """, (hours,))
    row = cur.fetchone()
    cur.execute(
        "SELECT COUNT(*) FROM feed_log WHERE `timestamp` >= NOW() - INTERVAL %s HOUR",
        (hours,)
    )
    feed_count = cur.fetchone()[0]
    conn.close()

    if not row or not row[7]:
        return {
            'temp_avg': None, 'temp_min': None, 'temp_max': None,
            'hum_avg': None, 'hum_min': None, 'hum_max': None,
            'fan_on_pct': 0, 'fan_runtime_min': 0,
            'feed_count': int(feed_count), 'feed_avg_per_day': 0
        }

    temp_avg, temp_min, temp_max, hum_avg, hum_min, hum_max, fan_on, total = row
    fan_on = fan_on or 0
    fan_on_pct = round((fan_on / total) * 100, 1) if total else 0
    fan_runtime_min = round((fan_on * 5) / 60, 1)

    days = hours / 24.0
    feed_avg_per_day = round(int(feed_count) / days, 1) if days > 0 else 0

    return {
        'temp_avg': float(temp_avg) if temp_avg is not None else None,
        'temp_min': float(temp_min) if temp_min is not None else None,
        'temp_max': float(temp_max) if temp_max is not None else None,
        'hum_avg':  float(hum_avg)  if hum_avg  is not None else None,
        'hum_min':  float(hum_min)  if hum_min  is not None else None,
        'hum_max':  float(hum_max)  if hum_max  is not None else None,
        'fan_on_pct': fan_on_pct,
        'fan_runtime_min': fan_runtime_min,
        'feed_count': int(feed_count),
        'feed_avg_per_day': feed_avg_per_day
    }

# Returns recent feed log rows with joined pet names
def getFeedLog(limit=20):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("""
        SELECT fl.id, p.name, fl.`trigger`, fl.portion_grams, fl.`timestamp`
        FROM feed_log fl
        LEFT JOIN pets p ON fl.pet_id = p.id
        ORDER BY fl.`timestamp` DESC LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ===========Settings and Pet Profile Queries===========
# Returns all key/value settings as dict
def getSettings():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT key_name, value FROM settings")
    rows = cur.fetchall()
    conn.close()
    return dict(rows)

# Updates one setting key with new value
def updateSetting(key, value):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = %s WHERE key_name = %s", (value, key))
    conn.commit()
    conn.close()

# Looks up pet profile by RFID UID
def getPetByRfid(uid):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rfid_uid, camera_label, pot_target, weight_kg, food_per_kg, ideal_weight_kg FROM pets WHERE rfid_uid = %s", (uid,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    keys = ['id','name','rfid_uid','camera_label','pot_target','weight_kg','food_per_kg','ideal_weight_kg']
    return dict(zip(keys, row))

# Looks up pet profile by camera label
def getPetByCameraLabel(label):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rfid_uid, camera_label, pot_target, weight_kg, food_per_kg, ideal_weight_kg FROM pets WHERE camera_label = %s", (label,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    keys = ['id','name','rfid_uid','camera_label','pot_target','weight_kg','food_per_kg','ideal_weight_kg']
    return dict(zip(keys, row))

# Returns all pet profiles
def getAllPets():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rfid_uid, camera_label, pot_target, weight_kg, food_per_kg, ideal_weight_kg FROM pets")
    rows = cur.fetchall()
    conn.close()
    keys = ['id','name','rfid_uid','camera_label','pot_target','weight_kg','food_per_kg','ideal_weight_kg']
    return [dict(zip(keys, r)) for r in rows]

# Inserts a new pet profile
def addPet(name, rfid_uid=None):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO pets (name, rfid_uid) VALUES (%s, %s)", (name, rfid_uid or None))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

# Deletes pet profile by ID
def deletePet(pet_id):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
    conn.commit()
    conn.close()

# Sentinel for "field not provided" in partial pet updates
_NOTSET = object()

# Updates editable pet profile fields
def updatePet(pet_id, name=None, rfid_uid=None, food_per_kg=None, ideal_weight_kg=_NOTSET):
    conn = getConnection()
    cur = conn.cursor()
    if name is not None:
        cur.execute("UPDATE pets SET name=%s WHERE id=%s", (name, pet_id))
    if rfid_uid is not None:
        cur.execute("UPDATE pets SET rfid_uid=%s WHERE id=%s", (rfid_uid or None, pet_id))
    if food_per_kg is not None:
        cur.execute("UPDATE pets SET food_per_kg=%s WHERE id=%s", (food_per_kg, pet_id))
    if ideal_weight_kg is not _NOTSET:
        val = float(ideal_weight_kg) if ideal_weight_kg else None
        cur.execute("UPDATE pets SET ideal_weight_kg=%s WHERE id=%s", (val, pet_id))
    conn.commit()
    conn.close()

# Updates latest known pet weight
def updatePetWeight(pet_id, weight_kg):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("UPDATE pets SET weight_kg=%s WHERE id=%s", (round(float(weight_kg), 2), pet_id))
    conn.commit()
    conn.close()

# Returns RFID event stats for selected window
def getRfidStats(hours=24):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM rfid_events WHERE `timestamp` >= NOW() - INTERVAL %s HOUR",
        (hours,)
    )
    total = cur.fetchone()[0]
    conn.close()
    days = hours / 24.0
    avg_per_day = round(total / days, 1) if days > 0 else 0
    return {'rfid_total': int(total), 'rfid_avg_per_day': avg_per_day}

# Returns number of RFID scans for today
def getRfidToday():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rfid_events WHERE DATE(`timestamp`) = CURDATE()")
    count = cur.fetchone()[0]
    conn.close()
    return int(count)

# ===========Schedule Queries===========
# Returns all schedules (enabled + disabled) for manage page
def getAllSchedules():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, time_of_day, enabled, last_triggered FROM feed_schedules ORDER BY time_of_day ASC")
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'time_of_day': r[1], 'enabled': bool(r[2]), 'last_triggered': str(r[3]) if r[3] else None} for r in rows]

# Stamps a schedule row when it triggers
def touchScheduleLastTriggered(schedule_id):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("UPDATE feed_schedules SET last_triggered = NOW() WHERE id = %s", (schedule_id,))
    conn.commit()
    conn.close()

# Adds new enabled schedule
def addSchedule(time_of_day):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO feed_schedules (time_of_day, enabled) VALUES (%s, 1)", (time_of_day,))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

# Deletes a schedule row
def deleteSchedule(schedule_id):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("DELETE FROM feed_schedules WHERE id = %s", (schedule_id,))
    conn.commit()
    conn.close()

# Returns only enabled schedules used by scheduler thread
def getFeedSchedules():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, time_of_day, enabled FROM feed_schedules WHERE enabled = 1")
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'time_of_day': r[1], 'enabled': r[2]} for r in rows]

# ===========Portion Calculation Helpers===========
# Returns latest N logged weights at feeding time for one pet
def getWeightHistory(pet_id, limit=5):
    """Return the last N weight_kg_at_feed values for a pet (newest first)."""
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT weight_kg_at_feed FROM feed_log
        WHERE pet_id = %s AND weight_kg_at_feed IS NOT NULL AND weight_kg_at_feed > 0
        ORDER BY `timestamp` DESC LIMIT %s
        """,
        (pet_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [float(r[0]) for r in rows]

# Calculates predicted next portion with history + ideal-weight adjustment
def calcIdealPortion(pet_id, cat_weight_sim=512):
    """
    Calculate the ideal portion (grams) for a pet's next feeding.

    Weight resolution (newest first):
      1. Average of last 5 weight_kg_at_feed entries in feed_log (≥3 required)
      2. pets.weight_kg (single last-known value)
      3. ADC fallback: 30 + (cat_weight_sim / 1023) × 50 g

    Portion calculation:
      - If ideal_weight_kg is set:
          base = ideal_weight_kg × food_per_kg
          trend_factor = clamp(ideal_weight_kg / avg_weight, 0.75, 1.25)
          portion = base × trend_factor
        (cat heavier than ideal → factor < 1 → less food; lighter → more food)
      - Else:
          portion = avg_weight × food_per_kg

    Result clamped to [20, 150] grams.
    """
    conn = getConnection()
    cur = conn.cursor()

    cur.execute(
        "SELECT weight_kg, food_per_kg, ideal_weight_kg FROM pets WHERE id = %s",
        (pet_id,)
    )
    pet_row = cur.fetchone()
    weight_kg      = float(pet_row[0]) if pet_row and pet_row[0] is not None else None
    food_per_kg    = float(pet_row[1]) if pet_row and pet_row[1] is not None else 60.0
    ideal_weight_kg = float(pet_row[2]) if pet_row and pet_row[2] is not None else None

    cur.execute(
        """
        SELECT weight_kg_at_feed FROM feed_log
        WHERE pet_id = %s AND weight_kg_at_feed IS NOT NULL AND weight_kg_at_feed > 0
        ORDER BY `timestamp` DESC LIMIT 5
        """,
        (pet_id,)
    )
    history = [float(r[0]) for r in cur.fetchall()]
    conn.close()

    # Resolve effective weight
    if len(history) >= 3:
        avg_weight = sum(history) / len(history)
    elif weight_kg is not None:
        avg_weight = weight_kg
    else:
        portion = 30.0 + (cat_weight_sim / 1023.0) * 50.0
        return round(max(20.0, min(150.0, portion)), 1)

    # Compute portion
    if ideal_weight_kg is not None and avg_weight > 0:
        base_portion  = ideal_weight_kg * food_per_kg
        trend_factor  = ideal_weight_kg / avg_weight
        trend_factor  = max(0.75, min(1.25, trend_factor))
        portion = base_portion * trend_factor
    else:
        portion = avg_weight * food_per_kg

    return round(max(20.0, min(150.0, portion)), 1)

# Returns average dispensed portion over selected window
def getAvgPortion(hours=24):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ROUND(AVG(portion_grams), 1)
        FROM feed_log
        WHERE `timestamp` >= NOW() - INTERVAL %s HOUR
          AND portion_grams IS NOT NULL
        """,
        (hours,)
    )
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else None

# ===========Command Queue===========
# Queues manual command for serial bridge dispatch

def queueCommand(command):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO pending_commands (command) VALUES (%s)", (command,))
    conn.commit()
    conn.close()

# Pops and deletes queued commands in FIFO order
def popPendingCommands():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, command FROM pending_commands ORDER BY id ASC")
    rows = cur.fetchall()
    if rows:
        ids = [r[0] for r in rows]
        cur.execute("DELETE FROM pending_commands WHERE id IN (%s)" % ','.join(['%s'] * len(ids)), ids)
        conn.commit()
    conn.close()
    return [r[1] for r in rows]
