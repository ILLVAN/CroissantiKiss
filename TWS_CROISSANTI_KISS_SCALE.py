# -*- coding: utf-8 -*-
"""
TWS DAX CROISSANTIKISS by ILLVAN

A Python DAX indicator and strategy working with the TWS API [ibapi], providing procyclic and anticyclic 
action in a scalable manner. 

Requieres running IB TWS or IB Gateway and valid IB Market Data Subscriptions to get Quotes.

todo:
    explain in readme
    make settings file
    make weights file
    make automated weight testing
    seasonality feature
    
BUGS:     
    - realtime wintodax repair during off hours  = -1  or leave it?
    - Traceback in app.disconnect
    -
"""
### IMPORTS ###
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.ticktype import TickTypeEnum
import threading
import time
import os
import sys
from datetime import date
from datetime import datetime
import json
import numpy as np
import random
import pandas as pd
pd.options.mode.chained_assignment = None   # default='warn'
import plotly
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.io as pio
pio.renderers.default = 'browser'

### SETTINGS ##  
date = str(date.today())                                     # get date from system
antipath = os.getcwd()+'\\'+'CROISSANTIKISS'                 # working path 
csvfilep = antipath+'\\'+date+'\\'+'CSV'+'\\'+date+'.csv'    # csv filepath 
wghtsfp = antipath+'\\'+date+'\\'+'WEIGHTS'+'\\'+date+'.json'# weights filepath
err = dict(                                                  # error directory 
    nodata = False)                                                    
sttngs = dict(                                               # settings directory  
    port = 7496,                                             # TWS: 7497 PAPER / 7496 REAL - GATEWAY: 4002 / 4001                                                
    freq = '4 hours',                                        # set time frequency for runs in frameselect
    perio = '4 Y',                                           # set time periods for runs in frameselect   
    get = True,                                              # set connection to server on / off
    getcur = True,                                          # set connection for realtime, requieres get
    manual = False,                                          # set to manual on / off hours
    manualprice = 14585,                                      # set manual price, requieres manual
    store = True,                                            # set storage
    test = True,                                             # set testing 
    plot = True,                                             # set plotting on / off, requieres testing                                                                                  
    scale = False,
    flagsize = 100,                                          # set size of signal for visualization 
    mincand = 3,                                             # set minimum candles to receive
    startcash = 15000,                                       # set startcash for testing    
    amount = 1,                                              # set amount of unleveraged contracts                                      
    cont = {'symbol':'IBDE40', 'type':'CFD', 
            'exchange':'SMART', 'currency':'EUR'},)          # set contract
oldwghts = dict(                                                # standard parameters / weights dir
    maxcb = 393,
    cbcomp = 1.618,
    cbfact = 0.33,
    maxmacd = 645,
    macdcomp = 0.7,
    mmaxperiod = 131,
    daxcoremaxperiod = 30,                                  
    macdfact = 2.0666,
    longfact = 2.22,                                         # set long factor
    attack = 30,
    crossattack = 450,
    bellsize = 113.12,
    histdivfact = np.sqrt(2),
    nettoflat = 3,
    trigema = 33)                                            # set EMA for signal triggers

newghts  = dict(
    maxcb = 402,
    cbcomp = 1.265,
    cbfact = 0.19,
    maxmacd = 654,
    macdcomp = 0.57,
    mmaxperiod = 141,
    daxcoremaxperiod = 28,                                  
    macdfact = 1.727,
    longfact = 2.31,                                         
    attack = 29,
    crossattack = 431,
    bellsize = 119.8,
    histdivfact = 1.2,
    nettoflat = 2,
    trigema = 30)   

fourwghts = dict(
    maxcb = 380,
    cbcomp = 1.618,
    cbfact = 0.7,
    maxmacd = 300,
    macdcomp = 1,
    mmaxperiod = 28,
    daxcoremaxperiod = 30,                                  
    macdfact = 2.0666,
    longfact = 2.179,                                         # set long factor
    attack = 30,
    crossattack = 499,
    bellsize = 113.12,
    histdivfact = np.sqrt(2),
    nettoflat = 3,
    trigema = 32)   

