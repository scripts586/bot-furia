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

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Bot Furia Online!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    Thread(target=run).start()

# --- CONFIGURAÇÃO ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

mediadores_dados = {} 
fila_mediadores = [] 
dados_filas = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- VIEW: FINALIZAÇÃO (/WIN) ---
class ViewFinalizarWin(discord.ui.View):
    def __init__(self, p1, p2, valor_aposta):
        super().__init__(timeout=None)
        self.p1, self.p2 = p1, p2
        self.valor = valor_aposta
        self.ganhador = None
        self.perdedor = None

    @discord.ui.select(placeholder="🥇 Selecionar o Vencedor...")
    async def select_ganhador(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.ganhador = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Ganhador: **{self.ganhador.display_name}**", ephemeral=True)

    @discord.ui.select(placeholder="💀 Selecionar o Perdedor...")
    async def select_perdedor(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.perdedor = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Perdedor: **{self.perdedor.display_name}**", ephemeral=True)

    @discord.ui.button(label="FINALIZAR E REGISTRAR", style=discord.ButtonStyle.danger, emoji="🔒")
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ganhador or not self.perdedor:
            return await interaction.response.send_message("❌ Selecione os dois!", ephemeral=True)
        
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
            emb = discord.Embed(title="🏁 PARTIDA ENCERRADA", color=0x2ECC71)
            emb.add_field(name="👑 Vencedor", value=f"{self.ganhador.mention}")
            emb.add_field(name="💀 Perdedor", value=f"{self.perdedor.mention}")
            emb.add_field(name="💰 Valor", value=f"```R$ {self.valor},00```", inline=False)
            await canal_res.send(embed=emb)

        await interaction.followup.send("🚨 Tópico fechando...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

# --- VIEW: FILA COM MENCIONAR (@) ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, modalidade):
        super().__init__(timeout=None)
        self.valor = valor
        self.modalidade = modalidade

    async def gerenciar_fila(self, interaction, tipo_gelo):
        bl = carregar_dados('blacklist.json')
        if str(interaction.user.id) in bl:
            return await interaction.response.send_message("❌ Você está banido!", ephemeral=True)

        chave = (interaction.channel.id, self.valor, tipo_gelo)
        if chave not in dados_filas: dados_filas[chave] = []
        
        fila = dados_filas[chave]
        if interaction.user in fila:
            return await interaction.response.send_message("Você já está na fila!", ephemeral=True)

        fila.append(interaction.user)
        
        # Atualiza a Embed com o @menção
        jogadores_str = "\n".join([p.mention for p in fila])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="Jogadores:", value=jogadores_str, inline=False)
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ Você entrou na fila de R$ {self.valor}!", ephemeral=True)

        if len(fila) >= 2: # Sempre 2 líderes
            p1, p2 = fila.pop(0), fila.pop(0)
            
            # Reset visual
            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)

            canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_res:
                msg = await canal_res.send(f"⚠️ **PARTIDA:** {p1.mention} **VS** {p2.mention}")
                thread = await msg.create_thread(name=f"💸 {self.modalidade} | R${self.valor}")
                
                # View de Confirmação Simples
                class ViewConfirm(discord.ui.View):
                    def __init__(self): super().__init__(timeout=None)
                    @discord.ui.button(label="CONFIRMAR", style=discord.ButtonStyle.success)
                    async def c(self, i, b):
                        await i.response.send_message(f"✅ {i.user.mention} confirmou!", ephemeral=False)

                await thread.send(f"Preparem-se! Modalidade: {self.modalidade}\nTipo: {tipo_gelo}", view=ViewConfirm())

    @discord.ui.button(label="Gelo Normal", style=discord.ButtonStyle.secondary, emoji="🧊")
    async def gelo_normal(self, i, b): await self.gerenciar_fila(i, "Gelo Normal")

    @discord.ui.button(label="Gelo Infinito", style=discord.ButtonStyle.secondary, emoji="♾️")
    async def gelo_infinito(self, i, b): await self.gerenciar_fila(i, "Gelo Infinito")

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair(self, interaction, button):
        for chave in dados_filas:
            if interaction.user in dados_filas[chave]:
                dados_filas[chave].remove(interaction.user)
                embed = interaction.message.embeds[0]
                f = dados_filas[chave]
                txt = "\n".join([p.mention for p in f]) if f else "Nenhum jogador na fila"
                embed.set_field_at(1, name="Jogadores:", value=txt, inline=False)
                await interaction.message.edit(embed=embed)
                return await interaction.response.send_message("Você saiu!", ephemeral=True)

# --- COMANDOS ---
@bot.tree.command(name="atualizar_filas")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("Gereando...", ephemeral=True)
    nome = interaction.channel.name.lower()
    mod = "1v1 Mobile" if "x1" in nome else "2v2 Mobile" if "x2" in nome else "3v3 Mobile" if "x3" in nome else "4v4 Mobile"
    
    await interaction.channel.purge(limit=50)
    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500, title=mod)
        embed.add_field(name="Valor:", value=f"R$ {v},00", inline=False)
        embed.add_field(name="Jogadores:", value="Nenhum jogador na fila", inline=False)
        embed.set_footer(text="Fúria Apostas - System Labs")
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, mod))

@bot.tree.command(name="win")
@app_commands.checks.has_role("ADM")
async def win(interaction: discord.Interaction, jogador1: discord.Member, jogador2: discord.Member, valor: str):
    view = ViewFinalizarWin(jogador1, jogador2, valor)
    opcoes = [discord.SelectOption(label=jogador1.display_name, value=str(jogador1.id)), discord.SelectOption(label=jogador2.display_name, value=str(jogador2.id))]
    view.select_ganhador.options = opcoes
    view.select_perdedor.options = opcoes
    await interaction.response.send_message(embed=discord.Embed(title="⚙️ FINALIZAR", color=0x95A5A6), view=view)

@bot.tree.command(name="ranking")
async def ranking(interaction: discord.Interaction):
    stats = carregar_dados('stats.json')
    if not stats: return await interaction.response.send_message("Sem dados.")
    ranking_ord = sorted(stats.items(), key=lambda item: item[1]['vitorias'], reverse=True)[:10]
    txt = "\n".join([f"**{i}.** <@{uid}> — {d['vitorias']} VIT" for i, (uid, d) in enumerate(ranking_ord, 1)])
    await interaction.response.send_message(embed=discord.Embed(title="🏆 RANKING", description=txt, color=0xF1C40F))

@bot.event
async def on_ready(): print(f"🚀 {bot.user.name} ONLINE")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Sincronizado!")

keep_alive()
bot.run(os.environ['TOKEN'])
