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

# --- SISTEMA DE ARQUIVOS (JSON) ---
def carregar_dados(arquivo):
    try:
        with open(arquivo, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def salvar_dados(arquivo, dados):
    with open(arquivo, 'w') as f:
        json.dump(dados, f, indent=4)

def carregar_blacklist(): return carregar_dados('blacklist.json')
def salvar_blacklist(dados): salvar_dados('blacklist.json', dados)

# --- KEEP ALIVE PARA RENDER ---
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
dados_filas_jogadores = {} 
salas_ativas = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- MODAL CADASTRO PIX ---
class ModalCadastroPix(discord.ui.Modal, title='Cadastro de Mediador'):
    nome = discord.ui.TextInput(label='Nome Completo', placeholder='Seu nome...')
    banco = discord.ui.TextInput(label='Banco', placeholder='Ex: Nubank...')
    chave = discord.ui.TextInput(label='Chave Pix', placeholder='Sua chave...')

    async def on_submit(self, interaction: discord.Interaction):
        mediadores_dados[interaction.user.id] = {
            "nome": self.nome.value,
            "banco": self.banco.value,
            "chave": self.chave.value
        }
        await interaction.response.send_message(f"✅ Dados Pix salvos com sucesso!", ephemeral=True)

# --- VIEW CONFIRMAÇÃO DA APOSTA ---
class ViewConfirmacaoAposta(discord.ui.View):
    def __init__(self, p1, p2, valor):
        super().__init__(timeout=None)
        self.p1, self.p2, self.valor = p1, p2, valor
        self.confirmado = {p1.id: False, p2.id: False}
        self.finalizado = False

    @discord.ui.button(label="Confirmar ✅", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction, button):
        if self.finalizado: return
        if interaction.user.id not in [self.p1.id, self.p2.id]:
            return await interaction.response.send_message("Tu não fazes parte desta aposta!", ephemeral=True)

        self.confirmado[interaction.user.id] = True
        await interaction.response.send_message(f"{interaction.user.mention} confirmou!", ephemeral=False)

        if all(self.confirmado.values()):
            self.finalizado = True
            self.stop()
            
            # Sorteio de Mediador
            mediador_id = random.choice(fila_mediadores) if fila_mediadores else None
            mediador_user = interaction.guild.get_member(mediador_id) if mediador_id else None
            dados_pix = mediadores_dados.get(mediador_id) if mediador_id else None

            # Criar Canal de Voz
            categoria = discord.utils.get(interaction.guild.categories, name="SALAS DE APOSTA") or await interaction.guild.create_category("SALAS DE APOSTA")
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(connect=False),
                self.p1: discord.PermissionOverwrite(connect=True, speak=True),
                self.p2: discord.PermissionOverwrite(connect=True, speak=True)
            }
            canal_voz = await interaction.guild.create_voice_channel(name=f"🎙️ {self.p1.display_name} vs {self.p2.display_name}", category=categoria, overwrites=overwrites)
            salas_ativas[f"{self.p1.id}-{self.p2.id}"] = canal_voz.id

            embed = discord.Embed(title="✅ PAGAMENTO LIBERADO", color=0x00FF00)
            if mediador_user: embed.add_field(name="👮 Mediador", value=mediador_user.mention, inline=False)
            if dados_pix:
                embed.add_field(name="🏦 Banco", value=dados_pix['banco'], inline=True)
                embed.add_field(name="🔑 Pix", value=f"```{dados_pix['chave']}```", inline=True)
            embed.add_field(name="🔊 Sala de Voz", value=canal_voz.mention, inline=False)
            
            await interaction.channel.send(content=f"{self.p1.mention} {self.p2.mention}", embed=embed)

# --- VIEW CENTRAL (MEDIADORES) ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar_med(self, interaction, button):
        if interaction.user.id not in mediadores_dados: return await interaction.response.send_message("❌ Cadastra o Pix!", ephemeral=True)
        if interaction.user.id not in fila_mediadores: fila_mediadores.append(interaction.user.id); await interaction.response.send_message("Entraste na fila!", ephemeral=True)
    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💸")
    async def cad_pix(self, interaction, button): await interaction.response.send_modal(ModalCadastroPix())

# --- VIEW JOGADORES ---
class ViewFilaJogadores(discord.ui.View):
    def __init__(self, valor, modo):
        super().__init__(timeout=None)
        self.valor, self.modo = valor, modo

    @discord.ui.button(label="Entrar na Fila ✅", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, button):
        bl = carregar_blacklist()
        if str(interaction.user.id) in bl:
            return await interaction.response.send_message("❌ Estás na BLACKLIST!", ephemeral=True)

        chave = (interaction.channel.id, self.valor)
        if chave not in dados_filas_jogadores: dados_filas_jogadores[chave] = []
        fila = dados_filas_jogadores[chave]
        
        if interaction.user in fila: return await interaction.response.send_message("Já estás na fila!", ephemeral=True)
        
        fila.append(interaction.user)
        await interaction.response.send_message(f"Entraste na fila de R$ {self.valor}!", ephemeral=True)

        if len(fila) >= 2:
            p1, p2 = fila.pop(0), fila.pop(0)
            canal_dest = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_dest:
                msg = await canal_dest.send(f"⚠️ **Aposta Iniciada:** {p1.mention} vs {p2.mention}")
                thread = await msg.create_thread(name=f"R${self.valor} - {p1.display_name} vs {p2.display_name}")
                await thread.send(content=f"{p1.mention} {p2.mention}", view=ViewConfirmacaoAposta(p1, p2, self.valor))

