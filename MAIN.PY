import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import json
import random

# --- BANCO DE DADOS SEGURO ---
def carregar_dados(arquivo):
    if not os.path.exists(arquivo):
        with open(arquivo, 'w') as f: json.dump({}, f)
        return {}
    try:
        with open(arquivo, 'r') as f: return json.load(f)
    except: return {}

def salvar_dados(arquivo, dados):
    with open(arquivo, 'w') as f: json.dump(dados, f, indent=4)

# --- BOT CONFIG ---
intents = discord.Intents.all()
class FuriaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        self.add_view(ViewCentral())
        # Não adicionamos ViewFila aqui porque elas são geradas dinamicamente
        print("✅ Sistema de Views Carregado")

bot = FuriaBot()
fila_mediadores = [] 
dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1", "0.50"]

# --- MODAL PIX ---
class ModalPixFuria(discord.ui.Modal, title='💠 CADASTRAR PIX - FÚRIA'):
    chave = discord.ui.TextInput(label='Sua Chave Pix', required=True)
    banco = discord.ui.TextInput(label='Nome do Banco', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        db = carregar_dados('pix.json')
        db[str(interaction.user.id)] = {"chave": self.chave.value, "banco": self.banco.value}
        salvar_dados('pix.json', db)
        await interaction.response.send_message("✅ Pix cadastrado!", ephemeral=True)

# --- VIEW CENTRAL ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅", custom_id="furia_entrar_med")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        pix_db = carregar_dados('pix.json')
        if str(interaction.user.id) not in pix_db:
            return await interaction.response.send_message("❌ Cadastre o Pix primeiro!", ephemeral=True)
        
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores])
            emb = interaction.message.embeds[0]
            emb.set_field_at(0, name="Mediadores Online:", value=txt, inline=False)
            await interaction.response.edit_message(embed=emb)
        else:
            await interaction.response.send_message("⚠️ Você já está na fila!", ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💠", custom_id="furia_pix_med")
    async def pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPixFuria())

# --- VIEW FILA JOGADORES ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, mod):
        super().__init__(timeout=None)
        self.valor, self.mod = valor, mod

    @discord.ui.button(label="Gelo Normal", style=discord.ButtonStyle.secondary, emoji="🧊")
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.puxar(interaction, "Gelo Normal")

    async def puxar(self, interaction, tipo):
        await interaction.response.defer(ephemeral=True) # EVITA O "APLICATIVO NÃO RESPONDEU"
        
        chave = (interaction.channel.id, self.valor)
        if chave not in dados_filas_memoria: dados_filas_memoria[chave] = []
        
        if interaction.user in dados_filas_memoria[chave]:
            return await interaction.followup.send("❌ Já está na fila!", ephemeral=True)

        dados_filas_memoria[chave].append(interaction.user)
        
        # Atualiza a lista na tela
        txt = "\n".join([p.mention for p in dados_filas_memoria[chave]])
        emb = interaction.message.embeds[0]
        emb.set_field_at(1, name="👥 Jogadores:", value=txt, inline=False)
        await interaction.message.edit(embed=emb)
        await interaction.followup.send("✅ Entrou!", ephemeral=True)

        if len(dados_filas_memoria[chave]) >= 2:
            if not fila_mediadores:
                dados_filas_memoria[chave].remove(interaction.user)
                return await interaction.followup.send("⚠️ Sem mediadores ON!", ephemeral=True)
            
            p1, p2 = dados_filas_memoria[chave].pop(0), dados_filas_memoria[chave].pop(0)
            med_id = random.choice(fila_mediadores)
            
            canal = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal:
                thread = await canal.create_thread(name=f"⚔️ {self.valor} | {self.mod}")
                await thread.send(f"⚔️ **PARTIDA INICIADA**\nJogadores: {p1.mention} vs {p2.mention}\nMediador: <@{med_id}>\nUse /win para finalizar.")

# --- COMANDOS ---
@bot.tree.command(name="central", description="Abre a central de mediadores")
async def central(interaction: discord.Interaction):
    emb = discord.Embed(title="👮 CENTRAL DE MEDIADORES - FÚRIA", color=0xFFA500)
    emb.add_field(name="Mediadores Online:", value="Nenhum no momento.", inline=False)
    await interaction.response.send_message(embed=emb, view=ViewCentral())

@bot.tree.command(name="win", description="Finaliza a partida")
async def win(interaction: discord.Interaction, ganhador: discord.Member, perdedor: discord.Member, valor: str):
    await interaction.response.send_message(f"🏆 **PARTIDA FINALIZADA**\nVencedor: {ganhador.mention}\nValor: R$ {valor}\nCanal será deletado em 5s.")
    await asyncio.sleep(5)
    await interaction.channel.delete()

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Comandos Sincronizados!")

@bot.event
async def on_ready():
    print(f"🚀 {bot.user.name} ONLINE")
    await bot.tree.sync() # Tenta sincronizar ao ligar

bot.run("MTQ2MzU5MTE1MTk0MzgxMTMwNQ.Gcbaby.rYsR-0qkUPtV-y-N4nwWJQLEplYkzDfiZwJZ1c")
