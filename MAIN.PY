import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import json
import random
from flask import Flask
from threading import Thread

# --- BANCO DE DADOS (JSON) ---
def carregar_dados(arquivo):
    if not os.path.exists(arquivo):
        with open(arquivo, 'w') as f: json.dump({}, f)
        return {}
    try:
        with open(arquivo, 'r') as f: return json.load(f)
    except: return {}

def salvar_dados(arquivo, dados):
    with open(arquivo, 'w') as f: json.dump(dados, f, indent=4)

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Bot Furia Online!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

# --- CONFIG BOT ---
intents = discord.Intents.all()

class FuriaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Registra a view como persistente
        self.add_view(ViewCentral())
        print("✅ Sistema de Views da FÚRIA Ativo")

bot = FuriaBot()

# Variáveis globais em memória
fila_mediadores = [] 
dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1", "0.50"]

# --- VIEWS ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅", custom_id="furia_med_on")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        pix_db = carregar_dados('pix.json')
        if str(interaction.user.id) not in pix_db:
            return await interaction.followup.send("❌ Cadastre o Pix primeiro!", ephemeral=True)
        
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores])
            emb = interaction.message.embeds[0]
            emb.set_field_at(0, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=emb)
            await interaction.followup.send("✅ Você está ON!", ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💠", custom_id="furia_pix_modal")
    async def pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Modais não podem ter defer antes, abrem direto
        await interaction.response.send_modal(ModalPixFuria())

# --- MODAL PIX ---
class ModalPixFuria(discord.ui.Modal, title='💠 CADASTRAR PIX - FÚRIA'):
    chave = discord.ui.TextInput(label='Chave Pix', required=True)
    banco = discord.ui.TextInput(label='Nome do Banco', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        db = carregar_dados('pix.json')
        db[str(interaction.user.id)] = {"chave": self.chave.value, "banco": self.banco.value}
        salvar_dados('pix.json', db)
        await interaction.response.send_message("✅ Pix salvo!", ephemeral=True)

# --- COMANDOS ---
@bot.tree.command(name="central", description="Painel de Mediadores")
async def central(interaction: discord.Interaction):
    emb = discord.Embed(title="👮 CENTRAL DE MEDIADORES - FÚRIA", color=0xFFA500)
    emb.add_field(name="Mediadores Online:", value="Nenhum no momento.", inline=False)
    await interaction.response.send_message(embed=emb, view=ViewCentral())

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ {len(synced)} comandos sincronizados!")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.event
async def on_ready():
    print(f"🚀 Bot {bot.user} Ligado!")
    await bot.tree.sync()

# --- RODAR O BOT COM SEGURANÇA ---
if __name__ == "__main__":
    keep_alive()
    # O código vai procurar uma variável chamada 'TOKEN' no seu sistema/GitHub
    token = os.environ.get('TOKEN')
    if token:
        bot.run(token)
    else:
        print("❌ ERRO: O Token não foi encontrado nas variáveis de ambiente!")
