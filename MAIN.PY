import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import asyncio
import random
import json

# --- DATABASE ---
def carregar_dados(arquivo):
    try:
        with open(arquivo, 'r') as f: return json.load(f)
    except FileNotFoundError: return {}

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
bot = commands.Bot(command_prefix='!', intents=intents)

dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- VIEW: FILA PADRÃO FÚRIA ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, modalidade):
        super().__init__(timeout=None)
        self.valor = valor
        self.modalidade = modalidade

    async def gerenciar_fila(self, interaction, tipo_gelo):
        chave = (interaction.channel.id, self.valor, tipo_gelo)
        if chave not in dados_filas_memoria: dados_filas_memoria[chave] = []
        
        fila = dados_filas_memoria[chave]
        if interaction.user in fila:
            return await interaction.response.send_message("❌ Você já está na fila!", ephemeral=True)

        fila.append(interaction.user)
        
        # Atualiza Embed com @mention em tempo real
        jogadores_str = "\n".join([p.mention for p in fila])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="Jogadores:", value=jogadores_str, inline=False)
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ Você entrou na fila de R$ {self.valor}!", ephemeral=True)

        if len(fila) >= 2: # Puxa com 2 jogadores líderes
            p1, p2 = fila.pop(0), fila.pop(0)
            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)

            canal_partidas = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_partidas:
                msg = await canal_partidas.send(f"⚠️ **PARTIDA ENCONTRADA:** {p1.mention} VS {p2.mention}")
                thread = await msg.create_thread(name=f"💸 {self.modalidade} | R${self.valor}")
                await thread.send(content=f"{p1.mention} {p2.mention}\n**Modalidade:** {self.modalidade}\n**Gelo:** {tipo_gelo}\nUsem /win para finalizar.")

    @discord.ui.button(label="Gelo Normal", style=discord.ButtonStyle.secondary, emoji="🧊")
    async def gelo_normal(self, i, b): await self.gerenciar_fila(i, "Gelo Normal")

    @discord.ui.button(label="Gelo Infinito", style=discord.ButtonStyle.secondary, emoji="♾️")
    async def gelo_infinito(self, i, b): await self.gerenciar_fila(i, "Gelo Infinito")

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair(self, interaction, button):
        for chave in dados_filas_memoria:
            if interaction.user in dados_filas_memoria[chave]:
                dados_filas_memoria[chave].remove(interaction.user)
                f = dados_filas_memoria[chave]
                txt = "\n".join([p.mention for p in f]) if f else "Nenhum jogador na fila"
                embed = interaction.message.embeds[0]
                embed.set_field_at(1, name="Jogadores:", value=txt, inline=False)
                await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✅ Saiu da fila!", ephemeral=True)

# --- COMANDO SLASH: ATUALIZAR FILAS ---
@bot.tree.command(name="atualizar_filas", description="Limpa o canal e gera as filas da Fúria")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Sincronizando canais e limpando mensagens...", ephemeral=True)
    
    canal_nome = interaction.channel.name.lower()
    
    # Detecção Rigorosa de Nome
    plataforma = "Mobile" if "mobile" in canal_nome else "Emulador" if "emulador" in canal_nome else "Aposta"
    
    # Detecção de Modalidade (1v1, 2v2, etc)
    if "1v1" in canal_nome: mod = "1v1"
    elif "2v2" in canal_nome: mod = "2v2"
    elif "3v3" in canal_nome: mod = "3v3"
    elif "4v4" in canal_nome: mod = "4v4"
    else: mod = "X"

    titulo_final = f"{mod} {plataforma}" # Ex: 1v1 Mobile ou 4v4 Emulador

    # Limpa o canal atual
    await interaction.channel.purge(limit=100)

    # Envia os painéis na ordem correta
    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500, title=titulo_final)
        embed.add_field(name="Valor:", value=f"R$ {v},00", inline=False)
        embed.add_field(name="Jogadores:", value="Nenhum jogador na fila", inline=False)
        embed.set_footer(text="Bot Apostado Free - System Labs") # Igual ao print
        
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, titulo_final))

@bot.event
async def on_ready():
    print(f"🚀 FÚRIA CONECTADA: {bot.user.name}")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Comandos Sincronizados com o Servidor!")

keep_alive()
bot.run(os.environ['TOKEN'])
