"""
app.py - Flask dashboard routes

Provides:
  - Page routes (dashboard, analytics, manage)
  - REST APIs for live sensor data, analytics, schedules, and pets
  - Manual command queueing endpoint for Arduino actions
"""

# ==========Import Statements==========
from flask import Flask, render_template, request, jsonify
from database.db import (
    getLatestReading, getLatestReadings, getHistoryByHours, getAnalyticsExtended,
    getTotalReadings, getFeedLog, getSettings, updateSetting,
    queueCommand, logFeedEvent, getRfidStats, getAvgPortion,
    getAllSchedules, addSchedule, deleteSchedule, getRfidToday,
    getAllPets, addPet, deletePet, updatePet
)
import config

# ===========Flask App State===========
app = Flask(__name__)

# ===========Page Routes===========
# Renders the main dashboard page
@app.route('/')
def index():
    return render_template('index.html')

# Renders analytics page
@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

# Renders manage page with automation settings
@app.route('/manage')
def manage():
    s = getSettings()
    return render_template('manage.html', settings=s)

# ===========Live Sensor APIs===========
# Returns latest sensor row plus derived cat_weight_kg and RFID count for today
@app.route('/api/latest')
def apiLatest():
    row = getLatestReading()
    if not row:
        return jsonify({})
    keys = ['id','temperature','humidity','ir_state','pot_value','fan_state','servo_state','timestamp','bowl_weight']
    d = dict(zip(keys, row))
    d['timestamp'] = str(d['timestamp'])
    pot = d.get('pot_value') or 0
    d['cat_weight_kg'] = round(pot / 100.0, 1)
    d['rfid_today'] = getRfidToday()
    return jsonify(d)

# Returns most recent N readings
@app.route('/api/latest-readings')
def apiLatestReadings():
    limit = request.args.get('limit', 10, type=int)
    rows = getLatestReadings(limit)
    keys = ['id','temperature','humidity','ir_state','pot_value','fan_state','servo_state','timestamp','bowl_weight']
    result = []
    for row in rows:
        d = dict(zip(keys, row))
        d['timestamp'] = str(d['timestamp'])
        result.append(d)
    return jsonify(result)

# Returns time-range history for charting
@app.route('/api/history')
def apiHistory():
    hours = request.args.get('hours', 24, type=int)
    rows = getHistoryByHours(hours)
    keys = ['id','temperature','humidity','ir_state','pot_value','fan_state','servo_state','timestamp','bowl_weight']
    result = []
    for row in rows:
        d = dict(zip(keys, row))
        d['timestamp'] = str(d['timestamp'])
        result.append(d)
    return jsonify(result)

# ===========Analytics APIs===========
# Returns aggregate stats for selected lookback window
@app.route('/api/analytics')
def apiAnalytics():
    hours = request.args.get('hours', 24, type=int)
    data = getAnalyticsExtended(hours)
    data['total_readings'] = getTotalReadings(hours)
    rfid = getRfidStats(hours)
    data['rfid_total'] = rfid['rfid_total']
    data['rfid_avg_per_day'] = rfid['rfid_avg_per_day']
    data['avg_portion'] = getAvgPortion(hours)
    return jsonify(data)

# Returns recent feed log entries with pet names
@app.route('/api/feedlog')
def apiFeedLog():
    limit = request.args.get('limit', 20, type=int)
    rows = getFeedLog(limit)
    result = []
    for row in rows:
        result.append({
            'id':            row[0],
            'pet':           row[1] or 'Unknown',
            'trigger':       row[2],
            'portion_grams': row[3],
            'timestamp':     str(row[4])
        })
    return jsonify(result)

# ===========Manual Control APIs===========
# Queues manual commands to be dispatched by serial bridge
@app.route('/api/command', methods=['POST'])
def apiCommand():
    cmd = request.json.get('command', '')
    allowed = ['FEED','FAN_ON','FAN_OFF','SERVO_OPEN','SERVO_CLOSE','STATUS']
    if cmd not in allowed:
        return jsonify({'error': 'Invalid command'}), 400
    queueCommand(cmd)
    if cmd == 'FEED':
        logFeedEvent(None, 'manual')
    return jsonify({'status': 'queued', 'command': cmd})