# --- COMANDOS DE TEXTO (!) ---
@bot.command(name="p")
async def perfil(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    stats = carregar_dados('stats.json')
    uid = str(membro.id)
    if uid not in stats: return await ctx.send(f"❌ {membro.display_name} não tem histórico.")
    d = stats[uid]
    total = d['vitorias'] + d['derrotas']
    wr = (d['vitorias'] / total * 100) if total > 0 else 0
    embed = discord.Embed(title=f"📊 Status de {membro.display_name}", color=0x00AAFF)
    embed.add_field(name="🏆 Vitórias", value=str(d['vitorias']), inline=True)
    embed.add_field(name="💀 Derrotas", value=str(d['derrotas']), inline=True)
    embed.add_field(name="🔥 Streak", value=f"{d['streak']} vitórias", inline=True)
    embed.add_field(name="📈 Winrate", value=f"{wr:.1f}%", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="win")
@commands.has_role("ADM")
async def win(ctx, ganhador: discord.Member, perdedor: discord.Member, valor: str):
    stats = carregar_dados('stats.json')
    for u in [ganhador, perdedor]:
        if str(u.id) not in stats: stats[str(u.id)] = {"vitorias": 0, "derrotas": 0, "streak": 0}
    
    stats[str(ganhador.id)]["vitorias"] += 1
    stats[str(ganhador.id)]["streak"] += 1
    stats[str(perdedor.id)]["derrotas"] += 1
    stats[str(perdedor.id)]["streak"] = 0
    salvar_dados('stats.json', stats)

    # Limpar sala de voz
    chave1, chave2 = f"{ganhador.id}-{perdedor.id}", f"{perdedor.id}-{ganhador.id}"
    sala_id = salas_ativas.pop(chave1, salas_ativas.pop(chave2, None))
    if sala_id:
        canal = ctx.guild.get_channel(sala_id)
        if canal: await canal.delete()

    embed = discord.Embed(title="🏆 FIM DA APOSTA", color=0x00FF00)
    embed.add_field(name="👑 Vencedor", value=ganhador.mention, inline=True)
    embed.add_field(name="💀 Perdedor", value=perdedor.mention, inline=True)
    embed.add_field(name="💰 Valor", value=f"R$ {valor}", inline=False)
    
    canal_res = discord.utils.get(ctx.guild.text_channels, name="seus-apostados-aqui📌")
    if canal_res: await canal_res.send(embed=embed)
    await ctx.send(f"✅ Vitória registada! Streak de {ganhador.display_name}: {stats[str(ganhador.id)]['streak']}")

# --- COMANDOS SLASH (/) ---
@bot.tree.command(name="blacklist", description="Bane um jogador")
@app_commands.checks.has_permissions(administrator=True)
async def blacklist(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    bl = carregar_blacklist()
    expira = (datetime.datetime.now() + datetime.timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
    bl[str(usuario.id)] = {"nome": usuario.name, "motivo": motivo, "expira": expira}
    salvar_blacklist(bl); await interaction.response.send_message(f"🚫 {usuario.mention} banido!")

@bot.tree.command(name="removebl", description="Remove da blacklist")
@app_commands.checks.has_permissions(administrator=True)
async def removebl(interaction: discord.Interaction, usuario: discord.Member):
    bl = carregar_blacklist()
    if str(usuario.id) in bl:
        del bl[str(usuario.id)]; salvar_blacklist(bl)
        await interaction.response.send_message(f"✅ {usuario.mention} removido!")

@bot.tree.command(name="central", description="Painel Mediadores")
async def central(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="🛡️ CENTRAL", description="Use os botões abaixo"), view=ViewCentral())

@bot.tree.command(name="atualizar_filas", description="Gera painéis")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Gerando...", ephemeral=True)
    canais = [c for c in interaction.guild.text_channels if "fila" in c.name.lower()]
    for canal in canais:
        await canal.purge(limit=50)
        for v in valores_lista:
            await canal.send(embed=discord.Embed(title="⚔️ APOSTADO", description=f"Valor: R$ {v},00"), view=ViewFilaJogadores(v, "Aposta"))

@bot.event
async def on_ready():
    bot.add_view(ViewCentral())
    print("✅ BOT ONLINE")

@bot.command()
async def sync(ctx):
    fmt = await bot.tree.sync()
    await ctx.send(f"✅ {len(fmt)} comandos sincronizados!")

keep_alive()
bot.run(os.environ['TOKEN'])
