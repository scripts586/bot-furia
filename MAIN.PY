import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import asyncio
import json

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
def keep_alive(): Thread(target=run).start()

# --- CONFIG BOT ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1", "0.50"]

# --- VIEW: FINALIZAÇÃO (WIN) ---
class ViewFinalizarWin(discord.ui.View):
    def __init__(self, p1, p2, valor_aposta):
        super().__init__(timeout=None)
        self.p1, self.p2, self.valor = p1, p2, valor_aposta
        self.ganhador = None
        self.perdedor = None

    @discord.ui.select(placeholder="🏆 Selecionar Vencedor (FÚRIA)")
    async def select_ganhador(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.ganhador = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Ganhador: {self.ganhador.mention}", ephemeral=True)

    @discord.ui.select(placeholder="💀 Selecionar Perdedor (FÚRIA)")
    async def select_perdedor(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.perdedor = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Perdedor: {self.perdedor.mention}", ephemeral=True)

    @discord.ui.button(label="REGISTRAR RESULTADO", style=discord.ButtonStyle.danger, emoji="🏁")
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ganhador or not self.perdedor:
            return await interaction.response.send_message("❌ Selecione os jogadores!", ephemeral=True)
        
        await interaction.response.defer()
        stats = carregar_dados('stats.json')
        for uid in [str(self.ganhador.id), str(self.perdedor.id)]:
            if uid not in stats: stats[uid] = {"vitorias": 0, "derrotas": 0}
        
        stats[str(self.ganhador.id)]["vitorias"] += 1
        stats[str(self.perdedor.id)]["derrotas"] += 1
        salvar_dados('stats.json', stats)

        canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
        if canal_res:
            emb = discord.Embed(title="🏁 ORG FÚRIA | RESULTADO", color=0x2ECC71)
            emb.add_field(name="👑 Vencedor", value=self.ganhador.mention)
            emb.add_field(name="💰 Valor", value=f"R$ {self.valor}")
            await canal_res.send(embed=emb)

        await interaction.channel.delete()

# --- VIEW: FILA COM MENCIONAR (@) ---
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
        
        await interaction.response.send_message(f"✅ Entrou na fila R$ {self.valor}", ephemeral=True)

        if len(fila) >= 2: # Puxa com 2 jogadores líderes
            p1, p2 = fila.pop(0), fila.pop(0)
            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)

            canal_partidas = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_partidas:
                msg = await canal_partidas.send(f"⚠️ **PARTIDA ORG FÚRIA:** {p1.mention} VS {p2.mention}")
                thread = await msg.create_thread(name=f"⚔️ {self.modalidade} | R${self.valor}")
                await thread.send(content=f"{p1.mention} {p2.mention}\n**Gelo:** {tipo_gelo}\nADMs, usem /win para finalizar.")

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
        await interaction.response.send_message("✅ Você saiu!", ephemeral=True)

# --- COMANDOS ORG FÚRIA ---
@bot.tree.command(name="atualizar_filas")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Atualizando Painéis FÚRIA...", ephemeral=True)
    nome_c = interaction.channel.name.lower()
    
    plataforma = "Mobile" if "mobile" in nome_c else "Emulador" if "emulador" in nome_c else "Aposta"
    x = "1v1" if "x1" in nome_c else "2v2" if "x2" in nome_c else "3v3" if "x3" in nome_c else "4v4"
    mod_final = f"{x} {plataforma}"

    await interaction.channel.purge(limit=100)

    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500, title=f"⚔️ {mod_final}")
        embed.add_field(name="💰 Valor da Aposta:", value=f"R$ {v}", inline=False)
        embed.add_field(name="👥 Jogadores:", value="Nenhum jogador na fila", inline=False)
        # Rodapé personalizado da Org Fúria
        embed.set_footer(text="ORG FÚRIA | SALAS 10 C") 
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, mod_final))

@bot.tree.command(name="win")
@app_commands.checks.has_role("ADM")
async def win(interaction: discord.Interaction, jogador1: discord.Member, jogador2: discord.Member, valor: str):
    view = ViewFinalizarWin(jogador1, jogador2, valor)
    opcoes = [discord.SelectOption(label=jogador1.display_name, value=str(jogador1.id)),
              discord.SelectOption(label=jogador2.display_name, value=str(jogador2.id))]
    view.select_ganhador.options = opcoes
    view.select_perdedor.options = opcoes
    await interaction.response.send_message(embed=discord.Embed(title="🏁 FINALIZAR APOSTA FÚRIA", color=0x95A5A6), view=view)

@bot.event
async def on_ready(): print(f"🚀 ORG FÚRIA ONLINE: {bot.user.name}")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Sincronizado!")

keep_alive()
bot.run(os.environ['TOKEN'])
