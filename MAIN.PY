import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# 1. Configuração do Servidor para o Render não dar erro
app = Flask('')

@app.route('/')
def home():
    return "Bot está online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Configuração do Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'🚀 BOT ONLINE: {bot.user}')

@bot.command()
async def furia(ctx):
    await ctx.send("FÚRIA ATIVADA! 🐾")

# 3. Início de tudo
keep_alive()
token = os.environ.get('TOKEN') # Aqui ele lê o que você salvou no Environment
bot.run(token)
