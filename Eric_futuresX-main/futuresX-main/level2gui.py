from PyQt5 import QtWidgets, QtCore
import sys
import random

class OrderBookWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Order Book - ES Futures")
        self.resize(500, 400)

        self.layout = QtWidgets.QVBoxLayout()
        self.table = QtWidgets.QTableWidget(10, 2)
        self.table.setHorizontalHeaderLabels(["Bid", "Ask"])
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)

        # Simulate updating the table every 0.5 seconds
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_order_book)
        self.timer.start(500)

    def update_order_book(self):
        self.table.clearContents()
        bid_prices = sorted([random.uniform(5200, 5250) for _ in range(10)], reverse=True)
        ask_prices = sorted([random.uniform(5251, 5300) for _ in range(10)])

        for i in range(10):
            bid_item = QtWidgets.QTableWidgetItem(f"{random.randint(1,10)}@{bid_prices[i]:.2f}")
            ask_item = QtWidgets.QTableWidgetItem(f"{random.randint(1,10)}@{ask_prices[i]:.2f}")
            self.table.setItem(i, 0, bid_item)
            self.table.setItem(i, 1, ask_item)

app = QtWidgets.QApplication(sys.argv)
window = OrderBookWindow()
window.show()
sys.exit(app.exec_())
