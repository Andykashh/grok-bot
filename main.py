import os
import time
import urllib.request
import json
import asyncio

import discord
from discord import app_commands
from discord.ext import tasks

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# GROK BOT | BTC Rapid Market Movement Alerts

BTC_MOVEMENT_CHECK_SECONDS = 60

# Alert when BTC moves 1% or more within 5 minutes
BTC_MOVEMENT_THRESHOLD = 0.01
BTC_MOVEMENT_WINDOW_SECONDS = 300

# Volume spike detection: 2x normal volume
BTC_VOLUME_SPIKE_MULTIPLIER = 2.0

# Prevent repeated alerts for the same event
BTC_MOVEMENT_ALERT_COOLDOWN = 300

# Track previously sent alerts
btc_movement_alert_state = {
    "last_up_alert": None,
    "last_down_alert": None,
    "last_volume_alert": None
}

intents = discord.Intents.default()


def get_btc_price():
    url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GrokBot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read())

    return float(data["data"]["amount"])


# GROK BOT | Detect Rapid BTC Price Movements


# GROK BOT | Detect Rapid BTC Price Movements

def detect_btc_movement(candles):
    if not candles or len(candles) < 6:
        return None

    candles = sorted(
        candles,
        key=lambda c: c["time"]
    )

    # Use completed 1-minute candles
    completed = candles[:-1]

    if len(completed) < 6:
        return None

    latest = completed[-1]
    previous = completed[-6]

    # Ensure the candles are 5 minutes apart
    if latest["time"] - previous["time"] != 300:
        return None

    old_price = float(previous["close"])
    new_price = float(latest["close"])

    if old_price <= 0:
        return None

    change_percent = (
        (new_price - old_price) / old_price
    ) * 100

    if change_percent >= BTC_MOVEMENT_THRESHOLD * 100:
        direction = "UP"
    elif change_percent <= -BTC_MOVEMENT_THRESHOLD * 100:
        direction = "DOWN"
    else:
        return None

    return {
        "direction": direction,
        "change_percent": round(change_percent, 2),
        "old_price": old_price,
        "new_price": new_price
    }


# GROK BOT | BTC Volume Spike Detection

def detect_btc_volume_spike(candles):
    """
    Compare the latest completed candle's volume
    against the previous 20 completed candles.
    """

    if not candles or len(candles) < 22:
        return None

    
    # Coinbase candles are dictionaries
    candles = sorted(candles, key=lambda c: c["time"])

    # Exclude the newest potentially incomplete candle
    completed = candles[:-1]

    latest = completed[-1]
    previous = completed[-21:-1]

    latest_volume = float(latest["volume"])

    average_volume = sum(
        float(candle["volume"]) for candle in previous
    ) / len(previous)


    if average_volume <= 0:
        return None

    volume_ratio = latest_volume / average_volume

    if volume_ratio >= BTC_VOLUME_SPIKE_MULTIPLIER:
        status = "SPIKE"
    else:
        status = "NORMAL"

    return {
        "status": status,
        "volume_ratio": round(volume_ratio, 2),
        "latest_volume": latest_volume,
        "average_volume": round(average_volume, 4),
        "is_spike": status == "SPIKE"
    }

class GrokBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.started_at = time.time()

    
    async def setup_hook(self):
        print("GROK BOT: Registering slash commands...")

        synced = await self.tree.sync()

        print("GROK BOT: Command synchronization complete.")
        print(f"Registered {len(synced)} slash commands.")


        if not kalshi_live_monitor.is_running():
            kalshi_live_monitor.start()
            print("GROK BOT: Live Kalshi monitoring activated.")
bot = GrokBot()

