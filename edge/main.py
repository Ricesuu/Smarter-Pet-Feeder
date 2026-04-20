import threading
from serialComm.serialBridge import run as runSerialBridge
from automation.scheduler import startScheduler
from dashboard.app import app
import config

if __name__ == '__main__':
    serialThread = threading.Thread(target=runSerialBridge, daemon=True)
    serialThread.start()
    startScheduler()
    print(f"[Main] Dashboard at http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
