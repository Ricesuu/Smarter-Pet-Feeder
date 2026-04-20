from flask import Flask, render_template, request, jsonify
from database.db import (
    getLatestReading, getLatestReadings, getHistoryByHours, getAnalyticsExtended,
    getTotalReadings, getFeedLog, getSettings, updateSetting,
    queueCommand, logFeedEvent, getRfidStats, getAvgPortion,
    getAllSchedules, addSchedule, deleteSchedule, getRfidToday,
    getAllPets, addPet, deletePet, updatePet
)
import config

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/manage')
def manage():
    s = getSettings()
    return render_template('manage.html', settings=s)

@app.route('/api/latest')
def apiLatest():
    row = getLatestReading()
    if not row:
        return jsonify({})
    keys = ['id','temperature','humidity','ir_state','pot_value','fan_state','servo_state','timestamp','bowl_weight']
    d = dict(zip(keys, row))
    d['timestamp'] = str(d['timestamp'])
    pot = d.get('pot_value') or 0
    d['cat_weight_kg'] = round(pot / 1023.0 * 10, 1)
    d['rfid_today'] = getRfidToday()
    return jsonify(d)

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

@app.route('/api/settings', methods=['POST'])
def apiUpdateSettings():
    data = request.json
    for key, value in data.items():
        updateSetting(key, value)
    return jsonify({'status': 'updated'})

@app.route('/api/schedules', methods=['GET'])
def apiGetSchedules():
    return jsonify(getAllSchedules())

@app.route('/api/schedules', methods=['POST'])
def apiAddSchedule():
    time_of_day = request.json.get('time_of_day', '')
    if not time_of_day or len(time_of_day) != 5:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400
    new_id = addSchedule(time_of_day)
    return jsonify({'status': 'added', 'id': new_id, 'time_of_day': time_of_day})

@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def apiDeleteSchedule(schedule_id):
    deleteSchedule(schedule_id)
    return jsonify({'status': 'deleted'})

@app.route('/api/pets', methods=['GET'])
def apiGetPets():
    pets = getAllPets()
    from database.db import calcIdealPortion
    for p in pets:
        if p.get('weight_kg') is not None and p.get('food_per_kg') is not None:
            p['calc_portion'] = round(p['weight_kg'] * p['food_per_kg'], 1)
        else:
            p['calc_portion'] = None
    return jsonify(pets)

@app.route('/api/pets', methods=['POST'])
def apiAddPet():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    rfid_uid = data.get('rfid_uid', '').strip() or None
    new_id = addPet(name, rfid_uid)
    return jsonify({'status': 'added', 'id': new_id})

@app.route('/api/pets/<int:pet_id>', methods=['PUT'])
def apiUpdatePet(pet_id):
    data = request.json or {}
    updatePet(
        pet_id,
        name=data.get('name'),
        rfid_uid=data.get('rfid_uid'),
        food_per_kg=data.get('food_per_kg')
    )
    return jsonify({'status': 'updated'})

@app.route('/api/pets/<int:pet_id>', methods=['DELETE'])
def apiDeletePet(pet_id):
    deletePet(pet_id)
    return jsonify({'status': 'deleted'})

if __name__ == '__main__':
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)

