import pymysql
import config

def getConnection():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.Cursor
    )

# --- Inserts ---

def insertSensorReading(data):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sensor_readings (temperature, humidity, ir_state, pot_value, fan_state, servo_state, bowl_weight) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (data.get('TEMP'), data.get('HUM'), data.get('IR'), data.get('POT'), data.get('FAN'), data.get('SERVO'), data.get('BOWL'))
    )
    conn.commit()
    conn.close()

def insertRfidEvent(uid, petId=None):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO rfid_events (uid, pet_id) VALUES (%s, %s)", (uid, petId))
    conn.commit()
    conn.close()

def logFeedEvent(petId, trigger, portion_grams=None, bowl_before=None, bowl_after=None):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feed_log (pet_id, `trigger`, portion_grams, bowl_before, bowl_after) VALUES (%s, %s, %s, %s, %s)",
        (petId, trigger, portion_grams, bowl_before, bowl_after)
    )
    conn.commit()
    conn.close()

# --- Queries ---

def getLatestReading():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sensor_readings ORDER BY `timestamp` DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row

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

def getLatestReadings(limit=10):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sensor_readings ORDER BY id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

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

def getSettings():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT key_name, value FROM settings")
    rows = cur.fetchall()
    conn.close()
    return dict(rows)

def updateSetting(key, value):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = %s WHERE key_name = %s", (value, key))
    conn.commit()
    conn.close()

def getPetByRfid(uid):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rfid_uid, camera_label, pot_target, weight_kg, food_per_kg FROM pets WHERE rfid_uid = %s", (uid,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    keys = ['id','name','rfid_uid','camera_label','pot_target','weight_kg','food_per_kg']
    return dict(zip(keys, row))

def getPetByCameraLabel(label):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rfid_uid, camera_label, pot_target, weight_kg, food_per_kg FROM pets WHERE camera_label = %s", (label,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    keys = ['id','name','rfid_uid','camera_label','pot_target','weight_kg','food_per_kg']
    return dict(zip(keys, row))

def getAllPets():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rfid_uid, camera_label, pot_target, weight_kg, food_per_kg FROM pets")
    rows = cur.fetchall()
    conn.close()
    keys = ['id','name','rfid_uid','camera_label','pot_target','weight_kg','food_per_kg']
    return [dict(zip(keys, r)) for r in rows]

def addPet(name, rfid_uid=None):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO pets (name, rfid_uid) VALUES (%s, %s)", (name, rfid_uid or None))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

def deletePet(pet_id):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
    conn.commit()
    conn.close()

def updatePet(pet_id, name=None, rfid_uid=None, food_per_kg=None):
    conn = getConnection()
    cur = conn.cursor()
    if name is not None:
        cur.execute("UPDATE pets SET name=%s WHERE id=%s", (name, pet_id))
    if rfid_uid is not None:
        cur.execute("UPDATE pets SET rfid_uid=%s WHERE id=%s", (rfid_uid or None, pet_id))
    if food_per_kg is not None:
        cur.execute("UPDATE pets SET food_per_kg=%s WHERE id=%s", (food_per_kg, pet_id))
    conn.commit()
    conn.close()

def updatePetWeight(pet_id, weight_kg):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("UPDATE pets SET weight_kg=%s WHERE id=%s", (round(float(weight_kg), 2), pet_id))
    conn.commit()
    conn.close()

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

def getRfidToday():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rfid_events WHERE DATE(`timestamp`) = CURDATE()")
    count = cur.fetchone()[0]
    conn.close()
    return int(count)

def getAllSchedules():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, time_of_day, enabled, last_triggered FROM feed_schedules ORDER BY time_of_day ASC")
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'time_of_day': r[1], 'enabled': bool(r[2]), 'last_triggered': str(r[3]) if r[3] else None} for r in rows]

def touchScheduleLastTriggered(schedule_id):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("UPDATE feed_schedules SET last_triggered = NOW() WHERE id = %s", (schedule_id,))
    conn.commit()
    conn.close()

def addSchedule(time_of_day):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO feed_schedules (time_of_day, enabled) VALUES (%s, 1)", (time_of_day,))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

def deleteSchedule(schedule_id):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("DELETE FROM feed_schedules WHERE id = %s", (schedule_id,))
    conn.commit()
    conn.close()

def getFeedSchedules():
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("SELECT id, time_of_day, enabled FROM feed_schedules WHERE enabled = 1")
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'time_of_day': r[1], 'enabled': r[2]} for r in rows]

def calcIdealPortion(pet_id, cat_weight_sim=512):
    """
    Calculate ideal portion (grams) for a pet.

    Priority:
    1. Pet profile: if weight_kg and food_per_kg are set → portion = weight_kg * food_per_kg
    2. Historical: if ≥3 valid feed_log records → rolling average of last 5
    3. Fallback: formula from potentiometer ADC (30 + scaled 0–50g)
    Result clamped to [20, 150] grams.
    """
    conn = getConnection()
    cur = conn.cursor()

    # 1. Pet profile formula
    cur.execute("SELECT weight_kg, food_per_kg FROM pets WHERE id = %s", (pet_id,))
    pet_row = cur.fetchone()
    if pet_row and pet_row[0] is not None and pet_row[1] is not None:
        portion = float(pet_row[0]) * float(pet_row[1])
        conn.close()
        return round(max(20.0, min(150.0, portion)), 1)

    # 2. Historical average
    cur.execute(
        """
        SELECT portion_grams FROM feed_log
        WHERE pet_id = %s AND portion_grams IS NOT NULL
        ORDER BY `timestamp` DESC LIMIT 5
        """,
        (pet_id,)
    )
    rows = cur.fetchall()
    conn.close()

    valid = [r[0] for r in rows if r[0] is not None and r[0] > 0]
    if len(valid) >= 3:
        portion = sum(valid) / len(valid)
    else:
        # 3. ADC fallback
        portion = 30.0 + (cat_weight_sim / 1023.0) * 50.0

    return round(max(20.0, min(150.0, portion)), 1)

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

# --- Command queue ---

def queueCommand(command):
    conn = getConnection()
    cur = conn.cursor()
    cur.execute("INSERT INTO pending_commands (command) VALUES (%s)", (command,))
    conn.commit()
    conn.close()

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
