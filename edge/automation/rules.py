from database.db import getSettings

_lastFanState = None

def evaluateRules(data, sendCommand):
    global _lastFanState
    settings = getSettings()
    humThreshold = float(settings.get('humidity_threshold', 70))

    shouldFanBeOn = data.get('HUM', 0) > humThreshold

    if shouldFanBeOn != _lastFanState:
        _lastFanState = shouldFanBeOn
        sendCommand('FAN_ON' if shouldFanBeOn else 'FAN_OFF')
