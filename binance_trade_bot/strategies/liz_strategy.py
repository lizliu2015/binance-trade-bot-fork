import sys
from datetime import datetime, timedelta, timezone

from binance_trade_bot.auto_trader import AutoTrader

TARGET = "ETH"
DATE_STR_FORMAT = '%Y-%m-%d %H:%M:%S'

''' Kline format
[
    1499040000000,      // Open time
    "0.01634790",       // Open
    "0.80000000",       // High
    "0.01575800",       // Low
    "0.01577100",       // Close
    "148976.11427815",  // Volume
    1499644799999,      // Close time
    "2434.19055334",    // Quote asset volume
    308,                // Number of trades
    "1756.87402397",    // Taker buy base asset volume
    "28.46694368",      // Taker buy quote asset volume
    "17928899.62484339" // Ignore.
  ]
'''
def formatKlines(kline: list):
    kline[0] = datetime.utcfromtimestamp(kline[0]/1000).strftime(DATE_STR_FORMAT)
    kline[6] = datetime.utcfromtimestamp(kline[6]/1000).strftime(DATE_STR_FORMAT)
    return kline

def rollingAvg(kline: list):
    last_3_4hr = kline[-4:-1]
    last_5_4hr = kline[-6:-1]
    ma3_4hr = sum([float(k[4]) for k in last_3_4hr])/len(last_3_4hr)
    ma5_4hr = sum([float(k[4]) for k in last_5_4hr])/len(last_5_4hr)
    return {"ma3_4hr": ma3_4hr, "ma5_4hr": ma5_4hr}

class Strategy(AutoTrader):
    def initialize(self):
        super().initialize()
        self.initialize_current_coin()

        self.target = self.db.get_coin(TARGET)

    def scout(self, current_time = None):
        """
        Scout for potential jumps from the current coin to another coin
        """
        all_tickers = self.manager.get_all_market_tickers()
        current_coin = self.db.get_current_coin()

        if current_time is None:
            current_time = datetime.today()

        start_time = (current_time - timedelta(days=1)).replace(tzinfo=timezone.utc).timestamp()
        klines = self.manager.binance_client.get_historical_klines(self.target + self.config.BRIDGE, self.manager.binance_client.KLINE_INTERVAL_4HOUR, str(start_time), str(current_time))
        klines = [formatKlines(k) for k in klines]
        avgs = rollingAvg(klines)

        # BUY BUY BUY!
        # print(f"{start_time.strftime(DATE_STR_FORMAT)} - {current_coin}")
        if avgs["ma3_4hr"] > avgs["ma5_4hr"] and current_coin.symbol == self.config.BRIDGE.symbol:
            print(f"BUY - {current_time} - {avgs}")
            if self.manager.buy_alt(self.target, self.config.BRIDGE, all_tickers):
                self.db.set_current_coin(self.target)
            else:
                self.logger.info("Couldn't buy, going back to scouting mode...")

        # SELL SELL SELL!
        elif avgs["ma5_4hr"] > avgs["ma3_4hr"] and current_coin.symbol == TARGET:
            print(f"SELL - {current_time} - {avgs}")
            if self.manager.sell_alt(self.target, self.config.BRIDGE, all_tickers):
                self.db.set_current_coin(self.config.BRIDGE)
            else:
                self.logger.info("Couldn't sell, going back to scouting mode...")

    def initialize_current_coin(self):
        """
        Decide what is the current coin, and set it up in the DB.
        """
        if self.db.get_current_coin() is None:
            current_coin_symbol = self.config.CURRENT_COIN_SYMBOL
            if not current_coin_symbol:
                sys.exit("Yo. Set the current_coin_symbol.\n")

            self.logger.info(f"Setting initial coin to {current_coin_symbol}")

            if current_coin_symbol not in self.config.SUPPORTED_COIN_LIST:
                sys.exit("***\nERROR!\nSince there is no backup file, a proper coin name must be provided at init\n***")
            self.db.set_current_coin(current_coin_symbol)

            # if we don't have a configuration, we selected a coin at random... Buy it so we can start trading.
            if self.config.CURRENT_COIN_SYMBOL == "":
                current_coin = self.db.get_current_coin()
                self.logger.info(f"Purchasing {current_coin} to begin trading")
                all_tickers = self.manager.get_all_market_tickers()
                self.manager.buy_alt(current_coin, self.config.BRIDGE, all_tickers)
                self.logger.info("Ready to start trading")