from PyQt6.QtWidgets import QApplication
import sys
from gui import OrderBookWindow
from data_collecter import DataCollector

# RUN THIS FILE

app = QApplication(sys.argv)



# Start L2 Data Collector
collector = DataCollector(symbol="ES")
collector.start()

# Start GUI
window = OrderBookWindow(collector=collector)
window.show()

# Exit process
def on_exit():
    print("[MAIN] Exiting...")
    collector.stop()
    collector.wait()

app.aboutToQuit.connect(on_exit)

sys.exit(app.exec())
