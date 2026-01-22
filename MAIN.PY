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
salas_ativas = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1"]

# --- VIEW DE FINALIZAÇÃO (WIN) ---
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
        await interaction.response.send_message(f"✅ Ganhador definido: {self.ganhador.mention}", ephemeral=True)

    @discord.ui.select(placeholder="💀 Selecione o Perdedor")
    async def select_perdedor(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.perdedor = interaction.guild.get_member(int(select.values[0]))
        await interaction.response.send_message(f"✅ Perdedor definido: {self.perdedor.mention}", ephemeral=True)

    @discord.ui.button(label="Finalizar Aposta 🏁", style=discord.ButtonStyle.danger)
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ganhador or not self.perdedor:
            return await interaction.response.send_message("❌ Selecione ambos os jogadores!", ephemeral=True)
        
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
            embed_res = discord.Embed(title="🏆 APOSTA FINALIZADA", color=0x00FF00)
            embed_res.add_field(name="👑 Vencedor", value=self.ganhador.mention, inline=True)
            embed_res.add_field(name="💀 Perdedor", value=self.perdedor.mention, inline=True)
            embed_res.add_field(name="💰 Valor", value=f"R$ {self.valor},00", inline=False)
            await canal_res.send(embed=embed_res)

        await interaction.followup.send("✅ Registrado! Fechando tópico...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- VIEW: FILA PADRÃO FÚRIA (COM @ E AUTO-PURGE) ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, modalidade):
        super().__init__(timeout=None)
        self.valor = valor
        self.modalidade = modalidade

    async def gerenciar_fila(self, interaction, tipo_gelo):
        bl = carregar_blacklist()
        if str(interaction.user.id) in bl:
            return await interaction.response.send_message("❌ Você está na Blacklist!", ephemeral=True)

        chave = (interaction.channel.id, self.valor, tipo_gelo)
        if chave not in dados_filas_memoria: dados_filas_memoria[chave] = []
        
        fila = dados_filas_memoria[chave]
        if interaction.user in fila:
            return await interaction.response.send_message("❌ Você já está nesta fila!", ephemeral=True)

        fila.append(interaction.user)
        
        # Atualiza a Embed com menção @
        jogadores_str = "\n".join([p.mention for p in fila])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="Jogadores:", value=jogadores_str, inline=False)
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ Você entrou na fila de R$ {self.valor}!", ephemeral=True)

        if len(fila) >= 2: # Puxa com 2 líderes
            p1, p2 = fila.pop(0), fila.pop(0)
            
            # Reset visual da fila
            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)

            canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_res:
                msg = await canal_res.send(f"⚠️ **PARTIDA ENCONTRADA:** {p1.mention} **VS** {p2.mention}")
                thread = await msg.create_thread(name=f"💸 {self.modalidade} | R${self.valor}")
                
                view_conf = ViewConfirmacaoAposta(p1, p2, self.valor)
                await thread.send(content=f"{p1.mention} {p2.mention}\n**Modalidade:** {self.modalidade}\n**Gelo:** {tipo_gelo}", view=view_conf)

    @discord.ui.button(label="Gelo Normal", style=discord.ButtonStyle.secondary, emoji="🧊")
    async def gelo_normal(self, i, b): await self.gerenciar_fila(i, "Gelo Normal")

    @discord.ui.button(label="Gelo Infinito", style=discord.ButtonStyle.secondary, emoji="♾️")
    async def gelo_infinito(self, i, b): await self.gerenciar_fila(i, "Gelo Infinito")

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair(self, interaction, button):
        removido = False
        for chave in dados_filas_memoria:
            if interaction.user in dados_filas_memoria[chave]:
                dados_filas_memoria[chave].remove(interaction.user)
                removido = True
                f = dados_filas_memoria[chave]
                txt = "\n".join([p.mention for p in f]) if f else "Nenhum jogador na fila"
                embed = interaction.message.embeds[0]
                embed.set_field_at(1, name="Jogadores:", value=txt, inline=False)
                await interaction.message.edit(embed=embed)
        
        msg = "✅ Saiu da fila!" if removido else "❌ Você não estava na fila."
        await interaction.response.send_message(msg, ephemeral=True)

# --- VIEWS AUXILIARES (PIX, CENTRAL, CONFIRMAÇÃO) ---
class ModalCadastroPix(discord.ui.Modal, title='📄 Cadastro de Mediador'):
    nome = discord.ui.TextInput(label='Nome Completo')
    banco = discord.ui.TextInput(label='Banco')
    chave = discord.ui.TextInput(label='Chave Pix')
    async def on_submit(self, interaction: discord.Interaction):
        mediadores_dados[interaction.user.id] = {"nome": self.nome.value, "banco": self.banco.value, "chave": self.chave.value}
        await interaction.response.send_message(f"✅ Dados salvos!", ephemeral=True)

