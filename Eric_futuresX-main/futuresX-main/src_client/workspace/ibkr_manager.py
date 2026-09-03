from decimal import Decimal
from ibapi.client import *
from ibapi.wrapper import *
import datetime
import time
import threading
from ibapi.ticktype import TickTypeEnum
from utils import *

port = 7497


class IBApp(EClient, EWrapper):

    # ----------- INTERNAL METHODS ------------
    def __init__(self):
        EClient.__init__(self, self)
        
        # Format: (price, size) Initiate as empty list
        self.bids = [None] * 10  
        self.asks = [None] * 10

        self.lock = threading.Lock()

        # Bid and Ask lists
        self.bids_list = []
        self.asks_list = []


        self.current_position = 0
        self.position_event = threading.Event()


    def nextValidId(self, orderId: OrderId):
        self.orderId = orderId
        print(f"[INFO] [ibkr_manager.py] Connection established. Order ID: {orderId}")
        print(f"[INFO] [ibkr_manager.py] [nextValidId] Opening ES Market Depth data")
        self.read_market_depth("ES")
    
    def nextId(self):
        self.orderId += 1
        print(f"[INFO] [ibkr_manager.py] New Connection Order ID: {self.orderId}")
        return self.orderId
    
    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}, orderReject: {advancedOrderReject}")
      
    def tickPrice(self, reqId, tickType, price, attrib):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, price: {price}, attrib: {attrib}")
      
    def tickSize(self, reqId, tickType, size):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.toStr(tickType)}, size: {size}")


    



    def updateMktDepth(self, reqId: TickerId, position: int, operation: int, side: int, price: float, size: Decimal):
        with self.lock:
            book = self.bids if side == 1 else self.asks

            if position >= len(book):
                return  # Ignore positions beyond requested depth

             # Insert or Update position
            if operation == 0 or operation == 1: 
                book[position] = (price, size)
            elif operation == 2:  # Delete
                book[position] = None

            # self.print_order_book()

            # ASDASDSADSAD
            self.bids_list = [item for item in self.bids if item is not None]
            self.asks_list = [item for item in self.asks if item is not None]
            
            '''
                operation to perform in the row: insert (0), update (1) or remove (2).
                # Side is either 1 or 0. Ask is 0, Bid is 1

                UpdateMarketDepth. ReqId: 10 Position: 0 Operation: 1 Side: 0 Price: 5901.75 Size: 5
                UpdateMarketDepth. ReqId: 10 Position: 2 Operation: 1 Side: 0 Price: 5902.25 Size: 17
                UpdateMarketDepth. ReqId: 10 Position: 3 Operation: 1 Side: 0 Price: 5902.5 Size: 18
                UpdateMarketDepth. ReqId: 10 Position: 1 Operation: 1 Side: 1 Price: 5901.25 Size: 11
            '''
            # code from documentation to print all entries
            # super().updateMktDepth(reqId, position, operation, side, price, size)
            # print("UpdateMarketDepth. ReqId:", reqId, "Position:", position, "Operation:",
            #     operation, "Side:", side, "Price:", floatMaxString(price), "Size:", decimalMaxString(size))
    
    def updateMktDepthL2(self, reqId: TickerId, position: int, marketMaker: str, operation: int, side: int, price: float, size: Decimal, isSmartDepth: bool):
            pass
            # This method is not needed
            #  super().updateMktDepthL2(reqId, position, marketMaker, operation, side, price, size, isSmartDepth)
            #  print("UpdateMarketDepthL2. ReqId:", reqId, "Position:", position, "MarketMaker:", marketMaker, "Operation:", operation, "Side:", side, "Price:", floatMaxString(price), "Size:", decimalMaxString(size), "isSmartDepth:", isSmartDepth)
    
    # def print_order_book(self):
    #     print("\n" + "-" * 50)
    #     print(f" {'Bids':<24} | {'Asks':<24}")
    #     print("-" * 50)

    #     for i in range(10):
    #         bid_str = ""
    #         ask_str = ""

    #         if self.bids[i]:
    #             price, size = self.bids[i]
    #             bid_str = f"{size:.0f}@{price:.2f}"

    #         if self.asks[i]:
    #             price, size = self.asks[i]
    #             ask_str = f"{size:.0f}@{price:.2f}"

    #         print(f" {bid_str:<24} | {ask_str:<24}")

    #     print("-" * 50 + "\n")
    def position(self, account: str, contract: Contract, position: Decimal,
                      avgCost: float):
        super().position(account, contract, position, avgCost)
        # print("Position.", "Account:", account, "Symbol:", contract.symbol, "SecType:",
        #     contract.secType, "Currency:", contract.currency,
        #     "Position:", (position), "Avg cost:", (avgCost))
        
        print(f"[POSITION] {position} contracts of {contract.symbol} at avg cost {avgCost}")
        with self.lock:
            self.current_position = position
            self.position_event.set()
             
    def read_market_depth(self, contractName: str):
        contract = get_latest_futures_contract(contractName)
        print(f"[INFO] [ibkr_manager.py] [read_market_depth] Contract: {contract}")
        # mycontract = Contract()
        # # mycontract.symbol = "AAPL"
        # # mycontract.secType = "STK"
        # # mycontract.exchange = "SMART"
        # # mycontract.currency = "USD"
        # mycontract.symbol = contractName
        # mycontract.secType = "FUT"
        # mycontract.currency = "USD"
        # mycontract.exchange = "CME"
        # mycontract.lastTradeDateOrContractMonth = 202506

        app.reqMarketDataType(1)
        # app.reqMktData(app.nextId(), mycontract, "232", False, False, [])

        # app.reqMktDepth(2001, ContractSamples.EurGbpFx(), 5, False, [])
        app.reqMktDepth(app.nextId(), contract, 10, False, [])
        # app.reqMktDepthExchanges()

    # ------------ INTERNAL ORDER OUTPUT ------------
    def openOrder(self, orderId: OrderId, contract: Contract, order: Order, orderState: OrderState):
        print(f"openOrder. orderId: {orderId}, contract: {contract}, order: {order}")

    def orderStatus(self, orderId: OrderId, status: str, filled: Decimal, remaining: Decimal, avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, clientId: int, whyHeld: str, mktCapPrice: float):
        print(f"orderId: {orderId}, status: {status}, filled: {filled}, remaining: {remaining}, avgFillPrice: {avgFillPrice}, permId: {permId}, parentId: {parentId}, lastFillPrice: {lastFillPrice}, clientId: {clientId}, whyHeld: {whyHeld}, mktCapPrice: {mktCapPrice}")

    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        print(f"reqId: {reqId}, contract: {contract}, execution: {execution}")

    # ----------- METHODS FOR DATA MANAGER ------------
    def get_market_depth(self):
        with self.lock:
            return self.bids_list, self.asks_list
    
    def get_positions(self):
        self.position_event.clear()  # reset the event
        self.reqPositions()
        
        if self.position_event.wait(timeout=1): #wait 1 second
            with self.lock:
                return self.current_position
        else:
            print("[ERROR] Timed out waiting for position.")
            return None

    # ------------ ORDER METHODS ------------
    def buy_market_order(self, contractName: str, size: int):
        contract = get_latest_futures_contract(contractName)

        order = Order()
        order.orderId = self.nextId()
        order.action = "BUY"
        order.tif = "GTC"
        order.orderType = "MKT"
        order.totalQuantity = size
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        self.placeOrder(order.orderId, contract, order)

        print(f"[INFO] [ibkr_manager.py] [buy_market_order] Placed buy market order. orderId: {order.orderId}, contract: {contract.symbol}, order: {order}")

    def sell_market_order(self, contractName: str, size: int):
        contract = get_latest_futures_contract(contractName)

        order = Order()
        order.orderId = self.nextId()
        order.action = "SELL"
        order.tif = "GTC"
        order.orderType = "MKT"
        order.totalQuantity = size
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        self.placeOrder(order.orderId, contract, order)

        print(f"[INFO] [ibkr_manager.py] [sell_market_order] Placed sell market order. orderId: {order.orderId}, contract: {contract.symbol}, order: {order}")

    def buy_limit_order(self, contractName: str, size: int, price: float):
        contract = get_latest_futures_contract(contractName)

        order = Order()
        order.orderId = self.nextId()
        order.action = "BUY"
        order.tif = "GTC"
        order.orderType = "LMT"
        order.lmtPrice = price
        order.totalQuantity = size
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        self.placeOrder(order.orderId, contract, order)
        print(f"[INFO] [ibkr_manager.py] [buy_limit_order] Placed buy limit order. orderId: {order.orderId}, contract: {contract.symbol}, order: {order}")

    def sell_limit_order(self, contractName: str, size: int, price: float):
        contract = get_latest_futures_contract(contractName)

        order = Order()
        order.orderId = self.nextId()
        order.action = "SELL"
        order.tif = "GTC"
        order.orderType = "LMT"
        order.lmtPrice = price
        order.totalQuantity = size
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        self.placeOrder(order.orderId, contract, order)
        print(f"[INFO] [ibkr_manager.py] [sell_limit_order] Placed sell limit order. orderId: {order.orderId}, contract: {contract.symbol}, order: {order}")
    
    def buy_bracket_order_market(self, contractName: str, size: int, take_profit_price: float, stop_loss_price: float):
        contract = get_latest_futures_contract(contractName)

        # Parent order
        parent = Order()
        parent.orderId = self.nextId()
        parent.action = "BUY"
        parent.tif = "GTC"
        parent.orderType = "MKT"
        parent.totalQuantity = size
        parent.transmit = False
        parent.eTradeOnly = ""
        parent.firmQuoteOnly = ""

        # Profit taker
        profit_taker = Order()
        profit_taker.orderId = parent.orderId + 1
        profit_taker.parentId = parent.orderId
        profit_taker.action = "SELL"
        profit_taker.orderType = "LMT"
        profit_taker.lmtPrice = take_profit_price
        profit_taker.totalQuantity = size
        profit_taker.transmit = False
        profit_taker.eTradeOnly = ""
        profit_taker.firmQuoteOnly = ""

        # Stop loss
        stop_loss = Order()
        stop_loss.orderId = parent.orderId + 2
        stop_loss.parentId = parent.orderId
        stop_loss.orderType = "STP"
        stop_loss.auxPrice = stop_loss_price
        stop_loss.action = "SELL"
        stop_loss.totalQuantity = size
        stop_loss.transmit = True
        stop_loss.eTradeOnly = ""
        stop_loss.firmQuoteOnly = ""

        self.placeOrder(parent.orderId, contract, parent)
        self.placeOrder(profit_taker.orderId, contract, profit_taker)
        self.placeOrder(stop_loss.orderId, contract, stop_loss)

        print(f"[INFO] [ibkr_manager.py] [buy_bracket_order_market] Placed buy market bracket order. orderId: {parent.orderId}, contract: {contract.symbol}, order: {parent}")
        print(f"[INFO] [ibkr_manager.py] [buy_bracket_order_market] Placed buy market bracket order. orderId: {profit_taker.orderId}, contract: {contract.symbol}, TP: {profit_taker}")
        print(f"[INFO] [ibkr_manager.py] [buy_bracket_order_market] Placed buy market bracket order. orderId: {stop_loss.orderId}, contract: {contract.symbol}, SL: {stop_loss}")

    def sell_bracket_order_market(self, contractName: str, size: int, take_profit_price: float, stop_loss_price: float):
        contract = get_latest_futures_contract(contractName)

        # Parent order
        parent = Order()
        parent.orderId = self.nextId()
        parent.action = "SELL"
        parent.tif = "GTC"
        parent.orderType = "MKT"
        parent.totalQuantity = size
        parent.transmit = False
        parent.eTradeOnly = ""
        parent.firmQuoteOnly = ""

        # Profit taker
        profit_taker = Order()
        profit_taker.orderId = parent.orderId + 1
        profit_taker.parentId = parent.orderId
        profit_taker.action = "BUY"
        profit_taker.orderType = "LMT"
        profit_taker.lmtPrice = take_profit_price
        profit_taker.totalQuantity = size
        profit_taker.transmit = False
        profit_taker.eTradeOnly = ""
        profit_taker.firmQuoteOnly = ""

        # Stop loss
        stop_loss = Order()
        stop_loss.orderId = parent.orderId + 2
        stop_loss.parentId = parent.orderId
        stop_loss.orderType = "STP"
        stop_loss.auxPrice = stop_loss_price
        stop_loss.action = "BUY"
        stop_loss.totalQuantity = size
        stop_loss.transmit = True
        stop_loss.eTradeOnly = ""
        stop_loss.firmQuoteOnly = ""

        self.placeOrder(parent.orderId, contract, parent)
        self.placeOrder(profit_taker.orderId, contract, profit_taker)
        self.placeOrder(stop_loss.orderId, contract, stop_loss)

        print(f"[INFO] [ibkr_manager.py] [sell_bracket_order_market] Placed sell market bracket order. orderId: {parent.orderId}, contract: {contract.symbol}, order: {parent}")
        print(f"[INFO] [ibkr_manager.py] [sell_bracket_order_market] Placed sell market bracket order. orderId: {profit_taker.orderId}, contract: {contract.symbol}, TP: {profit_taker}")
        print(f"[INFO] [ibkr_manager.py] [sell_bracket_order_market] Placed sell market bracket order. orderId: {stop_loss.orderId}, contract: {contract.symbol}, SL: {stop_loss}")

    def buy_bracket_order_limit(self, contractName: str, size: int, limit_price: float, take_profit_price: float, stop_loss_price: float):
        contract = get_latest_futures_contract(contractName)

        # Parent order
        parent = Order()
        parent.orderId = self.nextId()
        parent.action = "BUY"
        parent.tif = "GTC"
        parent.orderType = "LMT"
        parent.lmtPrice = limit_price
        parent.totalQuantity = size
        parent.transmit = False
        parent.eTradeOnly = ""
        parent.firmQuoteOnly = ""

        # Profit taker
        profit_taker = Order()
        profit_taker.orderId = parent.orderId + 1
        profit_taker.parentId = parent.orderId
        profit_taker.action = "SELL"
        profit_taker.orderType = "LMT"
        profit_taker.lmtPrice = take_profit_price
        profit_taker.totalQuantity = size
        profit_taker.transmit = False
        profit_taker.eTradeOnly = ""
        profit_taker.firmQuoteOnly = ""

        # Stop loss
        stop_loss = Order()
        stop_loss.orderId = parent.orderId + 2
        stop_loss.parentId = parent.orderId
        stop_loss.orderType = "STP"
        stop_loss.auxPrice = stop_loss_price
        stop_loss.action = "SELL"
        stop_loss.totalQuantity = size
        stop_loss.transmit = True
        stop_loss.eTradeOnly = ""
        stop_loss.firmQuoteOnly = ""

        self.placeOrder(parent.orderId, contract, parent)
        self.placeOrder(profit_taker.orderId, contract, profit_taker)
        self.placeOrder(stop_loss.orderId, contract, stop_loss)

        print(f"[INFO] [ibkr_manager.py] [buy_bracket_order_limit] Placed buy limit bracket order. orderId: {parent.orderId}, contract: {contract.symbol}, order: {parent}")
        print(f"[INFO] [ibkr_manager.py] [buy_bracket_order_limit] Placed buy limit bracket order. orderId: {profit_taker.orderId}, contract: {contract.symbol}, TP: {profit_taker}")
        print(f"[INFO] [ibkr_manager.py] [buy_bracket_order_limit] Placed buy limit bracket order. orderId: {stop_loss.orderId}, contract: {contract.symbol}, SL: {stop_loss}")
    
    def sell_bracket_order_limit(self, contractName: str, size: int, limit_price: float, take_profit_price: float, stop_loss_price: float):
        contract = get_latest_futures_contract(contractName)

        # Parent order
        parent = Order()
        parent.orderId = self.nextId()
        parent.action = "SELL"
        parent.tif = "GTC"
        parent.orderType = "LMT"
        parent.lmtPrice = limit_price
        parent.totalQuantity = size
        parent.transmit = False
        parent.eTradeOnly = ""
        parent.firmQuoteOnly = ""

        # Profit taker
        profit_taker = Order()
        profit_taker.orderId = parent.orderId + 1
        profit_taker.parentId = parent.orderId
        profit_taker.action = "BUY"
        profit_taker.orderType = "LMT"
        profit_taker.lmtPrice = take_profit_price
        profit_taker.totalQuantity = size
        profit_taker.transmit = False
        profit_taker.eTradeOnly = ""
        profit_taker.firmQuoteOnly = ""

        # Stop loss
        stop_loss = Order()
        stop_loss.orderId = parent.orderId + 2
        stop_loss.parentId = parent.orderId
        stop_loss.orderType = "STP"
        stop_loss.auxPrice = stop_loss_price
        stop_loss.action = "BUY"
        stop_loss.totalQuantity = size
        stop_loss.transmit = True
        stop_loss.eTradeOnly = ""
        stop_loss.firmQuoteOnly = ""

        self.placeOrder(parent.orderId, contract, parent)
        self.placeOrder(profit_taker.orderId, contract, profit_taker)
        self.placeOrder(stop_loss.orderId, contract, stop_loss)

        print(f"[INFO] [ibkr_manager.py] [sell_bracket_order_limit] Placed sell limit bracket order. orderId: {parent.orderId}, contract: {contract.symbol}, order: {parent}")
        print(f"[INFO] [ibkr_manager.py] [sell_bracket_order_limit] Placed sell limit bracket order. orderId: {profit_taker.orderId}, contract: {contract.symbol}, TP: {profit_taker}")
        print(f"[INFO] [ibkr_manager.py] [sell_bracket_order_limit] Placed sell limit bracket order. orderId: {stop_loss.orderId}, contract: {contract.symbol}, SL: {stop_loss}")

