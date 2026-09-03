import backtrader as bt
import yfinance as yf
import pandas as pd
import numpy as np

class DipBuyStrategy(bt.Strategy):
    # params = (
    #     ("dip_pct", 0.50),
    #     ("take_profit", 0.50),
    #     ("stop_loss", 0.25),
    # )

    def __init__(self):
        self.dataclose = self.datas[0].close

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))
    
    def next(self):     
        self.log('Close, %.2f' % self.dataclose[0])

        if self.dataclose[0] < self.dataclose[-1]:
            # current close less than previous close

            if self.dataclose[-1] < self.dataclose[-2]:
                # previous close less than the previous close

                # BUY, BUY, BUY!!! (with all possible default parameters)
                self.log('BUY CREATE, %.2f' % self.dataclose[0])
                self.buy()
                

# Download data
df = yf.download("SPXL", start="2015-01-01", end="2024-12-31")
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

print(df.head())

df = df[['Open', 'High', 'Low', 'Close', 'Volume']]  # drop 'Adj Close' to avoid confusion
df.columns = [col.lower() for col in df.columns]     # make lowercase for backtrader

# STEP 2: Pass data to Backtrader
data = bt.feeds.PandasData(
    dataname=df,
    open='open',
    high='high',
    low='low',
    close='close',
    volume='volume',
    openinterest=None
)

cerebro = bt.Cerebro()
cerebro.addstrategy(DipBuyStrategy)
cerebro.adddata(data)
cerebro.broker.set_cash(100000)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

results = cerebro.run()
cerebro.plot()

# Print analysis
strat = results[0]
print("Final portfolio value: ${:.2f}".format(cerebro.broker.getvalue()))
print("Sharpe Ratio:", strat.analyzers.sharpe.get_analysis())
print("Trade Analysis:", strat.analyzers.trades.get_analysis())