wghts = dict(   # nice bei neusten tests, mehr ertrag und fast kein drawdown, hohe trefferquote! -> neuer standard 
    maxcb = 380,
    cbcomp = 1.618,
    cbfact = 0.7,
    maxmacd = 300,
    macdcomp = 1,
    mmaxperiod = 27,
    daxcoremaxperiod = 30,                                  
    macdfact = 2.0666,
    longfact = 2.196,                                         # set long factor
    attack = 30,
    crossattack = 500,
    bellsize = 113.12,
    histdivfact = np.sqrt(2),
    nettoflat = 3,
    trigema = 32)    

# choose weights
#wghts = oldwghts

# STORAGE
def makedir():
    if sttngs['store'] is True and sttngs['scale'] is False:
        didnt = "Creation of directory %s failed / exists already"
        success = "Successfully created the directory %s "
        # working directory
        try:
            os.mkdir(antipath)
        except OSError:
            print (didnt % antipath)
        else:
            print (success % antipath)
        # date sub dir
        symbpath = antipath+'\\'+date                   
        try:
            os.mkdir(symbpath)
        except OSError:
            print (didnt % symbpath)
        else:
            print (success % symbpath)
        # csv sub sub dir 
        csvpath = antipath+'\\'+date+'\\'+'CSV' 
        try:
            os.mkdir(csvpath)
        except OSError:
            print (didnt % csvpath)
        else:
            print (success % csvpath)
        # chart sub sub dir   
        if sttngs['plot'] is True:
            chartdir = antipath+'\\'+date+'\\'+'CHARTS'
            try:
                os.mkdir(chartdir)
            except OSError:
                print (didnt % chartdir)
            else:
                print (success % chartdir)
        # weights sub sub dir   
        wghtsdir = antipath+'\\'+date+'\\'+'WEIGHTS'
        try:
            os.mkdir(wghtsdir)
        except OSError:
            print (didnt % wghtsdir)
        else:
            print (success % wghtsdir)
        with open(wghtsfp, 'w') as fhandout:
            json.dump(wghts, fhandout, indent=4)

