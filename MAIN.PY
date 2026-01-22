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
dados_filas_jogadores = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- MODAL CADASTRO PIX (MEDIADOR) ---
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
            if not fila_mediadores:
                await interaction.channel.send("⚠️ **ATENÇÃO:** Nenhum mediador online!")
            else:
                mediador_id = random.choice(fila_mediadores)
                dados_pix = mediadores_dados.get(mediador_id)
                mediador_user = interaction.guild.get_member(mediador_id)
                embed = discord.Embed(title="✅ PAGAMENTO LIBERADO", color=0x00FF00)
                if mediador_user: embed.add_field(name="👮 Mediador", value=mediador_user.mention, inline=False)
                if dados_pix:
                    embed.add_field(name="🏦 Banco", value=dados_pix['banco'], inline=True)
                    embed.add_field(name="🔑 Chave Pix", value=f"```{dados_pix['chave']}```", inline=True)
                embed.set_footer(text=f"Valor Total: R$ {self.valor},00")
                await interaction.channel.send(content=f"{self.p1.mention} {self.p2.mention}", embed=embed)

    @discord.ui.button(label="Cancelar ❌", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction, button):
        if interaction.user.id in [self.p1.id, self.p2.id]:
            self.finalizado = True
            await interaction.channel.send(f"❌ Aposta cancelada.")
            await asyncio.sleep(5)
            await interaction.channel.delete()