@bot.tree.command(
    name="btc",
    description="Get the latest Bitcoin spot price"
)
async def btc(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        price = await asyncio.to_thread(get_btc_price)

        embed = discord.Embed(
            title="GROK BOT | BTC MONITOR",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Bitcoin Spot Price",
            value=f"${price:,.2f}",
            inline=False
        )

        embed.set_footer(text="Informational data only")

        await interaction.followup.send(embed=embed)

    except Exception as error:
        print(f"BTC command error: {error}")
        await interaction.followup.send(
            f"Unable to retrieve BTC data: {error}"
        )


@bot.tree.command(
    name="btcanalysis",
    description="Get full Bitcoin technical analysis"
)
async def btcanalysis(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        # Fetch Bitcoin price and candle data
        price, candles5, candles15 = await asyncio.gather(
            asyncio.to_thread(get_btc_price),
            asyncio.to_thread(get_btc_candles, 300, 100),
            asyncio.to_thread(get_btc_candles, 900, 100)
        )

        # Analyze both timeframes
        analysis5 = analyze_timeframe(candles5)
        analysis15 = analyze_timeframe(candles15)

        
        # Analyze trading volume on both timeframes
        volume5 = analyze_volume(candles5)
        volume15 = analyze_volume(candles15)


        # Multi-timeframe confirmation
        confirmation = confirm_timeframes(
            analysis5,
            analysis15
        )

        market = confirmation["market"]
        color = confirmation["color"]

        # Generate trading signal
        trade = generate_trade_signal(
            candles5,
            analysis5,
            analysis15,
            volume5,
            volume15
        )

        # Detect reversals
        reversal5 = detect_reversal(candles5)
        reversal15 = detect_reversal(candles15)

        reversal = classify_reversal(
            reversal15,
            reversal5,
            analysis15["trend"]
        )

        # Create market analysis embed
        embed = discord.Embed(
            title="GROK BOT | BTC MARKET ANALYSIS",
            description=(
                f"BTC Spot Price: **${price:,.2f}**\n"
                f"Overall Direction: **{market}**"
            ),
            color=color
        )

        # 5-minute analysis
        embed.add_field(
            name="5-Minute Analysis",
            value=(
                f"Trend: **{analysis5['trend']}**\n"
                f"EMA20: ${analysis5['ema20']:,.2f}\n"
                f"EMA50: ${analysis5['ema50']:,.2f}\n"
                f"RSI: {analysis5['rsi']:.2f}"
            ),
            inline=True
        )

        # 15-minute analysis
        embed.add_field(
            name="15-Minute Analysis",
            value=(
                f"Trend: **{analysis15['trend']}**\n"
                f"EMA20: ${analysis15['ema20']:,.2f}\n"
                f"EMA50: ${analysis15['ema50']:,.2f}\n"
                f"RSI: {analysis15['rsi']:.2f}"
            ),
            inline=True
        )

        # Trading volume analysis
        embed.add_field(
            name="Trading Volume Analysis",
            value=(
                "**5-Minute Volume**\n"
                f"Activity: {volume5['volume_activity']}\n"
                f"Strength: {volume5['strength']}\n"
                f"Volume Ratio: {volume5['volume_ratio']:.2f}x\n"
                f"Change: {volume5['volume_change']:+.2f}%\n"
                f"Pressure: {volume5['pressure']}\n"
                f"Signal: **{volume5['volume_signal']}**\n\n"
                "**15-Minute Volume**\n"
                f"Activity: {volume15['volume_activity']}\n"
                f"Strength: {volume15['strength']}\n"
                f"Volume Ratio: {volume15['volume_ratio']:.2f}x\n"
                f"Change: {volume15['volume_change']:+.2f}%\n"
                f"Pressure: {volume15['pressure']}\n"
                f"Signal: **{volume15['volume_signal']}**"
            ),
            inline=False
        )

        # Multi-timeframe confirmation
        embed.add_field(
            name="Multi-Timeframe Confirmation",
            value=(
                f"Alignment: **{confirmation['alignment']}**\n"
                f"Momentum: **{confirmation['momentum']}**\n"
                f"Assessment: **{confirmation['confirmation']}**"
            ),
            inline=False
        )

        # Reversal analysis
        embed.add_field(
            name="Reversal Analysis",
            value=f"**{reversal}**",
            inline=False
        )

        # Detected signals
        signals = (
            [f"5M: {s}" for s in reversal5["signals"]
             if s != "Insufficient data"]
            +
            [f"15M: {s}" for s in reversal15["signals"]
             if s != "Insufficient data"]
        )

        embed.add_field(
            name="Detected Signals",
            value=(
                "\n".join(dict.fromkeys(signals))
                if signals
                else "No significant signals detected."
            ),
            inline=False
        )

        # Trading signal system
        if trade["signal"] == "WAIT":
            trade_text = (
                "**SIGNAL: WAIT**\n"
                f"Confidence Score: {trade['confidence']}%\n"
                "No qualifying trading setup detected."
            )

        else:
            trade_text = (
                f"**SIGNAL: {trade['signal']}**\n"
                f"Confidence Score: {trade['confidence']}%\n"
                f"Entry: ${trade['entry']:,.2f}\n"
                f"Stop Loss: ${trade['stop_loss']:,.2f}\n"
                f"Take Profit 1: ${trade['take_profit_1']:,.2f}\n"
                f"Take Profit 2: ${trade['take_profit_2']:,.2f}"
            )

        embed.add_field(
            name="GROK BOT | TRADING SIGNAL",
            value=trade_text,
            inline=False
        )

        embed.set_footer(
            text="GROK BOT | Technical Analysis | Informational Only"
        )

        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)

    
    except Exception as error:
        print(f"BTC analysis error: {error!r}")
        await interaction.followup.send(
            f"Unable to complete BTC analysis: {error}"
        )


@bot.tree.command(name="status", description="Check GROK BOT status")
async def status(interaction: discord.Interaction):
    uptime = int(time.time() - bot.started_at)

    await interaction.response.send_message(
        f"GROK BOT is online!\nUptime: {uptime // 60} minutes."
    )


def get_kalshi_markets():
    url = (
        "https://external-api.kalshi.com/"
        "trade-api/v2/markets"
        "?series_ticker=KXBTC15M&status=open&limit=5"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GrokBot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read())

    return data.get("markets", [])


def kalshi_price(market, side, price_type):
    dollars_key = f"{side}_{price_type}_dollars"
    cents_key = f"{side}_{price_type}"

    if market.get(dollars_key) is not None:
        return float(market[dollars_key])

    if market.get(cents_key) is not None:
        return float(market[cents_key]) / 100

    return None
def get_kalshi_quotes(market):
    return {
        "up_buy": kalshi_price(market, "yes", "ask"),
        "up_sell": kalshi_price(market, "yes", "bid"),
        "down_buy": kalshi_price(market, "no", "ask"),
        "down_sell": kalshi_price(market, "no", "bid"),
    }


def format_kalshi_quote(value):
    if value is None:
        return "Unavailable"
    return f"{value * 100:.1f}¢"


def kalshi_exit_status(bid):
    if bid is None:
        return "QUOTE UNAVAILABLE"
    if bid >= 0.80:
        return "80¢ EXIT TARGET REACHED"
    if bid >= 0.70:
        return "70¢ EXIT TARGET REACHED"
    return "BELOW EXIT TARGETS"
@bot.tree.command(
    name="kalshi",
    description="View live Kalshi BTC 15-minute markets"
)
async def kalshi(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        markets = await asyncio.to_thread(get_kalshi_markets)

        if not markets:
            await interaction.followup.send(
                "No open Kalshi BTC 15-minute markets found."
            )
            return

        embed = discord.Embed(
            title="GROK BOT | KALSHI BTC MARKETS",
            color=discord.Color.blue()
        )

        for market in markets[:5]:
            ticker = market.get("ticker", "Unknown")
            title = market.get("title", "BTC Market")

            yes_bid = kalshi_price(market, "yes", "bid")
            yes_ask = kalshi_price(market, "yes", "ask")
            no_bid = kalshi_price(market, "no", "bid")
            no_ask = kalshi_price(market, "no", "ask")

            def display_price(value):
                return f"${value:.2f}" if value is not None else "N/A"

            embed.add_field(
                name=title[:250],
                value=(
                    f"Ticker: `{ticker}`\n"
                    f"YES Bid: {display_price(yes_bid)}\n"
                    f"YES Ask: {display_price(yes_ask)}\n"
                    f"NO Bid: {display_price(no_bid)}\n"
                    f"NO Ask: {display_price(no_ask)}"
                ),
                inline=False
            )

        embed.set_footer(
            text="Kalshi public market data | Informational only"
        )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        print(f"Kalshi error: {error}")

        await interaction.followup.send(
            f"Unable to retrieve Kalshi markets: {error}"
        )

@bot.tree.command(
    name="kalshi_history",
    description="View historical prices for the active Kalshi BTC market"
)
async def kalshi_history(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        markets = await __import__("asyncio").to_thread(
            get_kalshi_markets
        )

        if not markets:
            await interaction.followup.send(
                "No open Kalshi BTC markets found."
            )
            return

        market = markets[0]
        ticker = market.get("ticker")

        if not ticker:
            await interaction.followup.send(
                "Unable to find the market ticker."
            )
            return

        end_ts = int(time.time())
        start_ts = end_ts - 15 * 60

        url = (
            "https://external-api.kalshi.com/trade-api/v2/"
            f"series/KXBTC15M/markets/{ticker}/candlesticks"
            f"?start_ts={start_ts}"
            f"&end_ts={end_ts}"
            "&period_interval=1"
        )

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "GrokBot/1.0"}
        )

        def fetch_history():
            with urllib.request.urlopen(
                request, timeout=15
            ) as response:
                return json.loads(response.read())

        data = await __import__("asyncio").to_thread(
            fetch_history
        )

        candles = data.get("candlesticks", [])

        if not candles:
            await interaction.followup.send(
                "No historical candles available yet."
            )
            return

        embed = discord.Embed(
            title="GROK BOT | KALSHI BTC HISTORY",
            description=(
                f"**Market:** `{ticker}`\n"
                "**Period:** Last 15 minutes\n"
                "**Interval:** 1 minute"
            ),
            color=discord.Color.blue()
        )

        for candle in candles[-15:]:
            timestamp = candle.get("end_period_ts")

            price_data = candle.get("price") or {}
            bid_data = candle.get("yes_bid") or {}
            ask_data = candle.get("yes_ask") or {}

            last_price = price_data.get("close_dollars")
            yes_bid = bid_data.get("close_dollars")
            yes_ask = ask_data.get("close_dollars")

            if timestamp is None:
                continue

            timestamp_text = (
                f"<t:{int(timestamp)}:t>"
            )

            def show_price(value):
                if value is None:
                    return "N/A"
                return f"${float(value):.2f}"

            embed.add_field(
                name=f"Time: {timestamp_text}",
                value=(
                    f"YES Price: {show_price(last_price)}\n"
                    f"YES Bid: {show_price(yes_bid)}\n"
                    f"YES Ask: {show_price(yes_ask)}"
                ),
                inline=True
            )

        embed.set_footer(
            text="Kalshi historical market data | Informational only"
        )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        print(f"Kalshi history error: {error}")

        await interaction.followup.send(
            f"Unable to retrieve Kalshi history: {error}"
        )

def get_btc_candles(granularity, count):
    end_time = int(time.time())
    start_time = end_time - (granularity * count)

    start = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time)
    )
    end = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(end_time)
    )

    url = (
        "https://api.exchange.coinbase.com/"
        "products/BTC-USD/candles"
        f"?granularity={granularity}"
        f"&start={start}&end={end}"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GrokBot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        raw = json.loads(response.read())

    candles = [
        {
            "time": row[0],
            "low": float(row[1]),
            "high": float(row[2]),
            "open": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5])
        }
        for row in raw
    ]

    return sorted(candles, key=lambda x: x["time"])


