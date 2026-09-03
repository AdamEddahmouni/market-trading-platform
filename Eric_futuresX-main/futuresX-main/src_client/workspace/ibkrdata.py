from threading import Lock
from ibkr_manager import app

"""
Manages clean market data from IBKR & Topstep
"""

class DataManager:
    def __init__(self):
        self.lock = Lock()
        self.bids = []
        self.asks = []
        self.ladder = []

    def update(self):
        """Pulls latest bids and asks from IBApp"""
        with self.lock:
            self.bids, self.asks = app.get_market_depth()

    def get_bids(self):
        self.update()
        return self.bids

    def get_asks(self):
        self.update()
        return self.asks

    def get_best_bid(self):
        self.update()
        return max(self.bids, key=lambda x: x[0])[0] if self.bids else None

    def get_best_ask(self):
        self.update()
        return min(self.asks, key=lambda x: x[0])[0] if self.asks else None

    def get_mid_price(self):
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid is not None and ask is not None:
            return round((bid + ask) / 2 / 0.25) * 0.25
        return None
    
    def get_market_depth(self):
        bids, asks = app.get_market_depth()
        
        bids = [b for b in bids if b is not None]
        asks = [a for a in asks if a is not None]

        self.ladder = asks[::-1] + bids

        # print(self.ladder)
        return bids, asks
    

    # -------------- EXECUTION ORDERS --------------
    def market_order(self, contractName: str, size: int, side: str):
        if side == "BUY":
            app.buy_market_order(contractName, size)
        elif side == "SELL":
            app.sell_market_order(contractName, size)
        else:
            print(f"[ERROR] [ibkr_manager.py] [market_order] Invalid side: {side}")

    def limit_order(self, contractName: str, size: int, price: float, side: str):
        if side == "BUY":
            app.buy_limit_order(contractName, size, price)
        elif side == "SELL":
            app.sell_limit_order(contractName, size, price)
        else:
            print(f"[ERROR] [ibkr_manager.py] [limit_order] Invalid side: {side}")
    
    def buy_bracket_order_market(self, contractName: str, size: int, take_profit_price: float, stop_loss_price: float):
        app.buy_bracket_order_market(contractName, size, take_profit_price, stop_loss_price)
    
    def sell_bracket_order_market(self, contractName: str, size: int, take_profit_price: float, stop_loss_price: float):
        app.sell_bracket_order_market(contractName, size, take_profit_price, stop_loss_price)
    
    def buy_bracket_order_limit(self, contractName: str, size: int, limit_price: float, take_profit_price: float, stop_loss_price: float):
        app.buy_bracket_order_limit(contractName, size, limit_price, take_profit_price, stop_loss_price)

    def sell_bracket_order_limit(self, contractName: str, size: int, limit_price: float, take_profit_price: float, stop_loss_price: float):
        app.sell_bracket_order_limit(contractName, size, limit_price, take_profit_price, stop_loss_price)

    def get_positions(self):
        return app.get_positions()
   
    
    def cancel_all_orders(self):
        app.cancel_all_orders()


    def disconnect(self):
        if app.isConnected():
            app.disconnect()

# Singleton instance for global use
data_manager = DataManager()