# Updates key/value automation settings
@app.route('/api/settings', methods=['POST'])
def apiUpdateSettings():
    data = request.json
    for key, value in data.items():
        updateSetting(key, value)
    return jsonify({'status': 'updated'})

# ===========Schedule APIs===========
# Returns all configured schedules
@app.route('/api/schedules', methods=['GET'])
def apiGetSchedules():
    return jsonify(getAllSchedules())

# Adds a schedule entry in HH:MM format
@app.route('/api/schedules', methods=['POST'])
def apiAddSchedule():
    time_of_day = request.json.get('time_of_day', '')
    if not time_of_day or len(time_of_day) != 5:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400
    new_id = addSchedule(time_of_day)
    return jsonify({'status': 'added', 'id': new_id, 'time_of_day': time_of_day})

# Deletes one schedule entry
@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def apiDeleteSchedule(schedule_id):
    deleteSchedule(schedule_id)
    return jsonify({'status': 'deleted'})

# ===========Pet Profile APIs===========
# Returns pet profiles plus derived avg weight, trend, and predicted portion
@app.route('/api/pets', methods=['GET'])
def apiGetPets():
    from database.db import calcIdealPortion, getWeightHistory
    pets = getAllPets()
    for p in pets:
        history = getWeightHistory(p['id'], limit=5)

        # Average weight: prefer ≥3 history readings, else fall back to last known
        if len(history) >= 3:
            avg_weight = round(sum(history) / len(history), 2)
        elif p.get('weight_kg') is not None:
            avg_weight = round(float(p['weight_kg']), 2)
        else:
            avg_weight = None
        p['avg_weight'] = avg_weight

        # Weight trend arrow based on newest vs oldest half of history
        if len(history) >= 3:
            recent = history[:2]
            older  = history[-2:]
            diff = (sum(recent) / len(recent)) - (sum(older) / len(older))
            p['weight_trend'] = '↑' if diff > 0.2 else ('↓' if diff < -0.2 else '→')
        else:
            p['weight_trend'] = '—'

        # Predicted portion using new calcIdealPortion logic
        p['predicted_portion'] = calcIdealPortion(p['id'])

        # Legacy simple calc (last weight × food/kg) still included for reference
        if p.get('weight_kg') is not None and p.get('food_per_kg') is not None:
            p['calc_portion'] = round(float(p['weight_kg']) * float(p['food_per_kg']), 1)
        else:
            p['calc_portion'] = None

    return jsonify(pets)

# Adds a new pet profile
@app.route('/api/pets', methods=['POST'])
def apiAddPet():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    rfid_uid = data.get('rfid_uid', '').strip() or None
    new_id = addPet(name, rfid_uid)
    return jsonify({'status': 'added', 'id': new_id})

# Updates editable fields for a pet profile
@app.route('/api/pets/<int:pet_id>', methods=['PUT'])
def apiUpdatePet(pet_id):
    data = request.json or {}
    kwargs = dict(
        name=data.get('name'),
        rfid_uid=data.get('rfid_uid'),
        food_per_kg=data.get('food_per_kg')
    )
    # Only pass ideal_weight_kg if the key is present in the request (allows clearing with 0)
    if 'ideal_weight_kg' in data:
        raw = data['ideal_weight_kg']
        kwargs['ideal_weight_kg'] = float(raw) if raw not in (None, '', 0, '0') else 0
    updatePet(pet_id, **kwargs)
    return jsonify({'status': 'updated'})

# Deletes a pet profile
@app.route('/api/pets/<int:pet_id>', methods=['DELETE'])
def apiDeletePet(pet_id):
    deletePet(pet_id)
    return jsonify({'status': 'deleted'})

# ===========Entry Point===========
if __name__ == '__main__':
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)

