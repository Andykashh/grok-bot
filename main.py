.
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


class GrokBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.started_at = time.time()

    async def setup_hook(self):
        await self.tree.sync()
        btc_updates.start()


bot = GrokBot()


@bot.tree.command(name="btc", description="Get the latest Bitcoin spot price")
async def btc(interaction: discord.Interaction):
    await interaction.response.defer()

@bot.tree.command(
    name="btcanalysis",
    description="Get full Bitcoin technical analysis"
)
async def btcanalysis(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        price, candles5, candles15 = await asyncio.gather(
            asyncio.to_thread(get_btc_price),
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

        if (
            analysis5["trend"] == "BULLISH"
            and analysis15["trend"] == "BULLISH"
        ):
            market = "BULLISH"
            color = discord.Color.green()
        elif (
            analysis5["trend"] == "BEARISH"
            and analysis15["trend"] == "BEARISH"
        ):
            market = "BEARISH"
            color = discord.Color.red()
        else:
            market = "MIXED / NEUTRAL"
            color = discord.Color.orange()

        embed = discord.Embed(
            title="GROK BOT | BTC MARKET ANALYSIS",
            description=(
                f"BTC Spot Price: **${price:,.2f}**\n"
                f"Overall Direction: **{market}**"
            ),
            color=color
        )

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

        embed.add_field(
            name="Reversal Analysis",
            value=f"**{reversal}**",
            inline=False
        )

        signals = (
            [f"5M: {s}" for s in reversal5["signals"]
             if s != "Insufficient data"]
            +
            [f"15M: {s}" for s in reversal15["signals"]
             if s != "Insufficient data"]
        )

        embed.add_field(
            name="Detected Signals",
            value="\n".join(dict.fromkeys(signals))
            if signals else "No significant signals detected.",
            inline=False
        )

        embed.set_footer(
            text="GROK BOT | Informational Only"
        )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        print(f"BTC analysis command error: {error}")
        await interaction.followup.send(
            f"Unable to complete BTC analysis: {error}"
        )

    try:
        price = get_btc_price()

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
        await interaction.followup.send(
            f"Unable to retrieve BTC data: {error}"
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


@bot.tree.command(
    name="kalshi",
    description="View live Kalshi BTC 15-minute markets"
)
async def kalshi(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        markets = await __import__("asyncio").to_thread(
            get_kalshi_markets
        )

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


def calculate_rsi(values, period=14):
    if len(values) <= period:
        return None

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]

    average_gain = sum(gains[-period:]) / period
    average_loss = sum(losses[-period:]) / period

    if average_loss == 0:
        return 100.0

    rs = average_gain / average_loss
    return 100 - (100 / (1 + rs))


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


def detect_reversal(candles):
    if len(candles) < 30:
        return {
            "bull": 0,
            "bear": 0,
            "signals": ["Insufficient data"]
        }

    closes = [c["close"] for c in candles]
    rsi = calculate_rsi(closes)

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
    previous_rsi = calculate_rsi(closes[:-1])

    if previous_rsi is not None and rsi is not None:
        if previous_rsi < 40 and rsi > previous_rsi:
            bull += 1
            signals.append("Bullish RSI recovery")

        if previous_rsi > 60 and rsi < previous_rsi:
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

    # RSI divergence using two recent swing windows
    if rsi is not None:
        older = candles[-12:-6]
        recent = candles[-6:]

        older_low = min(older, key=lambda c: c["low"])
        recent_low = min(recent, key=lambda c: c["low"])

        older_high = max(older, key=lambda c: c["high"])
        recent_high = max(recent, key=lambda c: c["high"])

        if (
            recent_low["low"] < older_low["low"]
            and recent_low["time"] > older_low["time"]
        ):
            bull += 1
            signals.append("Potential bullish price divergence")

        if (
            recent_high["high"] > older_high["high"]
            and recent_high["time"] > older_high["time"]
        ):
            bear += 1
            signals.append("Potential bearish price divergence")

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


@tasks.loop(minutes=15)
async def btc_updates():
    if not CHANNEL_ID:
        return

    try:
        channel = bot.get_channel(int(CHANNEL_ID))

        if channel is None:
            print("BTC update error: Discord channel not found.")
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

        # Detect reversal signals
        reversal5 = detect_reversal(candles5)
        reversal15 = detect_reversal(candles15)

        # Determine overall reversal classification
        reversal = classify_reversal(
            reversal15,
            reversal5,
            analysis15["trend"]
        )

        # Determine overall market direction
        if (
            analysis5["trend"] == "BULLISH"
            and analysis15["trend"] == "BULLISH"
        ):
            market = "BULLISH"
            color = discord.Color.green()

        elif (
            analysis5["trend"] == "BEARISH"
            and analysis15["trend"] == "BEARISH"
        ):
            market = "BEARISH"
            color = discord.Color.red()

        else:
            market = "MIXED / NEUTRAL"
            color = discord.Color.orange()

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



if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

bot.run(TOKEN)
