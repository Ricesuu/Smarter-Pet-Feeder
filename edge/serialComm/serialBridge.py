import serial
import time
from database.db import insertSensorReading, insertRfidEvent, getPetByRfid, popPendingCommands
from automation.rules import evaluateRules
from automation.feedingSession import getSession, updateCatWeight
import config

ser = None

# --- Message parser ---

def parseMessage(raw):
    if not raw:
        return None
    parts = raw.split(',')
    msgType = parts[0]

    if msgType == 'DATA':
        payload = {}
        for item in parts[1:]:
            if '=' in item:
                key, val = item.split('=')
                payload[key] = _parseValue(val)
        return {'type': 'DATA', 'payload': payload}
    elif msgType == 'RFID':
        return {'type': 'RFID', 'payload': parts[1] if len(parts) > 1 else ''}
    elif msgType == 'STATUS':
        payload = {}
        for item in parts[1:]:
            if '=' in item:
                key, val = item.split('=')
                payload[key] = int(val)
        return {'type': 'STATUS', 'payload': payload}
    elif msgType == 'FEED_DONE':
        return {'type': 'FEED_DONE', 'payload': {}}
    return None

def _parseValue(val):
    try:
        return float(val) if '.' in val else int(val)
    except ValueError:
        return val

# --- Serial bridge ---

def connect():
    global ser
    ser = serial.Serial(config.SERIAL_PORT, config.SERIAL_BAUD, timeout=1)
    time.sleep(2)

def run():
    connect()
    print(f"[SerialBridge] Running on {config.SERIAL_PORT} at {config.SERIAL_BAUD} baud")
    while True:
        try:
            for cmd in popPendingCommands():
                sendCommand(cmd)
                print(f"[Queue] Dispatched: {cmd}")
            line = ser.readline().decode('utf-8').strip()
            if not line:
                continue
            print(f"[Arduino] {line}")
            handleMessage(line)
        except Exception as e:
            print(f"[SerialBridge] Error: {e}")
            time.sleep(1)

def handleMessage(raw):
    msg = parseMessage(raw)
    if not msg:
        return

    if msg['type'] == 'DATA':
        insertSensorReading(msg['payload'])
        evaluateRules(msg['payload'], sendCommand)
        # Keep session informed of latest cat weight simulation (POT)
        updateCatWeight(msg['payload'].get('POT', 512))
        session = getSession()
        if session and msg['payload'].get('IR') == 1:
            session.onIrDetected()
        print(f"[DB] Saved — T={msg['payload'].get('TEMP')} H={msg['payload'].get('HUM')} "
              f"IR={msg['payload'].get('IR')} BOWL={msg['payload'].get('BOWL')}")

    elif msg['type'] == 'RFID':
        uid = msg['payload']
        pet = getPetByRfid(uid)
        insertRfidEvent(uid, pet['id'] if pet else None)
        print(f"[RFID] UID={uid} Pet={'unknown' if not pet else pet['name']}")
        session = getSession()
        if session and pet:
            session.onPetIdentified(pet, 'RFID')
        elif not session:
            print(f"[SerialBridge] RFID scan outside active session")

    elif msg['type'] == 'FEED_DONE':
        print("[SerialBridge] Feed done received")
        session = getSession()
        if session:
            session.onFeedDone()

def sendCommand(cmd):
    if ser and ser.is_open:
        ser.write((cmd + '\n').encode('utf-8'))
        print(f"[SerialBridge] Sent: {cmd}")

