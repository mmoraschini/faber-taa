# faber-taa
See results of the Meb Faber Tactical Asset Allocation (TAA) strategy on whatever ticker available on Yahoo!® Finance.

[yfinance](https://github.com/ranaroussi/yfinance) is used to query Yahoo!® Finance APIs.

Run it from here without the need to install anything: https://share.streamlit.io/mmoraschini/faber-taa/main

# Disclaimer #1
See https://github.com/ranaroussi/yfinance:

Yahoo!, Y!Finance, and Yahoo! finance are registered trademarks of Yahoo, Inc.

You should refer to Yahoo!'s terms of use ([here](https://policies.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.htm), [here](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), and [here](https://policies.yahoo.com/us/en/yahoo/terms/index.htm)) for details on your rights to use the actual data downloaded. Remember - the Yahoo! finance API is intended for personal use only.

# Disclaimer #2
The information obtained from this script is for instructional purposes only and should be verified before using it in any financial strategy. I am not a financial advisor and this project is not meant to give financial advices. Please, contact a registered financial advisor if you are interested in investing your money.

# Description
In his 2006 reserch paper Mebane Faber describes a simple investment strategy, based on the comparison of the current price level and the 10 months simple moving average (SMA) to decide whether to be invested in a given financial instrument or not. At the end of each month, one invests in the financial instrument of their choice if its closing price is above the 10 months (SMA) and disinvests if it drops below.

For more information refer to [Extrategic Dashboard](https://extradash.com/en/strategies/models/5/faber-tactical-asset-allocation/) that contains a detailed description of the strategy.

You can either clone the repo and launch the streamlit app or access it from https://share.streamlit.io/mmoraschini/faber-taa/main.

# ToDo
* Add trading costs
* Calculate comparison statistics
