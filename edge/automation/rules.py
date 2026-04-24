from database.db import getSettings

# ===========Rule State===========
_lastFanState = None

# ===========Automation Rules===========
# Evaluates live sensor data and controls fan based on humidity threshold
def evaluateRules(data, sendCommand):
    global _lastFanState

    settings = getSettings()
    humThreshold = float(settings.get('humidity_threshold', 70))

    shouldFanBeOn = data.get('HUM', 0) > humThreshold

    if shouldFanBeOn != _lastFanState:
        _lastFanState = shouldFanBeOn

        if shouldFanBeOn:
            sendCommand('FAN_ON')
        else:
            sendCommand('FAN_OFF')