def calculate_ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (value * multiplier) + (
            result * (1 - multiplier)
        )

    return result



def calculate_rsi_series(values, period=14):
    if len(values) <= period:
        return [None] * len(values)

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result = [None] * period

    def get_rsi(gain, loss):
        if loss == 0:
            return 100.0
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    result.append(get_rsi(avg_gain, avg_loss))

    for i in range(period, len(changes)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

        result.append(get_rsi(avg_gain, avg_loss))

    return result


def calculate_rsi(values, period=14):
    result = calculate_rsi_series(values, period)
    return result[-1]


def analyze_timeframe(candles):
    if len(candles) < 51:
        raise ValueError("Not enough candles for analysis.")

    closes = [c["close"] for c in candles]

    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    rsi = calculate_rsi(closes)

    price = closes[-1]

    if price > ema20 > ema50:
        trend = "BULLISH"
    elif price < ema20 < ema50:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    return {
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "trend": trend
    }


def confirm_timeframes(analysis5, analysis15):
    trend5 = analysis5["trend"]
    trend15 = analysis15["trend"]

    rsi5 = analysis5["rsi"]
    rsi15 = analysis15["rsi"]

    # Determine overall trend alignment
    if trend5 == "BULLISH" and trend15 == "BULLISH":
        market = "BULLISH"
        alignment = "BULLISH ALIGNMENT"
        color = discord.Color.green()

    elif trend5 == "BEARISH" and trend15 == "BEARISH":
        market = "BEARISH"
        alignment = "BEARISH ALIGNMENT"
        color = discord.Color.red()

    elif trend5 == "NEUTRAL" and trend15 == "NEUTRAL":
        market = "NEUTRAL"
        alignment = "NEUTRAL"
        color = discord.Color.orange()

    else:
        market = "MIXED / NEUTRAL"
        alignment = "TIMEFRAMES DISAGREE"
        color = discord.Color.orange()

    # Evaluate RSI momentum independently
    if rsi5 > 50 and rsi15 > 50:
        momentum = "BULLISH MOMENTUM"

    elif rsi5 < 50 and rsi15 < 50:
        momentum = "BEARISH MOMENTUM"

    else:
        momentum = "MIXED MOMENTUM"

    # Determine whether momentum supports the trend
    if market == "BULLISH":
        confirmation = (
            "FULL TREND + MOMENTUM SUPPORT"
            if momentum == "BULLISH MOMENTUM"
            else "TREND ALIGNED, MOMENTUM NOT CONFIRMED"
        )

    elif market == "BEARISH":
        confirmation = (
            "FULL TREND + MOMENTUM SUPPORT"
            if momentum == "BEARISH MOMENTUM"
            else "TREND ALIGNED, MOMENTUM NOT CONFIRMED"
        )

    else:
        confirmation = "NO FULL TREND CONFIRMATION"

    return {
        "market": market,
        "alignment": alignment,
        "momentum": momentum,
        "confirmation": confirmation,
        "color": color
    }


def detect_reversal(candles):
    if len(candles) < 30:
        return {
            "bull": 0,
            "bear": 0,
            "signals": ["Insufficient data"]
        }

    closes = [c["close"] for c in candles]
    rsi_values = calculate_rsi_series(closes)

    bull = 0
    bear = 0
    signals = []

    previous = candles[-2]
    current = candles[-1]

    # Bullish engulfing
    if (
        previous["close"] < previous["open"]
        and current["close"] > current["open"]
        and current["open"] <= previous["close"]
        and current["close"] >= previous["open"]
    ):
        bull += 1
        signals.append("Bullish engulfing")

    # Bearish engulfing
    if (
        previous["close"] > previous["open"]
        and current["close"] < current["open"]
        and current["open"] >= previous["close"]
        and current["close"] <= previous["open"]
    ):
        bear += 1
        signals.append("Bearish engulfing")

    # RSI momentum changes
    previous_rsi = rsi_values[-2]
    current_rsi = rsi_values[-1]

    if previous_rsi is not None and current_rsi is not None:
        if previous_rsi < 40 and current_rsi > previous_rsi:
            bull += 1
            signals.append("Bullish RSI recovery")

        if previous_rsi > 60 and current_rsi < previous_rsi:
            bear += 1
            signals.append("Bearish RSI weakening")

    # EMA20 crossover
    previous_ema = calculate_ema(closes[:-1], 20)
    current_ema = calculate_ema(closes, 20)

    if previous_ema is not None and current_ema is not None:
        if closes[-2] <= previous_ema and closes[-1] > current_ema:
            bull += 1
            signals.append("Bullish EMA20 crossover")

        if closes[-2] >= previous_ema and closes[-1] < current_ema:
            bear += 1
            signals.append("Bearish EMA20 crossover")

    # Actual RSI divergence
    older_start = len(candles) - 12
    recent_start = len(candles) - 6

    older = candles[older_start:recent_start]
    recent = candles[recent_start:]

    older_low_index = min(
        range(older_start, recent_start),
        key=lambda i: candles[i]["low"]
    )

    recent_low_index = min(
        range(recent_start, len(candles)),
        key=lambda i: candles[i]["low"]
    )

    older_high_index = max(
        range(older_start, recent_start),
        key=lambda i: candles[i]["high"]
    )

    recent_high_index = max(
        range(recent_start, len(candles)),
        key=lambda i: candles[i]["high"]
    )

    # Bullish divergence:
    # Price makes a lower low, RSI makes a higher low.
    if (
        candles[recent_low_index]["low"]
        < candles[older_low_index]["low"]
        and rsi_values[recent_low_index] is not None
        and rsi_values[older_low_index] is not None
        and rsi_values[recent_low_index]
        > rsi_values[older_low_index]
    ):
        bull += 1
        signals.append("Bullish RSI divergence")

    # Bearish divergence:
    # Price makes a higher high, RSI makes a lower high.
    if (
        candles[recent_high_index]["high"]
        > candles[older_high_index]["high"]
        and rsi_values[recent_high_index] is not None
        and rsi_values[older_high_index] is not None
        and rsi_values[recent_high_index]
        < rsi_values[older_high_index]
    ):
        bear += 1
        signals.append("Bearish RSI divergence")

    return {
        "bull": bull,
        "bear": bear,
        "signals": signals
    }



def classify_reversal(rev15, rev5, trend1):
    bull = rev15["bull"] + rev5["bull"]
    bear = rev15["bear"] + rev5["bear"]

    if bull >= 3 and rev15["bull"] > 0 and rev5["bull"] > 0:
        if trend1 == "BULLISH":
            return "CONFIRMED BULLISH REVERSAL"

        return "POTENTIAL BULLISH REVERSAL"

    if bear >= 3 and rev15["bear"] > 0 and rev5["bear"] > 0:
        if trend1 == "BEARISH":
            return "CONFIRMED BEARISH REVERSAL"

        return "POTENTIAL BEARISH REVERSAL"

    if bull >= 2 and bull > bear:
        return "POTENTIAL BULLISH REVERSAL"

    if bear >= 2 and bear > bull:
        return "POTENTIAL BEARISH REVERSAL"

    return "NO STRONG REVERSAL SIGNAL"


def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        raise ValueError("Not enough candles to calculate ATR.")

    true_ranges = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        true_range = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(true_range)

    return sum(true_ranges[-period:]) / period

def analyze_volume(candles, period=20):

    if len(candles) < period + 1:
        raise ValueError("Not enough candles for volume analysis.")

    volumes = [c["volume"] for c in candles]

    current_volume = volumes[-1]

    previous_volumes = volumes[-(period + 1):-1]

    average_volume = sum(previous_volumes) / period

    if average_volume == 0:
        volume_ratio = 0
    else:
        volume_ratio = current_volume / average_volume

    volume_change = (
        ((current_volume - average_volume) / average_volume) * 100
        if average_volume > 0 else 0
    )
    
    volume_spike = volume_ratio >= 1.5
    extreme_volume_spike = volume_ratio >= 2
    
    if average_volume == 0:
        unusual_volume = False
        volume_activity = "UNAVAILABLE"

    elif volume_ratio >= 1.5:
        unusual_volume = True
        volume_activity = "UNUSUALLY HIGH"

    elif volume_ratio <= 0.5:
        unusual_volume = True
        volume_activity = "UNUSUALLY LOW"

    else:
        unusual_volume = False
        volume_activity = "NORMAL"

    candle = candles[-1]

    candle_open = candle["open"]
    candle_close = candle["close"]
    candle_high = candle["high"]
    candle_low = candle["low"]

    candle_range = candle_high - candle_low

    if candle_range == 0:
        buying_pressure = 0
        selling_pressure = 0
        pressure = "NEUTRAL"

    else:
        close_position = (
            (candle_close - candle_low) / candle_range
        )

        if candle_close > candle_open and close_position >= 0.6:
            buying_pressure = close_position * 100
            selling_pressure = (1 - close_position) * 100
            pressure = "BUYERS"

        elif candle_close < candle_open and close_position <= 0.4:
            buying_pressure = close_position * 100
            selling_pressure = (1 - close_position) * 100
            pressure = "SELLERS"

        else:
            buying_pressure = close_position * 100
            selling_pressure = (1 - close_position) * 100
            pressure = "BALANCED"

    if volume_ratio >= 2:
        strength = "EXTREMELY HIGH"

    elif volume_ratio >= 1.5:
        strength = "HIGH"

    elif volume_ratio >= 1:
        strength = "NORMAL"

    else:
        strength = "LOW"


    if volume_ratio >= 2 and pressure == "BUYERS":
        volume_signal = "VERY STRONG BUYING"

    elif volume_ratio >= 2 and pressure == "SELLERS":
        volume_signal = "VERY STRONG SELLING"

    elif volume_ratio >= 1.5 and pressure == "BUYERS":
        volume_signal = "STRONG BUYING"

    elif volume_ratio >= 1.5 and pressure == "SELLERS":
        volume_signal = "STRONG SELLING"

    elif volume_ratio < 0.5:
        volume_signal = "VERY LOW PARTICIPATION"

    elif pressure == "BUYERS":
        volume_signal = "BUYING PRESSURE"

    elif pressure == "SELLERS":
        volume_signal = "SELLING PRESSURE"

    else:
        volume_signal = "NEUTRAL VOLUME"

    
    return {
        "current_volume": current_volume,
        "average_volume": average_volume,
        "volume_ratio": volume_ratio,
        "volume_change": volume_change,
        "strength": strength,
        "volume_spike": volume_spike,
        "extreme_volume_spike": extreme_volume_spike,
        "unusual_volume": unusual_volume,
        "volume_activity": volume_activity,
        "buying_pressure": buying_pressure,
        "selling_pressure": selling_pressure,
        "pressure": pressure,
        "volume_signal": volume_signal
    }



def generate_trade_signal(candles5, analysis5, analysis15, volume5, volume15):
    price = candles5[-1]["close"]
    atr = calculate_atr(candles5)

    rsi5 = analysis5["rsi"]
    rsi15 = analysis15["rsi"]

    signal = "WAIT"
    confidence = 0
    
    # Track developing setups before full confirmation
    setup_strength = 0

    trend5 = analysis5["trend"]
    trend15 = analysis15["trend"]

    
    if trend5 == "BULLISH":
        setup_strength += 20
    elif trend5 == "BEARISH":
        setup_strength += 20

    if trend15 == "BULLISH":
        setup_strength += 20
    elif trend15 == "BEARISH":
        setup_strength += 20


    # Reward agreement between timeframes
    if trend5 == trend15 and trend5 != "NEUTRAL":
        setup_strength += 20

    # RSI confirmation
    if trend5 == "BULLISH" and rsi5 > 50:
        setup_strength += 10
    elif trend5 == "BEARISH" and rsi5 < 50:
        setup_strength += 10

    if trend15 == "BULLISH" and rsi15 > 50:
        setup_strength += 10
    elif trend15 == "BEARISH" and rsi15 < 50:
        setup_strength += 10

    setup_strength = min(100, setup_strength)

    buying_signals = (
        "BUYING PRESSURE",
        "STRONG BUYING",
        "VERY STRONG BUYING"
    )

    selling_signals = (
        "SELLING PRESSURE",
        "STRONG SELLING",
        "VERY STRONG SELLING"
    )

    volume_signal5 = volume5["volume_signal"]
    volume_signal15 = volume15["volume_signal"]

    # BULLISH CONFIRMATION
    if (
        analysis5["trend"] == "BULLISH"
        and analysis15["trend"] == "BULLISH"
    ):
        confidence = 40

        if rsi5 > 50:
            confidence += 20

        if rsi15 > 50:
            confidence += 20

        if 50 < rsi5 < 70:
            confidence += 10

        # Volume confirmation
        if (
            volume_signal5 in buying_signals
            and volume_signal15 in buying_signals
        ):
            confidence += 10

        elif (
            volume_signal5 in selling_signals
            or volume_signal15 in selling_signals
        ):
            confidence -= 10

        elif (
            volume_signal5 in buying_signals
            or volume_signal15 in buying_signals
        ):
            confidence += 5

        if confidence >= 70:
            signal = "BUY"

    # BEARISH CONFIRMATION
    elif (
        analysis5["trend"] == "BEARISH"
        and analysis15["trend"] == "BEARISH"
    ):
        confidence = 40

        if rsi5 < 50:
            confidence += 20

        if rsi15 < 50:
            confidence += 20

        if 30 < rsi5 < 50:
            confidence += 10

        # Volume confirmation
        if (
            volume_signal5 in selling_signals
            and volume_signal15 in selling_signals
        ):
            confidence += 10

        elif (
            volume_signal5 in buying_signals
            or volume_signal15 in buying_signals
        ):
            confidence -= 10

        elif (
            volume_signal5 in selling_signals
            or volume_signal15 in selling_signals
        ):
            confidence += 5

        if confidence >= 70:
            signal = "SELL"

    confidence = max(0, min(100, confidence))

    
    result = {
        "signal": signal,
        "confidence": confidence,
        "entry": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "atr": atr
    }

    if signal == "BUY":
        stop = price - (atr * 1.5)
        risk = price - stop

        result["entry"] = price
        result["stop_loss"] = stop
        result["take_profit_1"] = price + (risk * 2)
        result["take_profit_2"] = price + (risk * 3)

    elif signal == "SELL":
        stop = price + (atr * 1.5)
        risk = stop - price

        result["entry"] = price
        result["stop_loss"] = stop
        result["take_profit_1"] = price - (risk * 2)
        result["take_profit_2"] = price - (risk * 3)

    return result


@tasks.loop(minutes=15)
async def btc_updates():
    if not CHANNEL_ID:
        return

    
    try:
        channel = bot.get_channel(int(CHANNEL_ID))

        if channel is None:
            channel = await bot.fetch_channel(int(CHANNEL_ID))

        if not hasattr(channel, "send"):
            print("BTC update error: Channel cannot receive messages.")
            return


        # Fetch BTC price and both candle timeframes
        price, candles5, candles15 = await asyncio.gather(
            asyncio.to_thread(get_btc_price),
            asyncio.to_thread(get_btc_candles, 300, 100),
            asyncio.to_thread(get_btc_candles, 900, 100)
        )

               # Analyze both timeframes
        analysis5 = analyze_timeframe(candles5)
        analysis15 = analyze_timeframe(candles15)

        
        # Analyze trading volume on both timeframes
        volume5 = analyze_volume(candles5)
        volume15 = analyze_volume(candles15)

        # Generate volume-confirmed trading signal
        trade = generate_trade_signal(
            candles5,
            analysis5,
            analysis15,
            volume5,
            volume15
        )

        
        
        # Detect reversal signals
        reversal5 = detect_reversal(candles5)
        reversal15 = detect_reversal(candles15)

        # Determine overall reversal classification
        reversal = classify_reversal(
            reversal15,
            reversal5,
            analysis15["trend"]
        )


        # Multi-timeframe trend confirmation
        confirmation = confirm_timeframes(
            analysis5,
            analysis15
        )

        market = confirmation["market"]
        color = confirmation["color"]


        # Build Discord embed
        embed = discord.Embed(
            title="GROK BOT | BTC MARKET ANALYSIS",
            description=(
                f"**Bitcoin Spot Price:** ${price:,.2f}\n"
                f"**Market Direction:** {market}"
            ),
            color=color
        )

        # 5-minute analysis
        embed.add_field(
            name="5-Minute Technical Analysis",
            value=(
                f"Trend: **{analysis5['trend']}**\n"
                f"EMA20: ${analysis5['ema20']:,.2f}\n"
                f"EMA50: ${analysis5['ema50']:,.2f}\n"
                f"RSI: **{analysis5['rsi']:.2f}**"
            ),
            inline=True
        )

        # 15-minute analysis
        embed.add_field(
            name="15-Minute Technical Analysis",
            value=(
                f"Trend: **{analysis15['trend']}**\n"
                f"EMA20: ${analysis15['ema20']:,.2f}\n"
                f"EMA50: ${analysis15['ema50']:,.2f}\n"
                f"RSI: **{analysis15['rsi']:.2f}**"
            ),
            inline=True
        )

        # Trading volume analysis
        embed.add_field(
            name="Trading Volume Analysis",
            value=(
                "**5-Minute Volume**\n"
                f"Activity: {volume5['volume_activity']}\n"
                f"Strength: {volume5['strength']}\n"
                f"Volume Ratio: {volume5['volume_ratio']:.2f}x\n"
                f"Change: {volume5['volume_change']:+.2f}%\n"
                f"Pressure: {volume5['pressure']}\n"
                f"Signal: **{volume5['volume_signal']}**\n\n"
                "**15-Minute Volume**\n"
                f"Activity: {volume15['volume_activity']}\n"
                f"Strength: {volume15['strength']}\n"
                f"Volume Ratio: {volume15['volume_ratio']:.2f}x\n"
                f"Change: {volume15['volume_change']:+.2f}%\n"
                f"Pressure: {volume15['pressure']}\n"
                f"Signal: **{volume15['volume_signal']}**"
            ),
            inline=False
        )

        # Multi-timeframe confirmation
        embed.add_field(
            name="Multi-Timeframe Confirmation",
            value=(
                f"**Alignment:** {confirmation['alignment']}\n"
                f"**Momentum:** {confirmation['momentum']}\n"
                f"**Assessment:** {confirmation['confirmation']}"
            ),
            inline=False
        )

        # Reversal classification
        embed.add_field(
            name="Reversal Analysis",
            value=f"**{reversal}**",
            inline=False
        )

        # Combine detected signals
        signals = []

        for signal in reversal5["signals"]:
            if signal != "Insufficient data":
                signals.append(f"5M: {signal}")

        for signal in reversal15["signals"]:
            if signal != "Insufficient data":
                signals.append(f"15M: {signal}")

        signals = list(dict.fromkeys(signals))

        embed.add_field(
            name="Detected Signals",
            value=(
                "\n".join(signals)
                if signals
                else "No significant reversal signals detected."
            ),
            inline=False
        )

        # RSI interpretation
        rsi5 = analysis5["rsi"]
        rsi15 = analysis15["rsi"]

        embed.add_field(
            name="RSI Momentum",
            value=(
                f"5M: {'Overbought' if rsi5 >= 70 else 'Oversold' if rsi5 <= 30 else 'Neutral'}\n"
                f"15M: {'Overbought' if rsi15 >= 70 else 'Oversold' if rsi15 <= 30 else 'Neutral'}"
            ),
            inline=False
        )

        # Trading signal system
        if trade["signal"] == "WAIT":
            trade_text = (
                "**SIGNAL: WAIT**\n"
                f"Confidence Score: {trade['confidence']}%\n"
                "No qualifying trading setup detected."
            )

        else:
            trade_text = (
                f"**SIGNAL: {trade['signal']}**\n"
                f"Confidence Score: {trade['confidence']}%\n"
                f"Entry: ${trade['entry']:,.2f}\n"
                f"Stop Loss: ${trade['stop_loss']:,.2f}\n"
                f"Take Profit 1: ${trade['take_profit_1']:,.2f}\n"
                f"Take Profit 2: ${trade['take_profit_2']:,.2f}"
            )

        embed.add_field(
            name="GROK BOT | TRADING SIGNAL",
            value=trade_text,
            inline=False
        )

        embed.set_footer(
            text="GROK BOT | Technical Analysis | Informational Only"
        )

        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)

        print("BTC technical-analysis update successfully posted.")

    except Exception as error:
        print(f"BTC update error: {error}")


