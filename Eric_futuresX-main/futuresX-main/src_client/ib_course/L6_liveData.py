from ibapi.client import *
from ibapi.wrapper import *
import datetime
import time
import threading
from ibapi.ticktype import TickTypeEnum

port = 7497


class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: OrderId):
        self.orderId = orderId
    
    def nextId(self):
        self.orderId += 1
        return self.orderId
    
    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}, orderReject: {advancedOrderReject}")
      
    def tickPrice(self, reqId, tickType, price, attrib):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, price: {price}, attrib: {attrib}")
      
    def tickSize(self, reqId, tickType, size):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, size: {size}")
    
    def updateMktDepth(self, reqId: TickerId, position: int, operation: int, side: int, price: float, size: Decimal):
             super().updateMktDepth(reqId, position, operation, side, price, size)
             print("UpdateMarketDepth. ReqId:", reqId, "Position:", position, "Operation:",
                   operation, "Side:", side, "Price:", floatMaxString(price), "Size:", decimalMaxString(size))
    
    def updateMktDepthL2(self, reqId: TickerId, position: int, marketMaker: str, operation: int, side: int, price: float, size: Decimal, isSmartDepth: bool):
             super().updateMktDepthL2(reqId, position, marketMaker, operation, side, price, size, isSmartDepth)
             print("UpdateMarketDepthL2. ReqId:", reqId, "Position:", position, "MarketMaker:", marketMaker, "Operation:", operation, "Side:", side, "Price:", floatMaxString(price), "Size:", decimalMaxString(size), "isSmartDepth:", isSmartDepth)
    
app = TestApp()
app.connect("127.0.0.1", port, 0)
threading.Thread(target=app.run).start()
time.sleep(1)

mycontract = Contract()
# mycontract.symbol = "AAPL"
# mycontract.secType = "STK"
# mycontract.exchange = "SMART"
# mycontract.currency = "USD"
mycontract.symbol = "ES"
mycontract.secType = "FUT"
mycontract.currency = "USD"
mycontract.exchange = "CME"
mycontract.lastTradeDateOrContractMonth = 202506

app.reqMarketDataType(1)
app.reqMktData(app.nextId(), mycontract, "232", False, False, [])

# app.reqMktDepth(2001, ContractSamples.EurGbpFx(), 5, False, [])
# app.reqMktDepth(app.nextId(), mycontract, 10, False, [])
# app.reqMktDepthExchanges()

