from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QProgressBar, QHeaderView, QSizePolicy,
    QLineEdit, QPushButton, QComboBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
import sys
import random
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import numpy as np
# from level2IBKR import get_market_depth, app as ibkr_app

from ibkrdata import data_manager
from data_collecter import DataCollector

from PyQt6.QtWidgets import QProgressBar


class OrderBookWindow(QMainWindow):
    def __init__(self, collector=None):
        super().__init__()
        self.setWindowTitle("Level 2 Order Book Window")
        self.setGeometry(100, 100, 1200, 900)

        # -------------- LAYOUTS --------------
        main_layout = QHBoxLayout()
        table_layout = QVBoxLayout()

        # -------------- DOM TABLE --------------
        self.label = QLabel("Level 2 Order Book")
        self.label.setFixedHeight(25)
        table_layout.addWidget(self.label)


        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Price", "COB"])
        self.table.setColumnWidth(0, 100)  # Price column
        self.table.setColumnWidth(1, 100) # COB column
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setRowCount(30)
        self.table.setMaximumWidth(200)

        # Add rows to the table
        for i in range(30):
            self.table.setRowHeight(i, 25)
        table_layout.addWidget(self.table)
        # self.table.horizontalHeader().setStretchLastSection(False)
        


        # -------------- BOOKMAP HEATMAP --------------
        self.heatmap_rows = 30     # price levels
        self.heatmap_cols = 1200    # time steps
        self.heatmap = np.zeros((self.heatmap_rows, self.heatmap_cols))
        self.image_view = pg.ImageView()
        self.image_view.ui.histogram.hide()
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        self.image_view.getView().invertY(False)
        hot_cmap = pg.colormap.getFromMatplotlib("hot").getLookupTable(0.0, 1.0)[::-1]  # reversed
        self.image_view.setColorMap(pg.ColorMap(pos=np.linspace(0.0, 1.0, 256), color=hot_cmap))
        self.image_view.getView().setAspectLocked(False)
        self.image_view.setStyleSheet("background-color:rgb(126, 59, 59); border: none;")
        
        self.image_view.setContentsMargins(0, 0, 0, 0)
        self.image_view.setFixedHeight(750)
        
        vb = self.image_view.getView()
        vb.setMouseEnabled(x=False, y=False)
        vb.setAspectLocked(False)
        
        # Lines for best bid and ask
        self.best_bid_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('g', width=2))
        self.best_ask_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', width=2))
        self.image_view.getView().addItem(self.best_bid_line)
        self.image_view.getView().addItem(self.best_ask_line)

        # Title
        image_layout = QVBoxLayout()
        self.image_label = QLabel("ES Futures (5000.00)")
        self.image_label.setStyleSheet("color: white;")
        self.image_label.setFixedHeight(50)
        self.image_label.setFont(QFont("Inter", 13, QFont.Weight.Bold))

        # initialize bookmap layout
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(self.image_view)
        image_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        image_container = QWidget()
        image_container.setLayout(image_layout)

        # -------------- ORDER ENTRY SECTION --------------
        order_box = QGroupBox("Order Entry")
        order_box.setStyleSheet("QGroupBox { font-weight: bold; }")

        order_layout = QFormLayout()

        # Side (Buy/Sell)
        self.side_combo = QComboBox()
        self.side_combo.addItems(["BUY", "SELL"])

        # Order Type (Market/Limit)
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["Market", "Limit"])
        self.order_type_combo.currentTextChanged.connect(self.on_order_type_changed)

        # Price input
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("e.g. 5000.00")
        self.price_input.setEnabled(True)  # Initially enabled for Limit orders

        # Size input
        self.size_input = QLineEdit()
        self.size_input.setPlaceholderText("e.g. 1")

        # Submit button
        submit_button = QPushButton("Place Order")
        submit_button.clicked.connect(self.place_order)

        # Add widgets to layout
        order_layout.addRow("Side:", self.side_combo)
        order_layout.addRow("Type:", self.order_type_combo)
        order_layout.addRow("Price:", self.price_input)
        order_layout.addRow("Size:", self.size_input)
        order_layout.addRow(submit_button)

        order_box.setLayout(order_layout)

        # -------------- DOM Pressure Label --------------
        self.pressure_label = QLabel("DOM Pressure: 0")
        self.pressure_label.setFixedHeight(25)
        self.pressure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        order_layout.addRow(self.pressure_label)

        # -------------- DATA BEING WRITTEN TO CSV --------------
        self.collector = collector 
        if self.collector:
            self.collector.data_collected.connect(self.update_data_display)
        self.data_label = QLabel("Waiting for L2 data...")
        self.data_label.setStyleSheet("color: white; font-size: 12px;")
        self.data_label.setFixedHeight(25)
        order_layout.addRow("Status:", self.data_label)



        # -------------- COMBINE LAYOUTS --------------
        table_container = QWidget()
        table_container.setLayout(table_layout)
        main_layout.addWidget(image_container, 4)
        main_layout.addWidget(table_container, 0)
        main_layout.addWidget(order_box, 0)
 

        # Initialize main window
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_table)
        self.timer.start(100)  # update every 0.1 second

    def update_data_display(self, data):
        """
        Update the GUI label to confirm data collection is running.
        """
        if data == "write":
            self.data_label.setText("Saving data... ✅")
        elif data == "wait":
            self.data_label.setText("Waiting for RTH/data... ❌")


    def on_order_type_changed(self, order_type):
        """Enable/disable price input based on order type"""
        self.price_input.setEnabled(order_type == "Limit")
        if order_type == "Market":
            self.price_input.clear()

    def place_order(self):
        side = self.side_combo.currentText()
        order_type = self.order_type_combo.currentText()
        
        try:
            size = int(self.size_input.text())
            price = float(self.price_input.text()) if order_type == "Limit" else None
        except ValueError:
            print("[ERROR] Invalid price or size.")
            return

        if order_type == "Limit" and not price:
            print("[ERROR] Price required for Limit orders.")
            return

        print(f"[ORDER ENTRY] [gui.py] [place_order] Placing {order_type} {side} order for {size}" + 
              (f" @ {price:.2f}" if price else ""))


        # -------------- PLACE ORDER --------------
        if order_type == "Market":
            data_manager.market_order("ES", size, side)
        elif order_type == "Limit":
            data_manager.limit_order("ES", size, price, side)
        elif order_type == "Bracket":
            data_manager.buy_bracket_order_market("ES", size, price, price)

        self.price_input.clear()
        self.size_input.clear()

    # Update orderbook using IBKR data
    def update_table(self):
        total_rows = 30
        # self.table.setRowCount(total_rows)
        # for i in range(total_rows):
        #     self.table.setRowHeight(i, 25)

        # Get live market data
        # bids, asks = data_manager.get_market_depth()
        # bids = [b for b in bids if b is not None]
        # asks = [a for a in asks if a is not None]

        bids, asks = data_manager.get_market_depth()
        # if not bids or not asks:
        #     return

        best_bid = max(bids, key=lambda x: x[0])[0]
        best_ask = min(asks, key=lambda x: x[0])[0]
        mid_price = round((best_bid + best_ask) / 2 / 0.25) * 0.25

        self.image_label.setText(f"ES Futures ({best_ask:.2f})")

        # Calculate price range for the heatmap
        price_range = self.heatmap_rows * 0.25  # Total price range covered by heatmap
        min_price = mid_price - (price_range / 2)
        max_price = mid_price + (price_range / 2)

        ladder_prices = [mid_price + (i - total_rows // 2) * 0.25 for i in range(total_rows)]

        # Calculate y-positions for best bid and ask lines (in pixels)
        if ladder_prices:
            min_price = ladder_prices[0]
            bid_y = (best_bid - min_price) / 0.25 * 25
            ask_y = (best_ask - min_price) / 0.25 * 25

            self.best_bid_line.setPos(bid_y + 12.5)
            self.best_ask_line.setPos(ask_y + 12.5)
        
        max_bid_size = max((b[1] for b in bids), default=1)
        max_ask_size = max((a[1] for a in asks), default=1)
        max_size = max(max_bid_size, max_ask_size, 1)

        # Initialize new heatmap column
        bookmap_column = np.zeros(self.heatmap_rows)

        # Map prices to heatmap rows
        for price, size in [(b[0], b[1]) for b in bids] + [(a[0], a[1]) for a in asks]:
            if min_price <= price <= max_price:
                # Map price to heatmap row index
                row_idx = int((price - min_price) / 0.25)
                if 0 <= row_idx < self.heatmap_rows:
                    bookmap_column[row_idx] = size / max_size

        for i, price in enumerate(reversed(ladder_prices)):  # highest price at top
            price_item = QTableWidgetItem(f"{price:.2f}")
            self.table.setItem(i, 0, price_item)

            bid = next((b for b in bids if abs(b[0] - price) < 1e-6), None)
            ask = next((a for a in asks if abs(a[0] - price) < 1e-6), None)

            self.table.removeCellWidget(i, 1)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(True)
            bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background-color: #2e2e2e;
                    text-align: left;
                    padding: 0px;
                }
            """)

            if bid:
                size = bid[1]
                percent = min(int(size / max_size * 100), 100)
                bar.setValue(percent)
                bar.setFormat(f"{size:.0f}")
                bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        background-color: #2e2e2e;
                        text-align: left;
                        padding: 0px;
                    }
                    QProgressBar::chunk {
                        background-color: rgb(48, 151, 0);
                    }
                """)

            elif ask:
                size = ask[1]
                percent = min(int(size / max_size * 100), 100)
                bar.setValue(percent)
                bar.setFormat(f"{size:.0f}")
                bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        background-color: #2e2e2e;
                        text-align: left;
                        padding: 0px;
                    }
                    QProgressBar::chunk {
                        background-color: rgb(230, 77, 57);
                    }
                """)

            else:
                bar.setValue(0)
                bar.setFormat("")

            self.table.setCellWidget(i, 1, bar)

        # --- Bookmap Heatmap Update ---
        self.heatmap = np.roll(self.heatmap, -1, axis=1)  # scroll left
        self.heatmap[:, -1] = bookmap_column  # insert new column
        self.image_view.setImage(
            self.heatmap.T,
            autoLevels=False,
            autoRange=False,
            levels=(0, 1),
            scale=(1, 25),     # width=1, height=25
            pos=(0, 0)
        )

        # Align so image is fully in view and does not have black padding
        vb = self.image_view.getView()
        vb.setRange(
            xRange=(0, self.heatmap_cols),
            yRange=(0, self.heatmap_rows * 25),
            padding=0
        )

        # --- DOM Pressure Calculation ---
        top_n = 5
        bid_pressure = sum(b[1] for b in bids[:top_n])
        ask_pressure = sum(a[1] for a in asks[:top_n])
        dom_pressure = bid_pressure - ask_pressure
        
        if dom_pressure > 100:
            color = "#2ecc71"  # Green for buy pressure
        elif dom_pressure < -100:
            color = "#e74c3c"  # Red for sell pressure
        else:
            color = "#f1c40f"  # Yellow for neutral/low pressure

        # Update label
        self.pressure_label.setText(f"DOM Pressure: {dom_pressure:.0f}")
        self.pressure_label.setStyleSheet(f"color: white; background-color: {color}; padding: 4px; border-radius: 4px;")


    def closeEvent(self, event):
        print("[INFO] [gui.py] Closing window...")

        self.timer.stop()
        
        # Disconnect from IBKR
        print("[INFO] [gui.py] Disconnecting from IBKR")
        data_manager.disconnect()
        
        # Accept the close event
        event.accept()

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = OrderBookWindow()
#     window.show()
#     sys.exit(app.exec())

"""
prompts

Prices color-coded for best bid/ask

Auto-resizing or smooth real-time updates

A heatmap visualization on top of this

bookmap
"""