@btc_updates.before_loop
async def before_btc_updates():
    await bot.wait_until_ready()

# GROK BOT | 1-Minute Reversal Monitor

# Remember the previous reversal state
last_reversal_state = None

@tasks.loop(minutes=1)
async def btc_reversal_monitor():
    try:
        candles5, candles15 = await asyncio.gather(
            asyncio.to_thread(get_btc_candles, 300, 100),
            asyncio.to_thread(get_btc_candles, 900, 100)
        )

        analysis5 = analyze_timeframe(candles5)
        analysis15 = analyze_timeframe(candles15)

        reversal5 = detect_reversal(candles5)
        reversal15 = detect_reversal(candles15)

        reversal = classify_reversal(
            reversal15,
            reversal5,
            analysis15["trend"]
        )

        
        global last_reversal_state

        # Only alert on new reversal states
        alert_states = {
            "POTENTIAL BULLISH REVERSAL",
            "CONFIRMED BULLISH REVERSAL",
            "POTENTIAL BEARISH REVERSAL",
            "CONFIRMED BEARISH REVERSAL"
        }

        # Initialize state without sending an old alert
        if last_reversal_state is None:
            last_reversal_state = reversal
            print(f"Reversal monitor initialized: {reversal}")
            return

        # Detect changes in reversal state
        if reversal != last_reversal_state:
            previous_state = last_reversal_state
            last_reversal_state = reversal

            if reversal in alert_states:
                if "BULLISH" in reversal:
                    color = discord.Color.green()
                    direction = "BULLISH"
                else:
                    color = discord.Color.red()
                    direction = "BEARISH"

                embed = discord.Embed(
                    title="GROK BOT | BTC REVERSAL ALERT",
                    description=(
                        f"**New Signal:** {reversal}\n"
                        f"**Direction:** {direction}\n"
                        f"**Previous State:** {previous_state}\n"
                        f"**5M Trend:** {analysis5['trend']}\n"
                        f"**15M Trend:** {analysis15['trend']}"
                    ),
                    color=color
                )

                embed.timestamp = discord.utils.utcnow()
                embed.set_footer(
                    text="GROK BOT | Reversal Warning | Informational Only"
                )

                if CHANNEL_ID:
                    channel = bot.get_channel(int(CHANNEL_ID))

                    if channel is None:
                        channel = await bot.fetch_channel(
                            int(CHANNEL_ID)
                        )

                    await channel.send(embed=embed)

                print(f"New reversal alert: {reversal}")


    except Exception as error:
        print(f"BTC reversal monitor error: {error}")