class ViewConfirmacaoAposta(discord.ui.View):
    def __init__(self, p1, p2, valor):
        super().__init__(timeout=None)
        self.p1, self.p2, self.valor = p1, p2, valor
        self.confirmado = {p1.id: False, p2.id: False}

    @discord.ui.button(label="Confirmar ✅", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction, button):
        if interaction.user.id not in [self.p1.id, self.p2.id]: return
        self.confirmado[interaction.user.id] = True
        await interaction.response.send_message(f"{interaction.user.mention} confirmou!", ephemeral=False)
        
        if all(self.confirmado.values()):
            mid = random.choice(fila_mediadores) if fila_mediadores else None
            dpix = mediadores_dados.get(mid) if mid else None
            muser = interaction.guild.get_member(mid) if mid else None
            
            embed = discord.Embed(title="✅ PAGAMENTO LIBERADO", color=0xF1C40F)
            if muser: embed.add_field(name="👮 Mediador", value=muser.mention, inline=False)
            if dpix: embed.add_field(name="🔑 Pix (Copia e Cola)", value=f"```{dpix['chave']}```", inline=False)
            embed.set_footer(text="Envie o comprovante abaixo.")
            await interaction.channel.send(embed=embed)

class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ficar Online", style=discord.ButtonStyle.success)
    async def entrar_med(self, interaction, button):
        if interaction.user.id not in mediadores_dados: return await interaction.response.send_message("❌ Cadastre o Pix!", ephemeral=True)
        if interaction.user.id not in fila_mediadores: fila_mediadores.append(interaction.user.id)
        await interaction.response.send_message("✅ Você está Online!", ephemeral=True)
    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary)
    async def cad_pix(self, interaction, button): await interaction.response.send_modal(ModalCadastroPix())

# --- COMANDOS SLASH ---
@bot.tree.command(name="atualizar_filas", description="Limpa o canal e gera as filas da Fúria")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Limpando e gerando filas...", ephemeral=True)
    nome_canal = interaction.channel.name.lower()
    
    plataforma = "Emulador" if "emulador" in nome_canal else "Mobile"
    x = "1v1" if "x1" in nome_canal else "2v2" if "x2" in nome_canal else "3v3" if "x3" in nome_canal else "4v4"
    mod_final = f"{x} {plataforma}" # Ex: 1v1 Mobile

    await interaction.channel.purge(limit=100) # Apaga tudo antes de mandar

    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500)
        embed.title = mod_final
        embed.add_field(name="Valor:", value=f"R$ {v},00", inline=False)
        embed.add_field(name="Jogadores:", value="Nenhum jogador na fila", inline=False)
        embed.set_footer(text="Fúria Apostas - System Labs") # Padrão Fúria
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, mod_final))

@bot.tree.command(name="win")
@app_commands.checks.has_role("ADM")
async def win(interaction: discord.Interaction, jogador1: discord.Member, jogador2: discord.Member, valor: str):
    opcoes = [discord.SelectOption(label=jogador1.display_name, value=str(jogador1.id)),
              discord.SelectOption(label=jogador2.display_name, value=str(jogador2.id))]
    view = ViewFinalizarWin(jogador1, jogador2, valor)
    view.select_ganhador.options = opcoes
    view.select_perdedor.options = opcoes
    await interaction.response.send_message(embed=discord.Embed(title="🏁 FINALIZAR PARTIDA", color=0x95A5A6), view=view)

@bot.tree.command(name="p")
async def perfil(interaction: discord.Interaction, membro: discord.Member = None):
    membro = membro or interaction.user
    stats = carregar_dados('stats.json')
    d = stats.get(str(membro.id), {"vitorias": 0, "derrotas": 0, "streak": 0})
    embed = discord.Embed(title=f"📊 Perfil: {membro.display_name}", color=0x00AAFF)
    embed.add_field(name="🏆 Vitórias", value=str(d['vitorias']))
    embed.add_field(name="💀 Derrotas", value=str(d['derrotas']))
    embed.add_field(name="🔥 Streak", value=str(d['streak']))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ranking")
async def ranking(interaction: discord.Interaction):
    stats = carregar_dados('stats.json')
    if not stats: return await interaction.response.send_message("Sem dados.")
    ranking_ord = sorted(stats.items(), key=lambda item: item[1]['vitorias'], reverse=True)[:10]
    txt = "\n".join([f"**{i}.** <@{uid}> — {d['vitorias']} VIT" for i, (uid, d) in enumerate(ranking_ord, 1)])
    await interaction.response.send_message(embed=discord.Embed(title="🏆 RANKING FÚRIA", description=txt, color=0xF1C40F))

@bot.tree.command(name="central")
async def central(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="🛡️ CENTRAL DE MEDIADORES"), view=ViewCentral())

# --- BOOT ---
@bot.event
async def on_ready():
    bot.add_view(ViewCentral())
    print("✅ SISTEMA FÚRIA ONLINE E UNIFICADO")

@bot.command()
async def sync(ctx):
    fmt = await bot.tree.sync()
    await ctx.send(f"✅ {len(fmt)} comandos sincronizados!")

keep_alive()
bot.run(os.environ['TOKEN'])