# --- VIEW CENTRAL (MEDIADORES) ---
class ViewCentral(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def atualizar_central(self, interaction):
        lista_str = "\n".join([f"• <@{m_id}>" for m_id in fila_mediadores]) if fila_mediadores else "Nenhum mediador online."
        embed = interaction.message.embeds[0]
        embed.clear_fields()
        embed.add_field(name="🎧 Mediadores Disponíveis", value=lista_str, inline=False)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar_med(self, interaction, button):
        if interaction.user.id not in mediadores_dados:
            return await interaction.response.send_message("❌ Cadastra o teu Pix!", ephemeral=True)
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            await interaction.response.send_message("Entraste na fila!", ephemeral=True)
            await self.atualizar_central(interaction)

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair_med(self, interaction, button):
        if interaction.user.id in fila_mediadores:
            fila_mediadores.remove(interaction.user.id)
            await interaction.response.send_message("Saíste da fila!", ephemeral=True)
            await self.atualizar_central(interaction)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💸")
    async def cad_pix(self, interaction, button):
        await interaction.response.send_modal(ModalCadastroPix())

# --- VIEW JOGADORES ---
class ViewFilaJogadores(discord.ui.View):
    def __init__(self, valor, modo_texto):
        super().__init__(timeout=None)
        self.valor, self.modo_texto = valor, modo_texto

    async def atualizar_embed(self, interaction, fila):
        jogadores_str = "\n".join([p.mention for p in fila]) if fila else "Ninguém"
        embed = interaction.message.embeds[0]
        embed.clear_fields()
        embed.add_field(name="💰 Valor", value=f"R$ {self.valor},00", inline=True)
        embed.add_field(name="👥 Aguardando", value=jogadores_str, inline=True)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Entrar na Fila ✅", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, button):
        bl = carregar_blacklist()
        if str(interaction.user.id) in bl:
            expira_dt = datetime.datetime.strptime(bl[str(interaction.user.id)]['expira'], "%Y-%m-%d %H:%M")
            if datetime.datetime.now() < expira_dt:
                return await interaction.response.send_message(f"❌ Estás na BLACKLIST até {bl[str(interaction.user.id)]['expira']}", ephemeral=True)

        chave = (interaction.channel.id, self.valor)
        if chave not in dados_filas_jogadores: dados_filas_jogadores[chave] = []
        fila = dados_filas_jogadores[chave]
        if interaction.user in fila: return await interaction.response.send_message("Já estás na fila!", ephemeral=True)

        fila.append(interaction.user)
        await interaction.response.send_message("Entraste na fila!", ephemeral=True)
        await self.atualizar_embed(interaction, fila)

        if len(fila) >= 2:
            p1, p2 = fila.pop(0), fila.pop(0)
            await self.atualizar_embed(interaction, fila)
            canal_dest = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_dest:
                msg = await canal_dest.send(f"⚠️ **Aposta Iniciada:** {p1.mention} vs {p2.mention}")
                thread = await msg.create_thread(name=f"R${self.valor} - {p1.display_name} vs {p2.display_name}")
                await thread.send(content=f"{p1.mention} {p2.mention}", view=ViewConfirmacaoAposta(p1, p2, self.valor))

    @discord.ui.button(label="Sair da Fila ❌", style=discord.ButtonStyle.danger)
    async def sair(self, interaction, button):
        chave = (interaction.channel.id, self.valor)
        fila = dados_filas_jogadores.get(chave, [])
        if interaction.user in fila:
            fila.remove(interaction.user)
            await self.atualizar_embed(interaction, fila)
            await interaction.response.send_message("Saíste da fila.", ephemeral=True)

# --- COMANDOS DE ESTATÍSTICAS (!p) ---
@bot.command(name="p")
async def perfil(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    stats = carregar_dados('stats.json')
    uid = str(membro.id)
    
    if uid not in stats:
        return await ctx.send(f"❌ {membro.display_name} não possui registros.")
    
    d = stats[uid]
    total = d['vitorias'] + d['derrotas']
    wr = (d['vitorias'] / total * 100) if total > 0 else 0
    
    embed = discord.Embed(title=f"📊 Status de {membro.display_name}", color=0x00AAFF)
    embed.add_field(name="🏆 Vitórias", value=str(d['vitorias']), inline=True)
    embed.add_field(name="💀 Derrotas", value=str(d['derrotas']), inline=True)
    embed.add_field(name="🔥 Streak", value=f"{d['streak']} vitórias", inline=True)
    embed.add_field(name="📈 Winrate", value=f"{wr:.1f}%", inline=True)
    embed.set_thumbnail(url=membro.display_avatar.url)
    await ctx.send(embed=embed)

# --- COMANDOS SLASH ---
@bot.event
async def on_ready():
    bot.add_view(ViewCentral())
    print(f'✅ SISTEMA ONLINE')

@bot.command()
async def sync(ctx):
    fmt = await bot.tree.sync()
    await ctx.send(f"✅ {len(fmt)} comandos sincronizados!")

@bot.tree.command(name="win", description="Registra vitória e atualiza estatísticas")
@app_commands.checks.has_role("ADM")
async def win(interaction: discord.Interaction, ganhador: discord.Member, perdedor: discord.Member, valor: str):
    await interaction.response.defer(ephemeral=True)
    stats = carregar_dados('stats.json')
    
    for u in [ganhador, perdedor]:
        if str(u.id) not in stats: stats[str(u.id)] = {"vitorias": 0, "derrotas": 0, "streak": 0}
    
    stats[str(ganhador.id)]["vitorias"] += 1
    stats[str(ganhador.id)]["streak"] += 1
    stats[str(perdedor.id)]["derrotas"] += 1
    stats[str(perdedor.id)]["streak"] = 0
    salvar_dados('stats.json', stats)

    canal = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
    embed = discord.Embed(title="🏆 RESULTADO DA APOSTA", color=0x00FF00)
    embed.add_field(name="👑 Vencedor", value=ganhador.mention, inline=True)
    embed.add_field(name="💀 Perdedor", value=perdedor.mention, inline=True)
    embed.add_field(name="💰 Valor", value=f"R$ {valor}", inline=False)
    embed.set_footer(text=f"Streak do Vencedor: {stats[str(ganhador.id)]['streak']}")
    await canal.send(embed=embed)
    await interaction.followup.send("✅ Vitória registrada!")

@bot.tree.command(name="blacklist", description="Bane um jogador")
@app_commands.checks.has_permissions(administrator=True)
async def blacklist(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    bl = carregar_blacklist()
    data = (datetime.datetime.now() + datetime.timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
    bl[str(usuario.id)] = {"nome": usuario.name, "motivo": motivo, "expira": data}
    salvar_blacklist(bl)
    await interaction.response.send_message(f"🚫 {usuario.mention} banido até {data}")

@bot.tree.command(name="removebl", description="Remove da blacklist")
@app_commands.checks.has_permissions(administrator=True)
async def removebl(interaction: discord.Interaction, usuario: discord.Member):
    bl = carregar_blacklist()
    if str(usuario.id) in bl:
        del bl[str(usuario.id)]; salvar_blacklist(bl)
        await interaction.response.send_message(f"✅ {usuario.mention} removido!")

@bot.tree.command(name="central", description="Painel Mediadores")
async def central(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ CENTRAL DE MEDIADORES", color=0x2f3136)
    embed.add_field(name="🎧 Mediadores", value="Nenhum online.", inline=False)
    await interaction.response.send_message(embed=embed, view=ViewCentral())

@bot.tree.command(name="atualizar_filas", description="Gera painéis")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Gerando...", ephemeral=True)
    canais = [c for c in interaction.guild.text_channels if "fila" in c.name.lower()]
    for canal in canais:
        await canal.purge(limit=50)
        for v in valores_lista:
            embed = discord.Embed(title="⚔️ APOSTADO", color=0xFF4500)
            embed.add_field(name="💰 Valor", value=f"R$ {v},00", inline=True)
            embed.add_field(name="👥 Aguardando", value="Ninguém", inline=True)
            await canal.send(embed=embed, view=ViewFilaJogadores(v, "Aposta"))

keep_alive()
bot.run(os.environ['TOKEN'])
