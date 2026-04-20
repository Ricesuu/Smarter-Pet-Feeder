import time
import threading
from datetime import datetime
from automation.feedingSession import startSession, getSession
from serialComm.serialBridge import sendCommand
from database.db import getFeedSchedules, touchScheduleLastTriggered
import config

_triggeredToday = set()

def scheduledFeedChecker():
    while True:
        now = datetime.now()
        currentTime = now.strftime('%H:%M')
        todayKey = now.strftime('%Y-%m-%d')

        schedules = getFeedSchedules()
        for s in schedules:
            key = f"{todayKey}_{s['time_of_day']}"
            if s['time_of_day'] == currentTime and key not in _triggeredToday:
                _triggeredToday.add(key)
                touchScheduleLastTriggered(s['id'])
                print(f"[Scheduler] Triggering feeding session at {currentTime}")
                startSession(sendCommand)

        time.sleep(15)

def sessionTimeoutWatcher():
    while True:
        time.sleep(30)
        session = getSession()
        if session:
            session.checkTimeout()

def startScheduler():
    t1 = threading.Thread(target=scheduledFeedChecker, daemon=True)
    t2 = threading.Thread(target=sessionTimeoutWatcher, daemon=True)
    t1.start()
    t2.start()
