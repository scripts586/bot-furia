import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import asyncio
import json
import random

# --- BANCO DE DADOS ---
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

fila_mediadores = [] 
dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1", "0.50"]

# --- CENTRAL DE MEDIADORES (MODAIS E VIEWS) ---
class ModalPix(discord.ui.Modal, title='📄 Cadastrar Pix'):
    chave = discord.ui.TextInput(label='Sua Chave Pix', placeholder='Ex: CPF, Celular ou E-mail', required=True)
    banco = discord.ui.TextInput(label='Nome do Banco', placeholder='Ex: Nubank, Inter', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        pix_db = carregar_dados('pix.json')
        pix_db[str(interaction.user.id)] = {"chave": self.chave.value, "banco": self.banco.value}
        salvar_dados('pix.json', pix_db)
        await interaction.response.send_message("✅ Pix cadastrado com sucesso!", ephemeral=True)

class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar(self, interaction, button):
        pix_db = carregar_dados('pix.json')
        if str(interaction.user.id) not in pix_db:
            return await interaction.response.send_message("❌ Cadastre seu Pix primeiro!", ephemeral=True)
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            # Atualiza embed da central
            embed = interaction.message.embeds[0]
            txt = "\n".join([f"👤 <@{m}>" for m in fila_mediadores]) if fila_mediadores else "Nenhum mediador online no momento."
            embed.set_field_at(1, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("✅ Você entrou na fila de mediadores!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Você já está na fila!", ephemeral=True)

    @discord.ui.button(label="Ranking Mediadores", style=discord.ButtonStyle.secondary, emoji="🏆")
    async def ranking_med(self, interaction, button):
        await interaction.response.send_message("🏆 Ranking de mediadores em breve!", ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💠")
    async def cad_pix(self, interaction, button):
        await interaction.response.send_modal(ModalPix())

    @discord.ui.button(label="Visualizar Pix", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def ver_pix(self, interaction, button):
        pix_db = carregar_dados('pix.json')
        meu_pix = pix_db.get(str(interaction.user.id))
        if meu_pix:
            await interaction.response.send_message(f"🏦 **Banco:** {meu_pix['banco']}\n🔑 **Chave:** {meu_pix['chave']}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Pix não encontrado!", ephemeral=True)

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair(self, interaction, button):
        if interaction.user.id in fila_mediadores:
            fila_mediadores.remove(interaction.user.id)
            embed = interaction.message.embeds[0]
            txt = "\n".join([f"👤 <@{m}>" for m in fila_mediadores]) if fila_mediadores else "Nenhum mediador online no momento."
            embed.set_field_at(1, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("❌ Você saiu da fila!", ephemeral=True)

# --- FILAS FÚRIA ---
class ViewFilaFuria(discord.ui.View):
    def __init__(self, valor, modalidade):
        super().__init__(timeout=None)
        self.valor, self.modalidade = valor, modalidade

    async def gerenciar_fila(self, interaction, tipo_gelo):
        chave = (interaction.channel.id, self.valor, tipo_gelo)
        if chave not in dados_filas_memoria: dados_filas_memoria[chave] = []
        fila = dados_filas_memoria[chave]
        if interaction.user in fila: return await interaction.response.send_message("❌ Já está na fila!", ephemeral=True)

        fila.append(interaction.user)
        jogadores_str = "\n".join([p.mention for p in fila])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="Jogadores:", value=jogadores_str, inline=False)
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"✅ Entrou R$ {self.valor}", ephemeral=True)

        if len(fila) >= 2:
            p1, p2 = fila.pop(0), fila.pop(0)
            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)
            canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_res:
                msg = await canal_res.send(f"⚠️ **PARTIDA ORG FÚRIA:** {p1.mention} VS {p2.mention}")
                thread = await msg.create_thread(name=f"⚔️ {self.modalidade} | R${self.valor}")
                
                # Envia o Pix do Mediador Aleatório se houver alguém online
                texto_med = "⚠️ Aguardando mediador online."
                if fila_mediadores:
                    med_sorteado = interaction.guild.get_member(random.choice(fila_mediadores))
                    pix_db = carregar_dados('pix.json')
                    dados_p = pix_db.get(str(med_sorteado.id))
                    texto_med = f"👮 **Mediador:** {med_sorteado.mention}\n🔑 **Pix:** `{dados_p['chave'] if dados_p else 'Não cadastrado'}`"

                await thread.send(content=f"{p1.mention} {p2.mention}\n{texto_med}")

    @discord.ui.button(label="Gelo Normal", style=discord.ButtonStyle.secondary, emoji="🧊")
    async def normal(self, i, b): await self.gerenciar_fila(i, "Gelo Normal")
    @discord.ui.button(label="Gelo Infinito", style=discord.ButtonStyle.secondary, emoji="♾️")
    async def infinito(self, i, b): await self.gerenciar_fila(i, "Gelo Infinito")
    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair_f(self, interaction, button):
        for chave in dados_filas_memoria:
            if interaction.user in dados_filas_memoria[chave]:
                dados_filas_memoria[chave].remove(interaction.user)
                f = dados_filas_memoria[chave]
                txt = "\n".join([p.mention for p in f]) if f else "Nenhum jogador na fila"
                embed = interaction.message.embeds[0]
                embed.set_field_at(1, name="Jogadores:", value=txt, inline=False)
                await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✅ Saiu!", ephemeral=True)

# --- COMANDOS ---
@bot.tree.command(name="central", description="Abre a Central de Mediadores FÚRIA")
async def central(interaction: discord.Interaction):
    embed = discord.Embed(title="Mediadores disponíveis", color=0xFFA500)
    embed.description = "Só interaja com o botão \"Entrar na Fila\", caso esteja disponível para mediar os apostados."
    embed.add_field(name="Mediadores Online:", value="Nenhum mediador online no momento.", inline=False)
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text="ORG FÚRIA | SALAS 10 C") #
    await interaction.response.send_message(embed=embed, view=ViewCentral())

@bot.tree.command(name="atualizar_filas")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Atualizando...", ephemeral=True)
    nome_c = interaction.channel.name.lower()
    plat = "Mobile" if "mobile" in nome_c else "Emulador" if "emulador" in nome_c else "Aposta"
    x = "1v1" if "x1" in nome_c else "2v2" if "x2" in nome_c else "3v3" if "x3" in nome_c else "4v4"
    mod = f"{x} {plat}"
    await interaction.channel.purge(limit=100)
    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500, title=f"⚔️ {mod}")
        embed.add_field(name="Valor:", value=f"R$ {v}", inline=False)
        embed.add_field(name="Jogadores:", value="Nenhum jogador na fila", inline=False)
        embed.set_footer(text="ORG FÚRIA | SALAS 10 C")
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, mod))

@bot.event
async def on_ready():
    bot.add_view(ViewCentral())
    print(f"🚀 FÚRIA INTEGRADA ONLINE!")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Sincronizado!")

keep_alive()
bot.run(os.environ['TOKEN'])
