# FuturesX
futures orderbook level 2 algo trading

## Dev setup instructions:
- download IBKR TWS
- follow https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/ to activate the api in tws
- get level 2 CME futures data for ES
- pip install ibapi
- you may need to pip install many others including PyQt6

## Run Instructions
FOR ALL EXCEPT BACKTEST YOU NEED TWS API LOGGED INTO PAPER TRADING MODE.

### To Run Bookmap Clone:
run in vscode: src_client/workspace/main.py

### To Backtest:
run in vscode: src_client/workspace/historical data/backtest_main.py
OR
run in vscode: src_client/workspace/historical data/backtest_main2.py

### To Real Time Paper Trade the Algorithm:
run in vscode: src_client/workspace/historical data/live_trader.py
* Bracket TP/SL transmit logic was fixed 2026-08-15 (`parent.transmit=False`, final child `transmit=True`). **Re-validate in TWS paper** before relying on `live_trader.py` for risk-managed exits.

## Current Development Progress
<img width="1805" height="692" alt="image" src="https://github.com/user-attachments/assets/4363af8b-3d53-490a-bac2-59a5dcc1bf61" />
