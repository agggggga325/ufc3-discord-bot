#!/usr/bin/env python3
import os
import json
import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERVER_IP = os.getenv("SERVER_IP", "51.75.118.171")
SERVER_PORT = os.getenv("SERVER_PORT", "20174")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

DATA_FILE = "bot_data.json"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "servers": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def check_server_status(session):
    url = f"http://{SERVER_IP}:{SERVER_PORT}/"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return resp.status == 200
    except Exception:
        return False

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global commands")
    except Exception as e:
        print(f"Command sync failed: {e}")

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms", ephemeral=True)

@bot.tree.command(name="status", description="Check UFC3 server status")
async def status(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        online = await check_server_status(session)
    if online:
        embed = discord.Embed(title="UFC3 Server Status", color=discord.Color.green())
        embed.add_field(name="Address", value=f"{SERVER_IP}:{SERVER_PORT}", inline=False)
        embed.add_field(name="Status", value="Online", inline=False)
    else:
        embed = discord.Embed(title="UFC3 Server Status", color=discord.Color.red())
        embed.add_field(name="Address", value=f"{SERVER_IP}:{SERVER_PORT}", inline=False)
        embed.add_field(name="Status", value="Offline", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="register", description="Register your Discord for netplay (WireGuard)")
async def register(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    if user_id in data["users"]:
        await interaction.response.send_message(
            "You are already registered. Use `/key` to get your WireGuard config.",
            ephemeral=True
        )
        return
    data["users"][user_id] = {
        "discord_name": str(interaction.user),
        "registered_at": asyncio.get_event_loop().time(),
        "wireguard_key": None,
    }
    save_data(data)
    await interaction.response.send_message(
        "Registered! An admin will assign your WireGuard key. Use `/key` once assigned.",
        ephemeral=True
    )

@bot.tree.command(name="key", description="Get your assigned WireGuard key")
async def key(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    if user_id not in data["users"]:
        await interaction.response.send_message(
            "Not registered. Use `/register` first.", ephemeral=True
        )
        return
    wg_key = data["users"][user_id].get("wireguard_key")
    if not wg_key:
        await interaction.response.send_message(
            "No WireGuard key assigned yet. Ask an admin to assign one.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        f"Your WireGuard public key: `{wg_key}`\n"
        f"Endpoint: {SERVER_IP}:{SERVER_PORT}",
        ephemeral=True
    )

@bot.tree.command(name="assignkey", description="[Admin] Assign a WireGuard key to a user")
@app_commands.describe(user="The user to assign a key to", wg_key="WireGuard public key")
async def assignkey(interaction: discord.Interaction, user: discord.User, wg_key: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    data = load_data()
    uid = str(user.id)
    if uid not in data["users"]:
        data["users"][uid] = {"discord_name": str(user), "registered_at": asyncio.get_event_loop().time(), "wireguard_key": None}
    data["users"][uid]["wireguard_key"] = wg_key
    save_data(data)
    await interaction.response.send_message(
        f"Assigned WireGuard key to {user.mention}: `{wg_key}`", ephemeral=True
    )

@bot.tree.command(name="matchmake", description="Announce you are looking for a match")
@app_commands.describe(opponent="Optional: tag a specific opponent")
async def matchmake(interaction: discord.Interaction, opponent: discord.User = None):
    data = load_data()
    uid = str(interaction.user.id)
    if uid not in data["users"] or not data["users"][uid].get("wireguard_key"):
        await interaction.response.send_message(
            "You need a registered WireGuard key to matchmake. Use `/register`.", ephemeral=True
        )
        return
    target = opponent.mention if opponent else "anyone"
    embed = discord.Embed(title="Match Request", color=discord.Color.blue())
    embed.add_field(name="Host", value=interaction.user.mention, inline=False)
    embed.add_field(name="Looking for", value=target, inline=False)
    embed.add_field(name="Server", value=f"{SERVER_IP}:{SERVER_PORT}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server connection info")
async def serverinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="UFC3 Reborn Online - Connection Info", color=discord.Color.green())
    embed.add_field(name="Game", value="UFC Undisputed 3 (Xbox 360 via Xenia Canary)", inline=False)
    embed.add_field(name="Server IP", value=SERVER_IP, inline=True)
    embed.add_field(name="Port", value=SERVER_PORT, inline=True)
    embed.add_field(name="Launcher", value="UFC3-Online-Launcher.py", inline=False)
    embed.add_field(name="Note", value="HTTP server hosts game files only. True netplay needs Discord auth + WireGuard VPN.", inline=False)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Set DISCORD_BOT_TOKEN environment variable")
        print("Copy .env.example to .env and add your token")
    else:
        bot.run(TOKEN)