app = IBApp()
app.connect("127.0.0.1", port, 0)
threading.Thread(target=app.run, daemon=True).start()
time.sleep(1)
# TEST METHODS HERE

# print(app.get_positions())
# app.buy_market_order("ES", 1)
# app.buy_limit_order("ES", 1, 5914.00)
# app.buy_bracket_order_market("ES", 1, 6000.00, 5970.00)
# app.sell_bracket_order_market("ES", 1, 5970.00, 6000.00)
# app.sell_bracket_order_limit("ES", 1, 5979.00, 6000.00, 5940.00)


# ----------- PUBLIC METHODS FOR USE IN OTHER FILES ------------
def get_market_depth():
    return app.get_market_depth()

def get_positions():
    return app.get_positions()

def buy_market_order(contractName: str, size: int):
    app.buy_market_order(contractName, size)

def sell_market_order(contractName: str, size: int):
    app.sell_market_order(contractName, size)


def buy_limit_order(contractName: str, size: int, price: float):
    app.buy_limit_order(contractName, size, price)

def sell_limit_order(contractName: str, size: int, price: float):
    app.sell_limit_order(contractName, size, price)

def buy_bracket_order_market(contractName: str, size: int, take_profit_price: float, stop_loss_price: float):
    app.buy_bracket_order_market(contractName, size, take_profit_price, stop_loss_price)

def sell_bracket_order_market(contractName: str, size: int, take_profit_price: float, stop_loss_price: float):
    app.sell_bracket_order_market(contractName, size, take_profit_price, stop_loss_price)

def buy_bracket_order_limit(contractName: str, size: int, limit_price: float, take_profit_price: float, stop_loss_price: float):
    app.buy_bracket_order_limit(contractName, size, limit_price, take_profit_price, stop_loss_price)

def sell_bracket_order_limit(contractName: str, size: int, limit_price: float, take_profit_price: float, stop_loss_price: float):
    app.sell_bracket_order_limit(contractName, size, limit_price, take_profit_price, stop_loss_price)