@btc_reversal_monitor.before_loop
async def before_btc_reversal_monitor():
    await bot.wait_until_ready()


# GROK BOT | Automatic BTC Movement Monitor

@tasks.loop(seconds=BTC_MOVEMENT_CHECK_SECONDS)
async def btc_movement_monitor():
    try:
        candles = await asyncio.to_thread(
            get_btc_candles, 60, 100
        )

        movement = detect_btc_movement(candles)
        volume = detect_btc_volume_spike(candles)

        if movement is None:
            return

        direction = movement["direction"]
        now = time.time()

        alert_key = (
            "last_up_alert"
            if direction == "UP"
            else "last_down_alert"
        )

        last_alert = btc_movement_alert_state[alert_key]

        if (
            last_alert is not None
            and now - last_alert < BTC_MOVEMENT_ALERT_COOLDOWN
        ):
            return

        if not CHANNEL_ID:
            return

        channel = bot.get_channel(int(CHANNEL_ID))

        if channel is None:
            channel = await bot.fetch_channel(
                int(CHANNEL_ID)
            )

        color = (
            discord.Color.green()
            if direction == "UP"
            else discord.Color.red()
        )

        embed = discord.Embed(
            title="GROK BOT | RAPID BTC MOVEMENT",
            description=(
                f"**Direction:** {direction}\n"
                f"**5-Minute Change:** "
                f"{movement['change_percent']:+.2f}%\n"
                f"**Previous Price:** "
                f"${movement['old_price']:,.2f}\n"
                f"**Current Price:** "
                f"${movement['new_price']:,.2f}"
            ),
            color=color
        )

        if volume and volume["is_spike"]:
            embed.add_field(
                name="VOLUME SPIKE WARNING",
                value=(
                    f"Volume Ratio: "
                    f"{volume['volume_ratio']:.2f}x\n"
                    "Unusually high trading activity detected."
                ),
                inline=False
            )

        embed.timestamp = discord.utils.utcnow()

        embed.set_footer(
            text="GROK BOT | BTC Movement Alert | Informational Only"
        )

        await channel.send(embed=embed)

        btc_movement_alert_state[alert_key] = now

        print(
            f"GROK BOT: BTC {direction} "
            f"{movement['change_percent']:+.2f}% alert sent."
        )

    except Exception as error:
        print(f"BTC movement monitor error: {error}")


