import time
import threading
from database.db import logFeedEvent, getLatestReading, updatePetWeight
from automation.historicalRules import calcIdealPortion
import config

IDLE = 'IDLE'
WAITING_FOR_IR = 'WAITING_FOR_IR'
WAITING_FOR_PET = 'WAITING_FOR_PET'
DISPENSING = 'DISPENSING'
DONE = 'DONE'
TIMEOUT = 'TIMEOUT'

_activeSession = None
_lock = threading.Lock()

# Latest cat_weight_sim (POT reading) shared from serialBridge
_latestCatWeight = 512

def updateCatWeight(val):
    global _latestCatWeight
    _latestCatWeight = val

class FeedingSession:
    def __init__(self, sendCommand):
        self.state = IDLE
        self.sendCommand = sendCommand
        self.pet = None
        self.startTime = None
        self.windowSeconds = config.FEED_WINDOW_SECONDS
        self.bowlBefore = None
        self.portionTarget = None
        self._fedPets = set()  # track pet IDs already served this session

    def start(self):
        self.state = WAITING_FOR_IR
        self.startTime = time.time()
        print(f"[FeedingSession] Started. Waiting for IR detection...")

    def onIrDetected(self):
        with _lock:
            if self.state != WAITING_FOR_IR:
                return
            if self._isExpired():
                self._timeout()
                return
            self.state = WAITING_FOR_PET
            print("[FeedingSession] IR detected. Waiting for RFID or camera ID...")

    def onPetIdentified(self, pet, trigger):
        with _lock:
            if self.state != WAITING_FOR_PET:
                return
            if self._isExpired():
                self._timeout()
                return
            if pet['id'] in self._fedPets:
                print(f"[FeedingSession] {pet['name']} already fed this session — skipping.")
                # Reset to wait for a different pet
                self.state = WAITING_FOR_IR
                return
            self.pet = pet
            self._fedPets.add(pet['id'])
            self.state = DISPENSING

            # Update pet weight from current potentiometer reading (simulated scale)
            weight_kg = round(_latestCatWeight / 1023.0 * 10, 2)
            updatePetWeight(pet['id'], weight_kg)

            # Snapshot bowl weight before dispensing
            latest = getLatestReading()
            # bowl_weight is index 8 in sensor_readings row (id=0 ... timestamp=7, bowl_weight=8)
            self.bowlBefore = float(latest[8]) if latest and latest[8] is not None else 0.0

            # Historical rule: calculate ideal portion for this pet
            self.portionTarget = calcIdealPortion(pet['id'], _latestCatWeight)
            print(f"[FeedingSession] Pet: {pet['name']} via {trigger}. "
                  f"Bowl before: {self.bowlBefore}g. Target portion: {self.portionTarget}g.")

            self.sendCommand(f"FEED,{self.portionTarget}")
            logFeedEvent(pet['id'], trigger)

    def onFeedDone(self):
        with _lock:
            if self.state != DISPENSING:
                return
            self.state = DONE

            # Record actual portion dispensed
            latest = getLatestReading()
            bowlAfter = float(latest[8]) if latest and latest[8] is not None else None
            portionActual = round(bowlAfter - self.bowlBefore, 1) if bowlAfter is not None else self.portionTarget

            petName = self.pet['name'] if self.pet else 'Unknown'
            print(f"[FeedingSession] Done for {petName}. "
                  f"Dispensed: {portionActual}g (bowl {self.bowlBefore}g → {bowlAfter}g).")

            # Update the most recent feed_log entry with actual measurements
            if self.pet:
                _updateLastFeedLog(self.pet['id'], portionActual, self.bowlBefore, bowlAfter)

            # Reset so another pet can eat within the same feed window
            if not self._isExpired():
                self.state = WAITING_FOR_IR
                self.pet = None
                self.bowlBefore = None
                self.portionTarget = None
                print("[FeedingSession] Ready for next pet within window.")
            else:
                clearSession()

    def checkTimeout(self):
        with _lock:
            if self.state in (DONE, TIMEOUT, IDLE):
                return
            if self._isExpired():
                self._timeout()

    def _isExpired(self):
        return time.time() - self.startTime > self.windowSeconds

    def _timeout(self):
        self.state = TIMEOUT
        print("[FeedingSession] Timed out. Skipping meal.")
        clearSession()

    def isActive(self):
        return self.state in (WAITING_FOR_IR, WAITING_FOR_PET, DISPENSING)


def _updateLastFeedLog(pet_id, portion_grams, bowl_before, bowl_after):
    """Update the most recent feed_log row for this pet with actual measurements."""
    from database.db import getConnection
    conn = getConnection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE feed_log SET portion_grams=%s, bowl_before=%s, bowl_after=%s
        WHERE pet_id=%s AND portion_grams IS NULL
        ORDER BY `timestamp` DESC LIMIT 1
        """,
        (portion_grams, bowl_before, bowl_after, pet_id)
    )
    conn.commit()
    conn.close()


def startSession(sendCommand):
    global _activeSession
    with _lock:
        if _activeSession and _activeSession.isActive():
            print("[FeedingSession] Session already active.")
            return _activeSession
        _activeSession = FeedingSession(sendCommand)
    _activeSession.start()
    return _activeSession

def getSession():
    return _activeSession

def clearSession():
    global _activeSession
    _activeSession = None
