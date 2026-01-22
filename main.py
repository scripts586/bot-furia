import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# Servidor para o Render não dar erro de Cloudflare
app = Flask('')

@app.route('/')
def home():
    return "Bot Online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Configuração do Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'🚀 BOT ONLINE: {bot.user}')

@bot.command()
async def furia(ctx):
    await ctx.send("FÚRIA ATIVADA! 🐾")

# Início
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get('TOKEN')
    bot.run(token)
