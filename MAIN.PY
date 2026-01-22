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
def salvar_blacklist(dados): salvar_dados('blacklist.json', dados)

# --- KEEP ALIVE (PARA RENDER/UPTIME) ---
app = Flask('')
@app.route('/')
def home(): return "Bot Furia Online!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURAÇÃO DO BOT ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

mediadores_dados = {} 
fila_mediadores = [] 
dados_filas_jogadores = {} 
salas_ativas = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- VIEW: FINALIZAÇÃO DE APOSTA (/WIN) ---
class ViewFinalizarWin(discord.ui.View):
    def __init__(self, p1, p2, valor_aposta):
        super().__init__(timeout=None)
        self.p1, self.p2 = p1, p2
        self.valor = valor_aposta
        self.ganhador = None
        self.perdedor = None

    @discord.ui.select(placeholder="🥇 Selecionar o Vencedor da Partida...")
    async def select_ganhador(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.ganhador = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Ganhador definido: **{self.ganhador.display_name}**", ephemeral=True)

    @discord.ui.select(placeholder="💀 Selecionar o Perdedor da Partida...")
    async def select_perdedor(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.perdedor = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Perdedor definido: **{self.perdedor.display_name}**", ephemeral=True)

    @discord.ui.button(label="FINALIZAR E REGISTRAR", style=discord.ButtonStyle.danger, emoji="🔒")
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ganhador or not self.perdedor:
            return await interaction.response.send_message("❌ Erro: Selecione ambos os jogadores!", ephemeral=True)
        
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
        embed_res = discord.Embed(title="🏁 RESULTADO REGISTRADO", color=0x2ECC71, timestamp=datetime.datetime.now())
        embed_res.add_field(name="👑 Vencedor", value=f"{self.ganhador.mention}\n`Streak: {stats[str(self.ganhador.id)]['streak']}🔥`", inline=True)
        embed_res.add_field(name="💀 Perdedor", value=f"{self.perdedor.mention}\n`Derrota`", inline=True)
        embed_res.add_field(name="💰 Valor", value=f"```R$ {self.valor},00```", inline=False)
        embed_res.set_footer(text="Fúria Apostas | Sistema Automatizado")
        
        if canal_res: await canal_res.send(embed=embed_res)

        chave_voz = f"{self.p1.id}-{self.p2.id}"
        sala_id = salas_ativas.pop(chave_voz, salas_ativas.pop(f"{self.p2.id}-{self.p1.id}", None))
        if sala_id:
            cv = interaction.guild.get_channel(sala_id)
            if cv: await cv.delete()

        await interaction.followup.send("🚨 **Aposta encerrada com sucesso!** O tópico será deletado em 5s.")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- MODAL: CADASTRO PIX ---
class ModalCadastroPix(discord.ui.Modal, title='📄 Cadastro de Mediador'):
    nome = discord.ui.TextInput(label='Nome Completo', placeholder='Seu nome real...')
    banco = discord.ui.TextInput(label='Banco', placeholder='Ex: Nubank, Inter...')
    chave = discord.ui.TextInput(label='Chave Pix', placeholder='Sua chave para receber...')
    async def on_submit(self, interaction: discord.Interaction):
        mediadores_dados[interaction.user.id] = {"nome": self.nome.value, "banco": self.banco.value, "chave": self.chave.value}
        await interaction.response.send_message(f"✅ Seus dados de pagamento foram salvos!", ephemeral=True)

# --- VIEW: CONFIRMAÇÃO NO TÓPICO ---
class ViewConfirmacaoAposta(discord.ui.View):
    def __init__(self, p1, p2, valor):
        super().__init__(timeout=None)
        self.p1, self.p2, self.valor = p1, p2, valor
        self.confirmado = {p1.id: False, p2.id: False}

    @discord.ui.button(label="ACEITAR DESAFIO", style=discord.ButtonStyle.success, emoji="⚔️")
    async def confirmar(self, interaction, button):
        if interaction.user.id not in [self.p1.id, self.p2.id]: return
        self.confirmado[interaction.user.id] = True
        await interaction.response.send_message(f"✅ {interaction.user.mention} confirmou!", ephemeral=False)
        
        if all(self.confirmado.values()):
            mid = random.choice(fila_mediadores) if fila_mediadores else None
            muser = interaction.guild.get_member(mid) if mid else None
            dpix = mediadores_dados.get(mid) if mid else None
            
            cat = discord.utils.get(interaction.guild.categories, name="SALAS DE APOSTA") or await interaction.guild.create_category("SALAS DE APOSTA")
            cv = await interaction.guild.create_voice_channel(name=f"🎙️ X1 R${self.valor}", category=cat)
            salas_ativas[f"{self.p1.id}-{self.p2.id}"] = cv.id
            
            embed = discord.Embed(title="🏦 PAGAMENTO LIBERADO", color=0xF1C40F)
            embed.description = "Realizem o pagamento para o mediador abaixo para iniciar."
            if muser: embed.add_field(name="👮 Mediador", value=muser.mention, inline=False)
            if dpix: embed.add_field(name="🔑 Pix (Copia e Cola)", value=f"```{dpix['chave']}```", inline=False)
            embed.add_field(name="🔊 Canal de Voz", value=cv.mention, inline=False)
            await interaction.channel.send(embed=embed)

# --- VIEW: CENTRAL DE MEDIADORES ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ficar Online", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar_med(self, interaction, button):
        if interaction.user.id not in mediadores_dados: return await interaction.response.send_message("❌ Cadastre seu Pix primeiro!", ephemeral=True)
        if interaction.user.id not in fila_mediadores: fila_mediadores.append(interaction.user.id); await interaction.response.send_message("Você está ONLINE!", ephemeral=True)
    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💸")
    async def cad_pix(self, interaction, button): await interaction.response.send_modal(ModalCadastroPix())

# --- VIEW: FILA DE JOGADORES ---
class ViewFilaJogadores(discord.ui.View):
    def __init__(self, valor):
        super().__init__(timeout=None)
        self.valor = valor
    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.secondary, emoji="✅")
    async def entrar(self, interaction, button):
        bl = carregar_blacklist()
        if str(interaction.user.id) in bl: return await interaction.response.send_message("🚫 Você está na Blacklist!", ephemeral=True)
        chave = (interaction.channel.id, self.valor)
        if chave not in dados_filas_jogadores: dados_filas_jogadores[chave] = []
        if interaction.user not in dados_filas_jogadores[chave]:
            dados_filas_jogadores[chave].append(interaction.user)
            await interaction.response.send_message(f"✅ Você entrou na fila de R$ {self.valor}!", ephemeral=True)
            if len(dados_filas_jogadores[chave]) >= 2:
                p1, p2 = dados_filas_jogadores[chave].pop(0), dados_filas_jogadores[chave].pop(0)
                canal_dest = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
                if canal_dest:
                    msg = await canal_dest.send(f"⚠️ **PARTIDA ENCONTRADA:** {p1.mention} vs {p2.mention}")
                    thread = await msg.create_thread(name=f"💸 R${self.valor} | {p1.display_name} vs {p2.display_name}")
                    await thread.send(content=f"{p1.mention} {p2.mention}", view=ViewConfirmacaoAposta(p1, p2, self.valor))

# --- COMANDOS SLASH (/) ---

@bot.tree.command(name="p", description="Ver o seu perfil de apostador")
async def p(interaction: discord.Interaction, membro: discord.Member = None):
    membro = membro or interaction.user
    stats = carregar_dados('stats.json')
    d = stats.get(str(membro.id), {"vitorias": 0, "derrotas": 0, "streak": 0})
    total = d['vitorias'] + d['derrotas']
    wr = (d['vitorias'] / total * 100) if total > 0 else 0
    embed = discord.Embed(title=f"📊 STATUS DE ATLETA", color=0x3498DB)
    embed.set_author(name=membro.display_name, icon_url=membro.display_avatar.url)
    embed.add_field(name="🏆 Vitórias", value=f"**{d['vitorias']}**", inline=True)
    embed.add_field(name="💀 Derrotas", value=f"**{d['derrotas']}**", inline=True)
    embed.add_field(name="🔥 Streak", value=f"**{d['streak']}**", inline=True)
    embed.add_field(name="📈 Winrate", value=f"**{wr:.1f}%**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ranking", description="Top 10 do Servidor")
async def ranking(interaction: discord.Interaction):
    stats = carregar_dados('stats.json')
    if not stats: return await interaction.response.send_message("❌ Sem dados.", ephemeral=True)
    ranking_ord = sorted(stats.items(), key=lambda item: item[1]['vitorias'], reverse=True)[:10]
    embed = discord.Embed(title="🏆 RANKING DE ELITE", color=0xF1C40F)
    desc = "```🏆 Pos | Jogador          | VIT```\n"
    for i, (uid, d) in enumerate(ranking_ord, 1):
        emoji = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        desc += f"{emoji} `{i:02d}` | <@{uid}> | `{d['vitorias']:02d}`\n"
    embed.description = desc
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="win", description="Finalizar aposta (Apenas ADM)")
@app_commands.checks.has_role("ADM")
async def win(interaction: discord.Interaction, jogador1: discord.Member, jogador2: discord.Member, valor: str):
    opcoes = [
        discord.SelectOption(label=jogador1.display_name, value=str(jogador1.id), emoji="👤"),
        discord.SelectOption(label=jogador2.display_name, value=str(jogador2.id), emoji="👤")
    ]
    view = ViewFinalizarWin(jogador1, jogador2, valor)
    view.select_ganhador.options = opcoes
    view.select_perdedor.options = opcoes
    embed = discord.Embed(title="⚙️ PAINEL DE CONTROLE", description="Selecione os resultados abaixo.", color=0x95A5A6)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="atualizar_filas", description="Gerar painéis de fila")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Gerando painéis...", ephemeral=True)
    canais = [c for c in interaction.guild.text_channels if "fila" in c.name.lower()]
    for canal in canais:
        await canal.purge(limit=50)
        for v in valores_lista:
            embed = discord.Embed(title="⚔️ DISPUTA APOSTADA", color=0xE67E22)
            embed.add_field(name="💰 Valor", value=f"```R$ {v},00```", inline=True)
            embed.set_footer(text="Clique no botão para entrar")
            await canal.send(embed=embed, view=ViewFilaJogadores(v))

@bot.tree.command(name="central")
async def central(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="🛡️ CENTRAL", color=0x2f3136), view=ViewCentral())

# --- BOOT E SYNC ---
@bot.event
async def on_ready():
    bot.add_view(ViewCentral())
    print(f"🚀 {bot.user.name} ONLINE!")

@bot.command()
async def sync(ctx):
    fmt = await bot.tree.sync()
    await ctx.send(f"✅ **{len(fmt)}** comandos sincronizados!")

keep_alive()
bot.run(os.environ['TOKEN'])
