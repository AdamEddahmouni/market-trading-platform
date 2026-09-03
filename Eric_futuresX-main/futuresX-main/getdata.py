from ibapi.client import *
from ibapi.wrapper import *
import threading
import time
from datetime import date
from ibapi.ticktype import TickTypeEnum

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
    
    def error(self, reqId, errorCode, errorString, advancedOrderReject):
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}, orderReject: {advancedOrderReject}")

    # def error(self, reqId, errorCode, errorString):
    #     print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}")

    def contractDetails(self, reqId, contractDetails):
        attrs = vars(contractDetails)
        # print("\n".join(f"{name}: {value}" for name,value in attrs.items()))
        print(contractDetails.contract)

    def contractDetailsEnd(self, reqId):
        print("End of contract details")
        self.disconnect()

    def tickPrice(self, reqId, tickType, price, attrib):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, price: {price}, attrib: {attrib}")

    def tickSize(self, reqId, tickType, size):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, size: {size}")

app = TradeApp()
app.connect("127.0.0.1", 7497, 0)
# 7497 Paper, 7496 Live
threading.Thread(target=app.run).start()
time.sleep(1)

for i in range(0,5):
    print(app.nextId())
    app.reqCurrentTime()


today = date.today()
year = today.year
month = today.month

# ES expires March (03), June (06), September (09), December (12)
if month <= 3:
    expiry = f"{year}03"
elif month <= 6:
    expiry = f"{year}06"
elif month <= 9:
    expiry = f"{year}09"
else:
    expiry = f"{year}12"

# If December passed, roll to next March
if month == 12 and today.day > 15:
    expiry = f"{year+1}03"

mycontract = Contract()
mycontract.symbol = "ES"
mycontract.secType = "FUT"
mycontract.currency = "USD"
mycontract.exchange = "CME"  
mycontract.lastTradeDateOrContractMonth = expiry
mycontract.includeExpired = False  # (lowercase 'i')

print("Futures Contract" + expiry)

# app.reqContractDetails(app.nextId(), mycontract)

# Get Live Mareket Data
app.reqMarketDataType(1)
app.reqMktData(app.nextId(), mycontract, "232", False, False, [])

# reqId: 15, tickType: LAST, price: 5906.0, attrib: CanAutoExecute: 0, PastLimit: 0, PreOpen: 0
