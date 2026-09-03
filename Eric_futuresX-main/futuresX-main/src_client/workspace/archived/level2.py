from ib_insync import *
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import date

# Connect to IB Gateway / TWS
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)  # 7497 is paper, 7496 is live



# Define the contract you want Level 2 data for
# contract = Stock('AAPL', 'SMART', 'USD')
# contract = Future('ES', '202506', 'GLOBEX')
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
mycontract.exchange = "CME"  # Use GLOBEX not CME
mycontract.lastTradeDateOrContractMonth = expiry
mycontract.includeExpired = False  # (lowercase 'i')



# Request market depth
ib.reqMktDepth(mycontract, numRows=10)

print(mycontract.marketDepthRows)
# Set up plot
fig, ax = plt.subplots()
bids = []
asks = []

# def animate(i):
#     global bids, asks
#     bids = []
#     asks = []
    
#     # Update bid and ask lists
    
#     for depth in mycontract.marketDepthRows:
#         if depth.side == 1:  # Bid
#             bids.append((depth.price, depth.size))
#         elif depth.side == 0:  # Ask
#             asks.append((depth.price, depth.size))
    
#     bids.sort(reverse=True)  # Highest bid first
#     asks.sort()              # Lowest ask first
    
#     ax.clear()
#     if bids:
#         bid_prices, bid_sizes = zip(*bids)
#         ax.barh(bid_prices, bid_sizes, color='green', alpha=0.6, label='Bids')
#     if asks:
#         ask_prices, ask_sizes = zip(*asks)
#         ax.barh(ask_prices, [-s for s in ask_sizes], color='red', alpha=0.6, label='Asks')
    
#     ax.set_xlabel('Size')
#     ax.set_ylabel('Price')
#     ax.legend()

# # Animate
# ani = animation.FuncAnimation(fig, animate, interval=500)

# plt.show()

# # Keep IB connection alive
# ib.run()
