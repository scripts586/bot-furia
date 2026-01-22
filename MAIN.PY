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

# --- KEEP ALIVE (Para o GitHub/Replit não dormir) ---
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
        # Registra as views como persistentes (não morrem no restart)
        self.add_view(ViewCentral())
        print("✅ Views persistentes carregadas!")

bot = FuriaBot()
fila_mediadores = [] 
dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1", "0.50"]

# --- MODAL: CADASTRO DE PIX ---
class ModalPixFuria(discord.ui.Modal, title='💠 CADASTRAR PIX - FÚRIA'):
    chave = discord.ui.TextInput(label='Sua Chave Pix', placeholder='Ex: CPF, Celular ou Aleatória', required=True)
    banco = discord.ui.TextInput(label='Nome do Banco', placeholder='Ex: Nubank, Inter...', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        pix_db = carregar_dados('pix.json')
        pix_db[str(interaction.user.id)] = {"chave": self.chave.value, "banco": self.banco.value}
        salvar_dados('pix.json', pix_db)
        await interaction.response.send_message(f"✅ Pix cadastrado com sucesso!", ephemeral=True)

# --- VIEW: CENTRAL DE MEDIADORES ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅", custom_id="furia_med_in")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True) # Resposta rápida
        pix_db = carregar_dados('pix.json')
        
        if str(interaction.user.id) not in pix_db:
            return await interaction.followup.send("❌ Você precisa cadastrar seu Pix antes!", ephemeral=True)
            
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores])
            embed = interaction.message.embeds[0]
            embed.set_field_at(0, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("✅ Você entrou na fila de mediadores!", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Você já está online!", ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💠", custom_id="furia_med_pix")
    async def cadastrar_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPixFuria())

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌", custom_id="furia_med_out")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id in fila_mediadores:
            fila_mediadores.remove(interaction.user.id)
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores]) if fila_mediadores else "Nenhum mediador online."
            embed = interaction.message.embeds[0]
            embed.set_field_at(0, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("❌ Você saiu da fila!", ephemeral=True)

# --- VIEW: FILAS DE JOGADORES ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, modalidade):
        super().__init__(timeout=None)
        self.valor, self.modalidade = valor, modalidade

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def entrar_fila(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        chave = (interaction.channel.id, self.valor)
        if chave not in dados_filas_memoria: dados_filas_memoria[chave] = []
        fila = dados_filas_memoria[chave]

        if interaction.user in fila:
            return await interaction.followup.send("❌ Você já está na fila!", ephemeral=True)

        fila.append(interaction.user)
        jogadores_str = "\n".join([p.mention for p in fila])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="👥 Jogadores:", value=jogadores_str, inline=False)
        await interaction.message.edit(embed=embed)

        if len(fila) >= 2:
            if not fila_mediadores:
                fila.remove(interaction.user) # Tira o player pra não travar
                return await interaction.followup.send("⚠️ Partida não iniciada! Não há **MEDIADORES ON** na /central.", ephemeral=True)

            p1, p2 = fila.pop(0), fila.pop(0)
            med_id = random.choice(fila_mediadores)
            pix_db = carregar_dados('pix.json')
            dp = pix_db.get(str(med_id), {"chave": "Não cadastrada", "banco": "Não informado"})

            canal_partidas = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_partidas:
                msg = await canal_partidas.send(f"⚠️ **PARTIDA GERADA:** {p1.mention} VS {p2.mention}")
                thread = await msg.create_thread(name=f"⚔️ {self.modalidade} R${self.valor}")
                await thread.send(f"⚔️ **JOGADORES:** {p1.mention} e {p2.mention}\n👮 **MEDIADOR:** <@{med_id}>\n💠 **PIX:** `{dp['chave']}` ({dp['banco']})\n\nUse `/win` para finalizar!")

# --- COMANDOS ---
@bot.tree.command(name="win", description="Finaliza a partida e deleta o canal")
async def win(interaction: discord.Interaction, ganhador: discord.Member, perdedor: discord.Member, valor: str):
    emb = discord.Embed(title="🏁 ORG FÚRIA | RESULTADO", color=0x2ECC71)
    emb.add_field(name="👑 Vencedor", value=ganhador.mention)
    emb.add_field(name="💰 Valor", value=f"R$ {valor}")
    
    canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
    if canal_res: await canal_res.send(embed=emb)
    
    await interaction.response.send_message("✅ Resultado registrado! Deletando canal em 5s...")
    await asyncio.sleep(5)
    await interaction.channel.delete()

@bot.tree.command(name="central", description="Painel de Mediadores")
async def central(interaction: discord.Interaction):
    embed = discord.Embed(title="👮 CENTRAL DE MEDIADORES", color=0xFFA500)
    embed.add_field(name="Mediadores Online:", value="Nenhum mediador online.", inline=False)
    embed.set_footer(text="ORG FÚRIA | SALAS 10 C")
    await interaction.response.send_message(embed=embed, view=ViewCentral())

@bot.tree.command(name="atualizar_filas")
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Atualizando Painéis...", ephemeral=True)
    nome_c = interaction.channel.name.lower()
    mod = "1v1" if "1v1" in nome_c else "Aposta"
    await interaction.channel.purge(limit=10)
    for v in valores_lista:
        emb = discord.Embed(title=f"⚔️ FILA {mod}", color=0xFFA500)
        emb.add_field(name="💰 Valor:", value=f"R$ {v}", inline=False)
        emb.add_field(name="👥 Jogadores:", value="Vazio", inline=False)
        await interaction.channel.send(embed=emb, view=ViewFilaFuria(v, mod))

@bot.command()
async def sync(ctx):
    fmt = await bot.tree.sync()
    await ctx.send(f"✅ {len(fmt)} comandos sincronizados!")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🚀 ORG FÚRIA ONLINE: {bot.user.name}")

keep_alive()
bot.run(os.environ.get('TOKEN'))
