from datetime import datetime, timedelta
import time
import os
import re
from dotenv import load_dotenv
import numpy as np

from apscheduler.schedulers.background import BackgroundScheduler
import urllib.request

from alpaca.trading.client import TradingClient
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# make sure you write down your API Key in a .env file
load_dotenv(dotenv_path="./.env_paper")
key_id = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

url = "http://51.81.209.49:54321/forecast_raw/"

trading_client = TradingClient(key_id, secret_key, paper=True)
account = trading_client.get_account()

order_size = {"spy": 4.0, "qqq": 4.5, 'vti': 8.0, 'xlf': 45, 'xle': 20}
past_orders = {}
def decide(ticker):
    with urllib.request.urlopen(url + ticker) as response:
        html = response.read()
    # data = re.sub('[^\d\.\- ]', '', str(html)).lstrip().rstrip()
    # data = re.sub(' +', ' ', data).split(' ')
    # print(data)
    data = json.loads(html.decode().replace('"', ''))
    hour_1_data = data[2]
    if html in [t['responses'] for t in past_orders.get(ticker, [])]:
        return -1  # something is wrong
    else:
        if hour_1_data >= 1:
            return 0.2, html
        elif hour_1_data >= 0.00:
            return 0.1, html
        else:
            return 0, html
    
# to do
# automatically sell after 1 hour
# be able to compute portfolio size
# alternative - just buy/sell a fixed size, won't change too much

def tick(ticker):
    clock = trading_client.get_clock()
    print('Tick! The time is: %s' % datetime.now(), "we are trading", ticker)
    if not clock.is_open:  # not open
        print("market is not open - do nothing")
        return
    print("Check if we have pending orders to sell")
    past_buys = past_orders.get(ticker, [])
    now = datetime.now()
    sold_something = False
    for i, p in enumerate(past_buys):
        if p['time'] + timedelta(minutes = 14, seconds = 30) <= now:  # should be minutes = 59
            market_order_data = MarketOrderRequest(
                            symbol=ticker.upper(),
                            qty=p['size'],
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.DAY
                            )

            market_order = trading_client.submit_order(
                            order_data=market_order_data
                           )
            past_orders[ticker].pop(i)
            print(f"Sold {ticker} of size {p['size']}.")
            sold_something = True
    if sold_something:
        print("We sold stuff, exit this loop")
        return
    # check if we reached our buying power
    # we need two sizes. Sizes (1/2), and number of shares. They need to be different.
    total_size = np.sum(np.array([p['size'] for p in past_buys]))
    if total_size >= 10:
        print(f"We have reached our buying power for ticker {ticker}, doing nothing this run.")
        return
    
    
    print("Getting data")
    result, response_html = decide(ticker)
    
    if response_html in [t['html'] for t in past_orders.get(ticker, [])]:
        print("redundant run, exit")
        return
    
    if result < 0.001:
        print(f"not buying, api call was {response_html}")
        return
    else: # we are buying
        if result >= 0.2:
            size = 2 * order_size[ticker]
        elif result >= 0.1:
            size = 1 * order_size[ticker]
        else:
            raise
        # make the purchase
        try:
            market_order_data = MarketOrderRequest(
                            symbol=ticker.upper(),
                            qty=size,
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.DAY
                            )

            market_order = trading_client.submit_order(
                            order_data=market_order_data
                           )
            # log the order
            this_order = {"time":  datetime.now(), "size": size, "html": response_html}
            print(this_order)
            if past_orders.get(ticker) is None:
                past_orders[ticker] = [this_order]
            else:
                past_orders[ticker].append(this_order)
        except:
            raise # do nothing for now.

                
        

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(tick, 'cron', second = 30, minute = "0/5", replace_existing=True, args = ['spy'])
    scheduler.add_job(tick, 'cron', second = 30, minute = "1/5", replace_existing=True, args = ['qqq'])
    #scheduler.add_job(tick, 'cron', second = 30, minute = "2/5", replace_existing=True, args = ['xlf'])
    #scheduler.add_job(tick, 'cron', second = 30, minute = "3/5", replace_existing=True, args = ['xle'])
    #scheduler.add_job(tick, 'cron', second = 30, minute = "4/5", replace_existing=True, args = ['vti'])
    
    scheduler.start()
    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        # This is here to simulate application activity (which keeps the main thread alive).
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        scheduler.shutdown()
