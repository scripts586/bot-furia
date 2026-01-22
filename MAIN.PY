import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import asyncio
import random
import json
import datetime

# --- BANCO DE DADOS (JSON) ---
def carregar_dados(arquivo):
    try:
        with open(arquivo, 'r') as f: return json.load(f)
    except FileNotFoundError: return {}

def salvar_dados(arquivo, dados):
    with open(arquivo, 'w') as f: json.dump(dados, f, indent=4)

def carregar_blacklist(): return carregar_dados('blacklist.json')

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Bot Furia Online!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIG BOT ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

mediadores_dados = {} 
fila_mediadores = [] 
dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- VIEW: FINALIZAÇÃO (WIN) ---
class ViewFinalizarWin(discord.ui.View):
    def __init__(self, p1, p2, valor_aposta):
        super().__init__(timeout=None)
        self.p1, self.p2 = p1, p2
        self.valor = valor_aposta
        self.ganhador = None
        self.perdedor = None

    @discord.ui.select(placeholder="🏆 Selecione o Ganhador")
    async def select_ganhador(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.ganhador = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Ganhador: {self.ganhador.mention}", ephemeral=True)

    @discord.ui.select(placeholder="💀 Selecione o Perdedor")
    async def select_perdedor(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.perdedor = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Perdedor: {self.perdedor.mention}", ephemeral=True)

    @discord.ui.button(label="Finalizar Aposta 🏁", style=discord.ButtonStyle.danger)
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ganhador or not self.perdedor:
            return await interaction.response.send_message("❌ Selecione ambos!", ephemeral=True)
        
        await interaction.response.defer()
        stats = carregar_dados('stats.json')
        for uid in [str(self.ganhador.id), str(self.perdedor.id)]:
            if uid not in stats: stats[uid] = {"vitorias": 0, "derrotas": 0, "streak": 0}
        
        stats[str(self.ganhador.id)]["vitorias"] += 1
        stats[str(self.ganhador.id)]["streak"] += 1
        stats[str(self.perdedor.id)]["derrotas"] += 1
        stats[str(self.perdedor.id)]["streak"] = 0
        salvar_dados('stats.json', stats)

        canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
        if canal_res:
            emb = discord.Embed(title="🏆 APOSTA REGISTRADA", color=0x2ECC71)
            emb.add_field(name="👑 Vencedor", value=self.ganhador.mention)
            emb.add_field(name="💀 Perdedor", value=self.perdedor.mention)
            emb.add_field(name="💰 Valor", value=f"R$ {self.valor},00")
            await canal_res.send(embed=emb)

        await interaction.followup.send("✅ Tópico deletado!")
        await interaction.channel.delete()

# --- VIEW: FILA PADRÃO FÚRIA ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, modalidade):
        super().__init__(timeout=None)
        self.valor = valor
        self.modalidade = modalidade

    async def gerenciar_fila(self, interaction, tipo_gelo):
        bl = carregar_blacklist()
        if str(interaction.user.id) in bl:
            return await interaction.response.send_message("❌ Blacklist!", ephemeral=True)

        chave = (interaction.channel.id, self.valor, tipo_gelo)
        if chave not in dados_filas_memoria: dados_filas_memoria[chave] = []
        
        fila = dados_filas_memoria[chave]
        if interaction.user in fila:
            return await interaction.response.send_message("❌ Já está na fila!", ephemeral=True)

        fila.append(interaction.user)
        
        # Atualiza Embed com @mention em tempo real
        jogadores_str = "\n".join([p.mention for p in fila])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="Jogadores:", value=jogadores_str, inline=False)
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ Entrou R$ {self.valor}", ephemeral=True)

        if len(fila) >= 2: # Puxa com 2 jogadores
            p1, p2 = fila.pop(0), fila.pop(0)
            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)

            canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_res:
                msg = await canal_res.send(f"⚠️ **PARTIDA:** {p1.mention} VS {p2.mention}")
                thread = await msg.create_thread(name=f"💸 {self.modalidade} | R${self.valor}")
                await thread.send(content=f"{p1.mention} {p2.mention}\nUse /win para finalizar.", view=ViewConfirmacaoSimple(p1, p2, self.valor))

# --- VIEWS AUXILIARES ---
class ViewConfirmacaoSimple(discord.ui.View):
    def __init__(self, p1, p2, valor):
        super().__init__(timeout=None)
        self.p1, self.p2, self.valor = p1, p2, valor
    @discord.ui.button(label="ACEITAR", style=discord.ButtonStyle.success)
    async def aceitar(self, i, b):
        await i.response.send_message(f"✅ {i.user.mention} aceitou o desafio!")

# --- COMANDOS SLASH ---
@bot.tree.command(name="atualizar_filas")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Atualizando...", ephemeral=True)
    nome = interaction.channel.name.lower()
    plataforma = "Emulador" if "emulador" in nome else "Mobile"
    x = "1v1" if "x1" in nome else "2v2" if "x2" in nome else "3v3" if "x3" in nome else "4v4"
    mod = f"{x} {plataforma}" #

    await interaction.channel.purge(limit=100) #

    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500, title=mod)
        embed.add_field(name="Valor:", value=f"R$ {v},00")
        embed.add_field(name="Jogadores:", value="Nenhum jogador na fila", inline=False)
        embed.set_footer(text="Fúria Apostas - System Labs") #
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, mod))

@bot.tree.command(name="win")
@app_commands.checks.has_role("ADM")
async def win(interaction: discord.Interaction, jogador1: discord.Member, jogador2: discord.Member, valor: str):
    view = ViewFinalizarWin(jogador1, jogador2, valor)
    opcoes = [discord.SelectOption(label=jogador1.display_name, value=str(jogador1.id)),
              discord.SelectOption(label=jogador2.display_name, value=str(jogador2.id))]
    view.select_ganhador.options = opcoes
    view.select_perdedor.options = opcoes
    await interaction.response.send_message(embed=discord.Embed(title="🏁 FINALIZAR"), view=view)

@bot.event
async def on_ready():
    print("🚀 FÚRIA UNIFICADA ONLINE!")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Sincronizado!")

keep_alive()
bot.run(os.environ['TOKEN'])
