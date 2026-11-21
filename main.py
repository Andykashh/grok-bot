
import os
import time
import urllib.request
import json

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

@tasks.loop(minutes=15)
async def btc_updates():
    if not CHANNEL_ID:
        return

    try:
        channel = bot.get_channel(int(CHANNEL_ID))

        if channel is None:
            return

        price = await __import__("asyncio").to_thread(
            get_btc_price
        )

        await channel.send(
            f"**GROK BOT | 15-MINUTE UPDATE**\n"
            f"BTC Spot Price: **${price:,.2f}**\n"
            f"Timestamp: <t:{int(time.time())}:F>"
        )

    except Exception as error:
        print(f"BTC update error: {error}")


if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

bot.run(TOKEN)
