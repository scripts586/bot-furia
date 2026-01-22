import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import asyncio
import json
import random

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

fila_mediadores = [] 
dados_filas_memoria = {} 
valores_lista = ["100", "50", "40", "30", "20", "10", "5", "4", "3", "2", "1", "0.50"]

# --- VIEW: FINALIZAÇÃO (WIN) COM 3 EMBEDS ---
class ViewWinFuria(discord.ui.View):
    def __init__(self, p1, p2, valor):
        super().__init__(timeout=None)
        self.p1, self.p2, self.valor = p1, p2, valor
        self.ganhador = None
        self.perdedor = None

    @discord.ui.button(label="DEFINIR GANHADOR", style=discord.ButtonStyle.success, emoji="🏆")
    async def set_ganhador(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        select = discord.ui.Select(placeholder="Quem venceu?")
        select.add_option(label=self.p1.display_name, value=str(self.p1.id))
        select.add_option(label=self.p2.display_name, value=str(self.p2.id))
        async def callback(i):
            self.ganhador = interaction.guild.get_member(int(select.values[0]))
            await i.response.send_message(f"✅ Ganhador definido: {self.ganhador.mention}", ephemeral=True)
        select.callback = callback
        view.add_item(select)
        await interaction.response.send_message("Selecione o vencedor:", view=view, ephemeral=True)

    @discord.ui.button(label="DEFINIR PERDEDOR", style=discord.ButtonStyle.danger, emoji="💀")
    async def set_perdedor(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        select = discord.ui.Select(placeholder="Quem perdeu?")
        select.add_option(label=self.p1.display_name, value=str(self.p1.id))
        select.add_option(label=self.p2.display_name, value=str(self.p2.id))
        async def callback(i):
            self.perdedor = interaction.guild.get_member(int(select.values[0]))
            await i.response.send_message(f"✅ Perdedor definido: {self.perdedor.mention}", ephemeral=True)
        select.callback = callback
        view.add_item(select)
        await interaction.response.send_message("Selecione o perdedor:", view=view, ephemeral=True)

    @discord.ui.button(label="ENCERRAR APOSTA", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def encerrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ganhador or not self.perdedor:
            return await interaction.response.send_message("❌ Defina o resultado primeiro!", ephemeral=True)
        
        canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
        if canal_res:
            emb = discord.Embed(title="🏁 ORG FÚRIA | RESULTADO", color=0x2ECC71)
            emb.add_field(name="👑 Vencedor", value=self.ganhador.mention)
            emb.add_field(name="💰 Valor", value=f"R$ {self.valor}")
            emb.set_footer(text="ORG FÚRIA | SALAS 10 C")
            await canal_res.send(embed=emb)
        await interaction.response.send_message("Encerrando tópico...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

# --- ADICIONE ESTA CLASSE ACIMA DA VIEW CENTRAL ---
class ModalPixFuria(discord.ui.Modal, title='💠 CADASTRAR PIX - FÚRIA'):
    chave = discord.ui.TextInput(label='Sua Chave Pix', placeholder='Ex: CPF, E-mail ou Aleatória', required=True)
    banco = discord.ui.TextInput(label='Nome do Banco', placeholder='Ex: Nubank, Inter, Itaú', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        pix_db = carregar_dados('pix.json')
        pix_db[str(interaction.user.id)] = {"chave": self.chave.value, "banco": self.banco.value}
        salvar_dados('pix.json', pix_db)
        await interaction.response.send_message(f"✅ Pix cadastrado com sucesso!", ephemeral=True)

# --- DENTRO DA CLASS VIEWCENTRAL, ADICIONE ESTES BOTÕES ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar(self, interaction, button):
        # Verifica se tem Pix antes de deixar entrar na fila
        pix_db = carregar_dados('pix.json')
        if str(interaction.user.id) not in pix_db:
            return await interaction.response.send_message("❌ Você precisa cadastrar seu Pix antes de entrar na fila!", ephemeral=True)
            
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            embed = interaction.message.embeds[0]
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores])
            embed.set_field_at(1, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("✅ Você entrou na fila de mediadores!", ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💠")
    async def cadastrar_pix(self, interaction, button):
        # Abre o formulário para o mediador digitar os dados
        await interaction.response.send_modal(ModalPixFuria())

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair(self, interaction, button):
        if interaction.user.id in fila_mediadores:
            fila_mediadores.remove(interaction.user.id)
            embed = interaction.message.embeds[0]
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores]) if fila_mediadores else "Nenhum mediador online."
            embed.set_field_at(1, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("❌ Você saiu da fila!", ephemeral=True)


# --- VIEW: CENTRAL DE MEDIADORES ---
class ViewCentral(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar(self, interaction, button):
        if interaction.user.id not in fila_mediadores:
            fila_mediadores.append(interaction.user.id)
            embed = interaction.message.embeds[0]
            # Menciona com @ na fila de mediadores
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores])
            embed.set_field_at(1, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("✅ Você entrou na fila!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Já está na fila!", ephemeral=True)

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair(self, interaction, button):
        if interaction.user.id in fila_mediadores:
            fila_mediadores.remove(interaction.user.id)
            embed = interaction.message.embeds[0]
            txt = "\n".join([f"<@{m}>" for m in fila_mediadores]) if fila_mediadores else "Nenhum mediador online."
            embed.set_field_at(1, name="Mediadores Online:", value=txt, inline=False)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("❌ Você saiu!", ephemeral=True)

# --- VIEW: FILAS DE JOGADORES ---
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
        await interaction.response.send_message(f"✅ Entrou na fila R$ {self.valor}", ephemeral=True)

        if len(fila) >= 2:
            # SÓ PUXA SE HOUVER MEDIADOR ON
            if not fila_mediadores:
                fila.pop() # Remove o último pra não travar a fila
                return await interaction.followup.send("⚠️ Partida não iniciada! Não há MEDIADORES ON na fila no momento.", ephemeral=True)

            p1, p2 = fila.pop(0), fila.pop(0)
            med_id = random.choice(fila_mediadores)
            med_obj = interaction.guild.get_member(med_id)

            embed.set_field_at(1, name="Jogadores:", value="Nenhum jogador na fila", inline=False)
            await interaction.message.edit(embed=embed)

            canal_res = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_res:
                msg = await canal_res.send(f"⚠️ **PARTIDA ORG FÚRIA:** {p1.mention} VS {p2.mention}")
                thread = await msg.create_thread(name=f"⚔️ {self.modalidade} | R${self.valor}")
                await thread.send(content=f"{p1.mention} {p2.mention}\n👮 **Mediador:** {med_obj.mention}\n**Gelo:** {tipo_gelo}\nUse /win para finalizar.")

    @discord.ui.button(label="Gelo Normal", style=discord.ButtonStyle.secondary, emoji="🧊")
    async def gelo_normal(self, i, b): await self.gerenciar_fila(i, "Gelo Normal")
    @discord.ui.button(label="Gelo Infinito", style=discord.ButtonStyle.secondary, emoji="♾️")
    async def gelo_infinito(self, i, b): await self.gerenciar_fila(i, "Gelo Infinito")

# --- COMANDOS SLASH ---
@bot.tree.command(name="win")
async def win(interaction: discord.Interaction, jogador1: discord.Member, jogador2: discord.Member, valor: str):
    emb1 = discord.Embed(title="🏆 GANHADOR", description=f"Selecione quem venceu: {jogador1.mention} ou {jogador2.mention}", color=0x2ECC71)
    emb2 = discord.Embed(title="💀 PERDEDOR", description=f"Selecione quem perdeu: {jogador1.mention} ou {jogador2.mention}", color=0xE74C3C)
    emb3 = discord.Embed(title="🔒 ENCERRAR APOSTA", description=f"Valor: **R$ {valor}**\nClique para fechar o tópico.", color=0x34495E)
    emb3.set_footer(text="ORG FÚRIA | SALAS 10 C")
    view = ViewWinFuria(jogador1, jogador2, valor)
    await interaction.response.send_message(embeds=[emb1, emb2, emb3], view=view)

@bot.tree.command(name="central")
async def central(interaction: discord.Interaction):
    embed = discord.Embed(title="Mediadores disponíveis", color=0xFFA500)
    embed.add_field(name="Instruções:", value="Entre na fila apenas se puder mediar agora.", inline=False)
    embed.add_field(name="Mediadores Online:", value="Nenhum mediador online.", inline=False)
    embed.set_footer(text="ORG FÚRIA | SALAS 10 C")
    await interaction.response.send_message(embed=embed, view=ViewCentral())

@bot.tree.command(name="atualizar_filas")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("🧹 Atualizando...", ephemeral=True)
    nome_c = interaction.channel.name.lower()
    plat = "Mobile" if "mobile" in nome_c else "Emulador"
    x = "1v1" if "1v1" in nome_c else "2v2" if "2v2" in nome_c else "3v3" if "3v3" in nome_c else "4v4"
    mod = f"{x} {plat}"
    await interaction.channel.purge(limit=100)
    for v in valores_lista:
        embed = discord.Embed(color=0xFFA500, title=f"⚔️ {mod}")
        embed.add_field(name="💰 Valor:", value=f"R$ {v}", inline=False)
        embed.add_field(name="👥 Jogadores:", value="Nenhum jogador na fila", inline=False)
        embed.set_footer(text="ORG FÚRIA | SALAS 10 C")
        await interaction.channel.send(embed=embed, view=ViewFilaFuria(v, mod))

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🚀 ORG FÚRIA INTEGRADA ONLINE!")

keep_alive()
bot.run(os.environ['TOKEN'])