# CONNECT & GET DATA
def congetdisco():   
    class HistoApp(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.data = [] #Initialize variable to store candle
        
        # def error(self, reqId, errorCode, errorString):
        #     pass
        #     # print("Error: ", reqId, " ", errorCode, " ", errorString)

        def historicalData(self, reqId, bar):
            # print(f'Time: {bar.date} Open: {bar.open} Close: {bar.close} High: {bar.high} Low: {bar.low}')
            self.data.append([bar.date, bar.open, bar.close, bar.high, bar.low])
    
    class TickerApp(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.data = []
    
        def tickPrice(self, reqId, tickType, price, attrib):
            readtype = TickTypeEnum.to_str(tickType)
            print('READTYPE:"',readtype,'"')
            print("Tick Price. Ticker Id:", reqId, "tickType:", readtype, "Price:", price, end=' ')
            if readtype in ['BID','ASK']:    # filter for BID & ASK prizes, eliminates precloses
                self.data.append([price])
            
        def tickSize(self, reqId, tickType, size):
            print("Tick Size. Ticker Id:", reqId, "tickType:", TickTypeEnum.to_str(tickType), "Size:", size)     

    def run_loop():
        app.run()
    
    def run_loop2():
        app2.run()  
        
    # connect
    app = HistoApp()
    app.connect('127.0.0.1', sttngs['port'], 123) 
    app2 = TickerApp()
    app2.connect("127.0.0.1", sttngs['port'], 222) 
    
    #Start the sockets in threads
    t1 = threading.Thread(target=run_loop, daemon=True)
    t1.start()
    time.sleep(2)
    if sttngs['getcur'] is True:
        t2 = threading.Thread(target=run_loop2)
        t2.start()
    time.sleep(2) #Sleep interval to allow time for connections to server
    # Create contract object
    x_contract = Contract()
    x_contract.symbol = sttngs['cont']['symbol']
    x_contract.secType = sttngs['cont']['type']
    x_contract.exchange = sttngs['cont']['exchange']
    x_contract.currency = sttngs['cont']['currency']
    #Request historical candles
    freq = sttngs['freq']
    perio = sttngs['perio']
    app.reqHistoricalData(1, x_contract, '', perio, freq, 'BID', 1, 2, False, [])
    
    #Request current tick quotes and store as lastprice while historical data is loading
    if sttngs['getcur'] is True:
        app2.reqMarketDataType(4)  # argument is data type: 1 live, 2 frozen, 3 delayed, 4 delayed frozen
        app2.reqMktData(777, x_contract, "", False, False, [])
        time.sleep(7) #sleep to allow enough time for historical data to be returned and to get some ticks
        app2.cancelMktData(777)
        dfcur = pd.DataFrame(app2.data, columns=['Price'])
        app2.disconnect() ##### raises WinError - to check, needed for clean relogin.
        print(dfcur)
        lastprice = dfcur['Price'].mean()
        
    # option for manual inputting the last price in off hours
    if sttngs['manual'] is True:
        lastprice = sttngs['manualprice']
        
    if sttngs['getcur'] is False:
        time.sleep(5) # time for historical data to return
           
    # put historical data in pandas DataFrame, create and append last bar from current price, store df in csv for checks and disconnect
    df = pd.DataFrame(app.data, columns=['DateTime','Open', 'Close', 'High', 'Low'])
    app.disconnect() ##### raises WinError - to check, needed for clean relogin.
    df.set_index('DateTime', drop=True, inplace=True)
    if sttngs['getcur'] is True or sttngs['manual'] is True:
        ts = pd.Timestamp(datetime.now())
        print('### LAST PRICE: ',lastprice,' TIMESTAMP: ',ts,' ###')
        nowsec = int(float(str(ts.timestamp()).replace(',', '.'))) # produce seconds timestamp, remove base 10 spelling
        lastbar = pd.DataFrame([[nowsec, lastprice, lastprice, lastprice, lastprice]], columns=['DateTime', 'Open', 'Close', 'High', 'Low'])
        lastbar.set_index('DateTime', drop=True, inplace=True)
        print(lastbar)
        print('### LEN DF ###', len(df), df)
        df = df.append(lastbar)
    err['nodata'] = False
    if len(df.index) < 2:       # nodata error in case there is no data received
        print('===== couldnt get data ====')
        err['nodata'] = True 
    df.to_csv(csvfilep)
    print('### LEN DF ###', len(df))
    return df


# CALCULATE
def calcthis(df, wghts):
    # print('calculating')
    # print('▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲ WAIT ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲')
    dfcalc = df
    dfcalc.reset_index(level='DateTime', inplace=True)
    # print('DFCALC new index', dfcalc)
    # variables 
    maxcb = wghts['maxcb']
    cbcomp = wghts['cbcomp']
    cbfact = wghts['cbfact']
    maxmacd = wghts['maxmacd']
    macdcomp = wghts['macdcomp']
    mmaxperiod = wghts['mmaxperiod']
    daxcoremaxperiod = wghts['daxcoremaxperiod']
    macdfact = wghts['macdfact']
    longfact = wghts['longfact']
    attack = wghts['attack']
    crossattack = wghts['crossattack']
    bellsize = wghts['bellsize']
    histdivfact = wghts['histdivfact']
    nettoflat = wghts['nettoflat']
    trigema = wghts['trigema']
    err['startpoint'] = dfcalc['Close'][0]
    # calc
    exp1 = dfcalc.Close.ewm(span=12, adjust=False).mean()
    exp2 = dfcalc.Close.ewm(span=26, adjust=False).mean()   
    dfcalc['MACD'] = (exp1 - exp2) * macdfact
    dfcalc['MACDema9'] = dfcalc['MACD'].ewm(span=9, adjust=False).mean() 
    dfcalc['Macdmax'] = abs(dfcalc['MACD']).rolling(window=mmaxperiod).max()
    hist = dfcalc['MACD'] - dfcalc['MACDema9']
    histema1 = hist.ewm(span=2, adjust=False).mean()
    histema3 = hist.ewm(span=3, adjust=False).mean()        
    dfcalc['histdiv'] = (histema1 - histema3) * histdivfact
    dfcalc['Pro'] = dfcalc['MACD'] + dfcalc['histdiv'] 
    cpro = []
    for macd in dfcalc['Pro']:
        if macd > maxmacd:
            macd = maxmacd + ((macd - maxmacd) / macdcomp)
        if macd < -1 * maxmacd:
            macd = -1 * maxmacd - ((macd + maxmacd) / macdcomp)
        cpro.append(macd)
    dfcalc['Pro'] = cpro
    dfcalc['Sign'] = np.sign(dfcalc['MACD'])
    dfcalc['Cross'] = dfcalc['histdiv'] - dfcalc['Sign'].ewm(span=3, adjust=False).mean()
    dfcalc['Bell'] = bellsize * -1 * dfcalc['Sign'].ewm(span=attack, adjust=False).mean()
    dfcalc['Crossbuy'] = (4 * dfcalc['Bell']) + cbfact * dfcalc['Macdmax'] * dfcalc['Cross'].ewm(span=crossattack, adjust=False).mean()
    ccrossb = []
    for cb in dfcalc['Crossbuy']:
        if cb > maxcb:
            cb = maxcb + (cb - maxcb) / cbcomp
        if cb < - maxcb:
            cb = (-1*maxcb) + ((cb + maxcb) / cbcomp)
        ccrossb.append(cb)
    dfcalc['Crossbuy'] = ccrossb  
    dfcalc['Netto'] = dfcalc['Crossbuy'] + dfcalc['Pro'] # + dfcalc['Bell'] 
    dfcalc['Nettoflat'] = (dfcalc['Netto'].ewm(nettoflat, adjust=False)).mean()
    dfcalc['Daxcorefast'] = (4 * dfcalc['Nettoflat']) + (12 * (dfcalc['Netto'] - dfcalc['Nettoflat']).ewm(span=3, adjust=False).mean())
    dfcalc['Daxcoreflat'] = (4 * dfcalc['Nettoflat']) + (12 * (dfcalc['Netto'] - dfcalc['Nettoflat']).rolling(3).mean()).rolling(4).mean()
    dfcalc['Daxcorepre'] = 1.8 * ((dfcalc['Daxcorefast'] - dfcalc['Daxcoreflat']).rolling(4).mean())
    dfcalc['Daxcorpremax'] = (dfcalc['Daxcorepre']).rolling(window=daxcoremaxperiod).max()
    dfcalc['Daxcorpremin'] = (dfcalc['Daxcorepre'] / longfact).rolling(window=daxcoremaxperiod).min()
    # print(dfcalc['Daxcorpremin'])
    dfcalc['Daxcormax'] = dfcalc['Daxcorpremax'] + dfcalc['Daxcorpremin']
    # print(dfcalc['Daxcormax'])
    dfcalc['Daxcore'] = (dfcalc['Close'] + dfcalc['Daxcorepre']).rolling(3).mean() + dfcalc['Daxcormax'] # conversion to get it on level
    dfcalc['SMA200'] = (dfcalc['Close']).rolling(window=200).mean() 
    dfcalc['SMA3'] = (dfcalc['Close']).rolling(window=3).mean()
    emaname = 'EMA'+str(trigema)
    err['emaname'] = emaname
    dfcalc[emaname] = dfcalc['Close'].ewm(span=trigema, adjust=False).mean()
    dfcalc['Daxcorevis'] = dfcalc['Daxcore'] + (dfcalc['SMA3'] - dfcalc[emaname])
    dfcalc['Flag'] = (dfcalc['Daxcore'] - dfcalc[emaname]).ewm(span=3, adjust=False).mean() 
    dfcalc['Flag'].mask(dfcalc['Flag'] >= 0, sttngs['flagsize'], inplace= True)
    dfcalc['Flag'].mask(dfcalc['Flag'] < 0, -sttngs['flagsize'], inplace= True)
        
    return dfcalc

#QUICK TEST
def testthis(dfcalc, wghts):
    
    dftested = dfcalc
    dftested['Preflag'] = dftested['Flag'].shift(1)
    dftested['Signal'] = ((dftested["Preflag"] + (2*dftested["Flag"])) / 100)
    dftrades = dftested.loc[abs(dftested['Signal']) == (sttngs['flagsize'] / 100)]
    dftrades['Buy'] = dftrades['Close'] * sttngs['amount'] * dftested['Signal'] 
    cashbefore = sttngs['startcash']  
    dftrades['Dif'] = dftrades['Close'] - dftrades['Close'].shift(1)
    dftrades['Winloss'] = dftrades['Signal'].shift(1) * dftrades['Dif'] * sttngs['amount']
    dftrades['Cumuwinloss'] = dftrades['Winloss'].cumsum()
    dftrades['TOTAL'] = cashbefore + dftrades['Cumuwinloss']
    # print trade df for checks, including or exluding Columns ad lib only 8 at a time, excluding makes things easier.
    # dftradescheck = dftrades.drop(columns=['Sign','Cross','Bell','Crossbuy','Netto', 'Pro', 'Macdmax'])
    # dftradescheck = dftradescheck.drop(columns=['MACD','MACDema9','histdiv','Flag','Nettoflat','SMA200', 'SMA3', 'Daxcore'])
    # dftradescheck = dftradescheck.drop(columns=['Daxcorefast','Daxcorpremin','Daxcorpremax','Daxcorepre', 'Preflag'])
    # print(dftradescheck.to_string())

    start = 0
    checknan = np.isnan(float(dfcalc.head(1)['Close'].values[0]))
    if len(dfcalc) > 1 and  checknan == False:
        start = int(dfcalc.head(1)['Close'].values[0])
        # print('START: ',start)
    dftrades['wintostart'] = start + dftrades['Cumuwinloss']    
    if sttngs['scale'] is False:
        print(dftrades)
    
    return [dftested,dftrades]
  
# PLOT TO HTML
def plotthis(dftested,dftrades):
    dfplot = dftested
    dfplot['Zero'] = 0
    dftrades.set_index('DateTime', inplace=True)
    dfplot.set_index('DateTime', inplace=True)
    dftrades.index = pd.to_datetime(dftrades.index, unit='s')
    dfplot.index = pd.to_datetime(dfplot.index, unit='s')
    # create candlestick chart with annotations with plotly 
    fig = make_subplots(rows=2, cols=1, row_heights=[0.4,0.6], shared_xaxes=True,
                                        vertical_spacing = 0.05)
    fig.add_trace(go.Scatter(name='BELL',x=dfplot.index, y=dfplot['Bell'], 
                                        line=dict(color='dimgrey', width=1)),
                                        row=1, col=1)

    fig.add_trace(go.Scatter(name='PRO', x=dfplot.index, y=dfplot['Pro'], 
                                        line=dict(color='darkturquoise', width=1),
                                        fill='tonexty',
                                        fillcolor = 'rgba(160,207,245,0.6)'),
                                        row=1, col=1)
    fig.add_trace(go.Scatter(name='ANTI',x=dfplot.index, y=dfplot['Crossbuy'],
                                        line=dict(color='purple', width=0.8), 
                                        fill='tonexty',
                                        fillcolor = 'rgba(77,255,255,0.1)'),
                                        row=1, col=1)
    fig.add_trace(go.Scatter(name='NULL',x=dfplot.index, y=dfplot['Zero'], 
                                        line=dict(color='black', width=1.5)),
                                        row=1, col=1)
    fig.add_trace(go.Scatter(name=('NETTO'),x=dfplot.index, y=dfplot['Nettoflat'], 
                                        line=dict(color='darkblue', width=0.1),
                                        fill='tonexty',
                                        fillcolor = 'rgba(114,5,186,0.2)'),
                                        row=1, col=1)
    fig.add_trace(go.Scatter(name='FLAG',x=dfplot.index, y=dfplot['Flag'], 
                                        line=dict(color='darkmagenta', dash='dashdot', width=1)),
                                        row=1, col=1)
    # fig.add_trace(go.Scatter(name='SHORT',x=dfplot.index, y=dfplot['Short'], 
    #                                     line=dict(color='darkred', width=1.5)),
    #                                     row=1, col=1)
    fig.add_trace(go.Scatter(name='WIN2DAX',x=dftrades.index, y=dftrades['wintostart'], 
                                        line=dict(color='rgba(40,80,240,0.3)', width=1)),
                                        row=2, col=1)
    # fig.add_trace(go.Scatter(name='TOTAL',x=dftrades.index, y=dftrades['TOTAL'], 
    #                                     line=dict(color='rgba(80,40,240,0.2)', width=2)),
    #                                     row=2, col=1)
    fig.add_trace(go.Candlestick(name='BARS',x=dfplot.index,
                                        open=dfplot['Open'],
                                        high=dfplot['High'],
                                        low=dfplot['Low'],
                                        close=dfplot['Close'],
                                        increasing_line_color= 'darkseagreen', 
                                        decreasing_line_color= 'tomato'),
                                        row=2, col=1)
    fig.add_trace(go.Scatter(name='SMA200',x=dfplot.index, y=dfplot['SMA200'], 
                                        line=dict(color='darkgreen', width=1)),
                                        row=2, col=1)
    fig.add_trace(go.Scatter(name='SMA3',x=dfplot.index, y=dfplot['SMA3'], 
                                        line=dict(color='rgba(40,120,210,0.3)', width=1)),
                                        row=2, col=1)
    fig.add_trace(go.Scatter(name=err['emaname'],x=dfplot.index, y=dfplot[err['emaname']], 
                                        line=dict(color='rgba(70,113,240,0.9)', width=1)),
                                        row=2, col=1)
    fig.add_trace(go.Scatter(name='DAXCORE',x=dfplot.index, y=dfplot['Daxcore'], 
                                        line=dict(color='rgba(30,40,210,0.2)', width=0.5),
                                        fill='tonexty',
                                        fillcolor = 'rgba(30,40,210,0.1)'),
                                        row=2, col=1)
    fig.add_trace(go.Scatter(name='DXC OFFSET',x=dfplot.index, y=dfplot['Daxcorevis'], 
                                        line=dict(color='rgba(0,140,240,0.2)', width=0.5),
                                        fill='tonexty',
                                        fillcolor = 'rgba(0,140,240,0.3)'),
                                        row=2, col=1)
    tit = 'DAX CROISSANTIKISS '+sttngs['freq']+', '+sttngs['perio']
    fig.update_layout(
         legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1),
        title={'text': tit,'y':0.95,'x':0.02,'xanchor': 'left','yanchor': 'top'},
        uniformtext_minsize=8, uniformtext_mode='hide',
        xaxis1=dict(type = 'category'),
        xaxis2=dict(type = 'category'),
        yaxis1_title='Indication',
        yaxis2_title='Price',
        xaxis1_rangeslider_visible=False,
        xaxis2_rangeslider_visible=True)
    fig.update_xaxes(tickangle=45, tickfont=dict(family='Rockwell', color='black', size=9))
    chartdir = antipath+'\\'+date+'\\'+'CHARTS'
    chartfilep = chartdir+'\\'+date+'.html'
    plotly.offline.plot(fig, filename=chartfilep)
    print('▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲ DONE ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲')
    print('❋✦✪✬௷ ༓ ࿌℥ ࿄ ࿂᧟ ℺ ↗ ⍑ ⽩↘ ↟ ↡ ↭ ႞ ⇗ ⇘ ⌘  ╗  ╝⌛ ⌬ ⌶ ⍐ ⍝ ⏫ ⏬ ⏹ ☁ ▚ ▞ ⽢⏆ ⍭ ▤ ▩ ◯ ⌖ ⍢ ☃ ◉ ֎ ۞ ༜ ⏀ ௴  ୰ ✺')
    return dfplot

# # # # # # # # # # # # # #  DEF RUN  # # # # # # # # # # # # # #
def runall(wghts):
    makedir()
    if sttngs['get'] is True:
        while True:
            df = congetdisco()
            if len(df) > sttngs['mincand']: 
                break
            else:
                time.sleep(3)
                continue
    else:
        try:
            df = pd.read_csv(csvfilep)
            df.set_index('DateTime', drop=True, inplace=True)
            # print(df)
        except:
            print('could not find csv, please get DATA')
            sys.exit()
    if len(df.index) < 2:       # nodata error in case there is no data received
            print('===== couldnt get data ====')
            err['nodata'] = True 
    if err['nodata'] != True:
        dfcalc = calcthis(df, wghts)
        if sttngs['test'] is True:
            both = testthis(dfcalc, wghts)
            dftested = both[0]
            dftrades = both[1]
            checkratnan = False
            checkratnan = np.isnan(float(dftrades.tail(1)['wintostart'].values[0]))
            # print(checkratnan)
            rating = None
            if checkratnan == False:
                rating = int(dftrades.tail(1)['wintostart'].values[0])
                if rating > 26900:
                    threadname = threading.get_ident() 
                    print('RATING: ', rating, 'THREAD: ', threadname)
                if rating > 28900:
                    print('################ VERY NICE WEIGHTS ################')
                    print(wghts)
                    err['rating'] = (rating, wghts)
                    wghtsname = wghtsfp.split('.')[0] + '_' + str(rating) + '_' + sttngs['perio'] + '.json'
                    with open(wghtsname, 'w') as fhandout:
                        json.dump(wghts, fhandout, indent=4)
                    dfplot = plotthis(dftested,dftrades)
                    print('plotted1')
                    sttngs['plot'] = False
            if sttngs['plot'] is True and sttngs['scale'] is False:
                dfplot = plotthis(dftested,dftrades)
                print('plotted2')
            
# # # # # # # # # # # #  SCALING LOOP # # # # # # # # # # # #
def scalethis():
    def calcloop():
        while True:
            # time.sleep(0.1)
            # overwrite parameters dir with random numbers in preset ranges
            wghts = dict(
                maxcb = random.uniform(370,410),
                cbcomp = random.uniform(0.95,2.2),
                cbfact = random.uniform(0.2,1.1),
                maxmacd = random.uniform(600,700),
                macdcomp = random.uniform(0.5,1.1),
                mmaxperiod = random.randint(122,142),
                daxcoremaxperiod = random.randint(23,37),                                  
                macdfact  = random.uniform(1.5,3.2),
                longfact  = random.uniform(0.95,3.2),                                         
                attack  = random.randint(23,37),
                crossattack = random.randint(430,470),
                bellsize = random.uniform(105,125),
                histdivfact = random.uniform(1.2,1.6),
                nettoflat = random.randint(2,4),
                trigema = random.randint(25,41))                                            
            runall(wghts)
        
    if sttngs['scale'] is True:
        sttngs['get'] = False
        scale1 = threading.Thread(target=calcloop, daemon=True)
        scale2 = threading.Thread(target=calcloop, daemon=True)
        scale3 = threading.Thread(target=calcloop, daemon=True)
        scale4 = threading.Thread(target=calcloop, daemon=True)
        scale5 = threading.Thread(target=calcloop, daemon=True)
        scale6 = threading.Thread(target=calcloop, daemon=True)
        scale7 = threading.Thread(target=calcloop, daemon=True)
        scale1.start()
        time.sleep(1)
        scale2.start()
        time.sleep(1)
        scale3.start()
        time.sleep(1)
        scale4.start()
        time.sleep(1)
        scale5.start()
        time.sleep(1)
        scale6.start()
        time.sleep(1)
        scale7.start()
        time.sleep(2000)
        # sys.exit()
    else:
        runall(wghts)

# # # # # # # # # # # # # #  RUN  # # # # # # # # # # # # # #
# # # # # # # # # # # # WITH SCALING  # # # # # # # # # # # #
scalethis()