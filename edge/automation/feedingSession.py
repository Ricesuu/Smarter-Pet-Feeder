# ==========Import Statements==========
import time
import threading

from database.db import logFeedEvent, getLatestReading, updatePetWeight
from automation.historicalRules import calcIdealPortion
import config


# ===========Session States===========

IDLE = 'IDLE'
WAITING_FOR_IR = 'WAITING_FOR_IR'
WAITING_FOR_PET = 'WAITING_FOR_PET'
DISPENSING = 'DISPENSING'
DONE = 'DONE'
TIMEOUT = 'TIMEOUT'


# ===========Global Session Data===========

_activeSession = None
_lock = threading.Lock()
_latestCatWeight = 512


# ===========Shared Functions===========
# Updates latest potentiometer value used as simulated pet weight
def updateCatWeight(val):
    global _latestCatWeight
    _latestCatWeight = val


# ===========Feeding Session Class===========

class FeedingSession:

    def __init__(self, sendCommand):
        # Initializes feeding session data
        self.state = IDLE
        self.sendCommand = sendCommand

        self.pet = None
        self.startTime = None
        self.windowSeconds = config.FEED_WINDOW_SECONDS

        self.bowlBefore = None
        self.portionTarget = None
        self._fedPets = set()

    # ------------------Start Session------------------
    # Starts feeding window and waits for IR detection
    def start(self):
        self.state = WAITING_FOR_IR
        self.startTime = time.time()

        print("[FeedingSession] Started. Waiting for IR detection...")

    # ------------------IR Detection Trigger------------------
    # Moves session into pet identification stage after IR trigger
    def onIrDetected(self):
        with _lock:

            if self.state != WAITING_FOR_IR:
                return

            if self._isExpired():
                self._timeout()
                return

            self.state = WAITING_FOR_PET

            print("[FeedingSession] IR detected. Waiting for RFID pet identification...")

    # ------------------Pet Identified Trigger------------------
    # Starts dispensing after valid pet is identified
    def onPetIdentified(self, pet, trigger):
        with _lock:

            if self.state != WAITING_FOR_PET:
                return

            if self._isExpired():
                self._timeout()
                return

            if pet['id'] in self._fedPets:
                print(f"[FeedingSession] {pet['name']} already fed this session.")
                self.state = WAITING_FOR_IR
                return

            self.pet = pet
            self._fedPets.add(pet['id'])
            self.state = DISPENSING

            weight_kg = round(_latestCatWeight / 100.0, 2)
            updatePetWeight(pet['id'], weight_kg)

            latest = getLatestReading()
            self.bowlBefore = float(latest[8]) if latest and latest[8] is not None else 0.0

            self.portionTarget = calcIdealPortion(pet['id'], _latestCatWeight)

            print(
                f"[FeedingSession] Pet: {pet['name']} via {trigger}. "
                f"Bowl before: {self.bowlBefore}g. "
                f"Target portion: {self.portionTarget}g."
            )

            self.sendCommand(f"FEED,{self.portionTarget}")
            logFeedEvent(pet['id'], trigger, weight_kg_at_feed=weight_kg)

    # ------------------Feed Completed Trigger------------------
    # Finalizes feed results and resets for next pet
    def onFeedDone(self):
        with _lock:

            if self.state != DISPENSING:
                return

            self.state = DONE

            latest = getLatestReading()
            bowlAfter = float(latest[8]) if latest and latest[8] is not None else None

            if bowlAfter is not None:
                portionActual = round(bowlAfter - self.bowlBefore, 1)
            else:
                portionActual = self.portionTarget

            petName = self.pet['name'] if self.pet else 'Unknown'

            print(
                f"[FeedingSession] Done for {petName}. "
                f"Dispensed: {portionActual}g."
            )

            if self.pet:
                _updateLastFeedLog(
                    self.pet['id'],
                    portionActual,
                    self.bowlBefore,
                    bowlAfter
                )

            if not self._isExpired():
                self.state = WAITING_FOR_IR
                self.pet = None
                self.bowlBefore = None
                self.portionTarget = None

                print("[FeedingSession] Ready for next pet within window.")

            else:
                clearSession()

    # ------------------Timeout Check------------------
    # Checks whether feeding window has expired
    def checkTimeout(self):
        with _lock:

            if self.state in (DONE, TIMEOUT, IDLE):
                return

            if self._isExpired():
                self._timeout()

    # ------------------Helper Functions------------------
    # Returns True if feeding window expired
    def _isExpired(self):
        return time.time() - self.startTime > self.windowSeconds
    # Ends expired feeding session
    def _timeout(self):
        self.state = TIMEOUT

        print("[FeedingSession] Timed out. Skipping meal.")

        clearSession()
    # Returns True if session still active
    def isActive(self):
        return self.state in (
            WAITING_FOR_IR,
            WAITING_FOR_PET,
            DISPENSING
        )


# ===========Database Helper Functions===========
# Updates latest feed log with actual dispensed portion
def _updateLastFeedLog(pet_id, portion_grams, bowl_before, bowl_after):

    from database.db import getConnection

    conn = getConnection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE feed_log
        SET portion_grams=%s,
            bowl_before=%s,
            bowl_after=%s
        WHERE pet_id=%s
          AND portion_grams IS NULL
        ORDER BY `timestamp` DESC
        LIMIT 1
        """,
        (
            portion_grams,
            bowl_before,
            bowl_after,
            pet_id
        )
    )

    conn.commit()
    conn.close()


# ===========Public Session Functions===========
# Starts new feeding session if none active
def startSession(sendCommand):
    global _activeSession

    with _lock:

        if _activeSession and _activeSession.isActive():
            print("[FeedingSession] Session already active.")
            return _activeSession

        _activeSession = FeedingSession(sendCommand)

    _activeSession.start()

    return _activeSession

# Returns current active session
def getSession():
    return _activeSession

# Clears active feeding session
def clearSession():
    global _activeSession
    _activeSession = None