@btc_movement_monitor.before_loop
async def before_btc_movement_monitor():
    await bot.wait_until_ready()

# GROK BOT | LIVE KALSHI BTC MONITOR

from datetime import datetime

kalshi_message = None
kalshi_last_ticker = None
from collections import deque
import statistics

kalshi_price_history = deque(maxlen=360)

async def build_kalshi_analysis():
    markets, price = await asyncio.gather(
        asyncio.to_thread(get_kalshi_markets),
        asyncio.to_thread(get_btc_price)
    )

    now = time.time()
    active_markets = []

    for market in markets:
        try:
            close_ts = datetime.fromisoformat(
                market["close_time"].replace("Z", "+00:00")
            ).timestamp()

            open_ts = datetime.fromisoformat(
                market["open_time"].replace("Z", "+00:00")
            ).timestamp()

            if open_ts <= now < close_ts:
                active_markets.append((close_ts, market))

        except (KeyError, ValueError, TypeError):
            continue

    if not active_markets:
        return discord.Embed(
            title="GROK BOT | KALSHI BTC",
            description="Waiting for an active BTC market.",
            color=discord.Color.orange()
        ), None

    close_ts, market = min(
        active_markets,
        key=lambda item: item[0]
    )

    ticker = market["ticker"]
    target = market.get("floor_strike")

    if target is None:
        return discord.Embed(
            title="GROK BOT | KALSHI BTC",
            description="Waiting for Kalshi target price.",
            color=discord.Color.orange()
        ), ticker

    target = float(target)
    difference = price - target

    remaining = max(0, int(close_ts - time.time()))

    minutes, seconds = divmod(remaining, 60)

    if difference > 0:
        position = "UP - ABOVE TARGET"
        color = discord.Color.green()

    elif difference < 0:
        position = "DOWN - BELOW TARGET"
        color = discord.Color.red()

    else:
        position = "AT TARGET"
        color = discord.Color.orange()

    embed = discord.Embed(
        title="GROK BOT | LIVE KALSHI BTC",
        color=color
    )

    embed.add_field(
        name="Kalshi Target Price",
        value=f"${target:,.2f}",
        inline=True
    )

    embed.add_field(
        name="Coinbase BTC Price",
        value=f"${price:,.2f}",
        inline=True
    )

    embed.add_field(
        name="Distance From Target",
        value=f"${difference:+,.2f}",
        inline=False
    )

    embed.add_field(
        name="Time Remaining Until Close",
        value=f"{minutes}m {seconds}s",
        inline=False
    )

    embed.add_field(
        name="Current Position",
        value=f"**{position}**",
        inline=False
    )

    embed.add_field(
        name="Market Ticker",
        value=f"`{ticker}`",
        inline=False
    )

    # LIVE MOMENTUM AND SPIKE ENGINE
    now = time.time()
    kalshi_price_history.append((now, float(price)))

    def price_change(seconds):
        for ts, old_price in reversed(kalshi_price_history):
            if ts <= now - seconds:
                if now - ts > seconds + 20:
                    return None
                return price - old_price
        return None

    change30 = price_change(30)
    change60 = price_change(60)
    change180 = price_change(180)

    def direction(change):
        if change is None:
            return "COLLECTING DATA"
        if change > price * 0.0002:
            return "BULLISH"
        if change < -price * 0.0002:
            return "BEARISH"
        return "NEUTRAL"

    def format_change(change):
        if change is None:
            return "COLLECTING DATA"
        return f"{direction(change)} (${change:+,.2f})"

    history = list(kalshi_price_history)
    moves = [
        (history[i][1] - history[i-1][1])
        for i in range(1, len(history))
        if 2 <= history[i][0] - history[i-1][0] <= 20
    ]

    spike = "COLLECTING DATA"
    volatility = "COLLECTING DATA"
    reversal = "COLLECTING DATA"
    outlook = "UNCERTAIN"

    if len(moves) >= 18:
        baseline = statistics.stdev(moves[:-1])
        threshold = max(baseline * 3, price * 0.0003)

        spike = "NO SPIKE DETECTED"

        if moves[-1] > threshold:
            spike = "UPWARD SPIKE DETECTED"
        elif moves[-1] < -threshold:
            spike = "DOWNWARD SPIKE DETECTED"

        recent_vol = statistics.stdev(moves[-6:])
        volatility = (
            "ELEVATED"
            if recent_vol > max(baseline * 1.5, 0.01)
            else "NORMAL"
        )

        reversal = "NO CLEAR REVERSAL"

        if change30 is not None and change180 is not None:
            if direction(change30) == "BULLISH" and direction(change180) == "BEARISH":
                reversal = "POTENTIAL BULLISH REVERSAL"
            elif direction(change30) == "BEARISH" and direction(change180) == "BULLISH":
                reversal = "POTENTIAL BEARISH REVERSAL"

        if change30 is not None and change60 is not None:
            if direction(change30) == direction(change60):
                outlook = direction(change30)

    embed.add_field(
        name="Live Momentum",
        value=(
            f"30s: {format_change(change30)}\n"
            f"1m: {format_change(change60)}\n"
            f"3m: {format_change(change180)}"
        ),
        inline=False
    )

    embed.add_field(
        name="Spike & Reversal Analysis",
        value=(
            f"Volatility: **{volatility}**\n"
            f"Spike: **{spike}**\n"
            f"Reversal: **{reversal}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Short-Term Momentum Outlook",
        value=f"**{outlook}**\nUnvalidated momentum indicator",
        inline=False
    )
    quotes = get_kalshi_quotes(market)

    embed.add_field(
        name="LIVE KALSHI CONTRACT PRICES",
        value=(
            f"UP Buy: {format_kalshi_quote(quotes['up_buy'])}\n"
            f"UP Sell: {format_kalshi_quote(quotes['up_sell'])}\n"
            f"DOWN Buy: {format_kalshi_quote(quotes['down_buy'])}\n"
            f"DOWN Sell: {format_kalshi_quote(quotes['down_sell'])}"
        ),
        inline=False
    )

    embed.add_field(
        name="EXIT TARGET MONITOR",
        value=(
            f"UP: {kalshi_exit_status(quotes['up_sell'])}\n"
            f"DOWN: {kalshi_exit_status(quotes['down_sell'])}"
        ),
        inline=False
    )
    embed.set_footer(
        text="Coinbase price estimate | Not a settlement prediction"
    )

    embed.timestamp = discord.utils.utcnow()

    return embed, ticker


@tasks.loop(seconds=3)
async def kalshi_live_monitor():
    global kalshi_message
    global kalshi_last_ticker

    try:
        if not CHANNEL_ID:
            print("Kalshi monitor: CHANNEL_ID missing")
            return

        channel = bot.get_channel(int(CHANNEL_ID))

        if channel is None:
            channel = await bot.fetch_channel(
                int(CHANNEL_ID)
            )

        embed, ticker = await build_kalshi_analysis()

        if (
            kalshi_message is None
            or ticker != kalshi_last_ticker
        ):
            kalshi_message = await channel.send(
                embed=embed
            )

        else:
            try:
                await kalshi_message.edit(embed=embed)
            except discord.NotFound:
                kalshi_message = await channel.send(
                    embed=embed
                )

        kalshi_last_ticker = ticker

        print("GROK BOT: Kalshi analysis updated.")

    except Exception as error:
        print(f"Kalshi live monitor error: {error!r}")


@kalshi_live_monitor.before_loop
async def before_kalshi_live_monitor():
    await bot.wait_until_ready()


if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

bot.run(TOKEN)
