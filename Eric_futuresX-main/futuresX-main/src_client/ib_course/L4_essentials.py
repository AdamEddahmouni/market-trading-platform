from ibapi.client import *
from ibapi.wrapper import *
import threading
import time

# python getdata.py --port 7497
class TradeApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        self.orderId = orderId

    def nextId(self):
        self.orderId += 1
        return self.orderId
    
    def currentTime(self, time):
        print(time)
    
    def error(self, reqId, errorCode, errorString, advancedOrderReject = ""):
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}, orderReject: {advancedOrderReject}")
    # def error(self, reqId, errorCode, errorString):
    #     print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}")

app = TradeApp()
app.connect("127.0.0.1", 7497, 0)
# 7497 Paper, 7496 Live
threading.Thread(target=app.run).start()
time.sleep(1)

for i in range(0,5):
    print(app.nextId())
    app.reqCurrentTime()

