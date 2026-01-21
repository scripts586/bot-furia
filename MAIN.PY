import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import asyncio
import random

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

# --- VIEW CONFIRMAÇÃO DA APOSTA (TÓPICO) ---
class ViewConfirmacaoAposta(discord.ui.View):
    def __init__(self, p1, p2, valor):
        super().__init__(timeout=None)
        self.p1 = p1
        self.p2 = p2
        self.valor = valor
        self.confirmado = {p1.id: False, p2.id: False}
        self.finalizado = False

    @discord.ui.button(label="Confirmar ✅", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction, button):
        if self.finalizado: return

        if interaction.user.id not in [self.p1.id, self.p2.id]:
            return await interaction.response.send_message("Tu não fazes parte desta aposta!", ephemeral=True)

        self.confirmado[interaction.user.id] = True
        await interaction.response.send_message(f"{interaction.user.mention} confirmou a aposta!", ephemeral=False)

        if all(self.confirmado.values()):
            self.finalizado = True
            self.stop() 
            
            # SORTEIO DO MEDIADOR
            if not fila_mediadores:
                await interaction.channel.send("⚠️ **ATENÇÃO:** Nenhum mediador online na fila! Marquem algum cargo administrativo.")
            else:
                mediador_id = random.choice(fila_mediadores)
                dados_pix = mediadores_dados.get(mediador_id)
                mediador_user = interaction.guild.get_member(mediador_id)

                embed = discord.Embed(title="✅ APOSTA VALIDADA - PAGAMENTO LIBERADO", color=0x00FF00)
                embed.description = f"Os jogadores confirmaram! Enviem o valor para o mediador sorteado abaixo."
                
                if mediador_user:
                    embed.add_field(name="👮 Mediador da Vez", value=mediador_user.mention, inline=False)
                
                if dados_pix:
                    embed.add_field(name="🏦 Banco", value=dados_pix['banco'], inline=True)
                    embed.add_field(name="🔑 Chave Pix", value=f"```{dados_pix['chave']}```", inline=True)
                    embed.add_field(name="👤 Nome", value=dados_pix['nome'], inline=False)
                
                embed.set_footer(text=f"Valor Total da Mesa: R$ {self.valor},00")
                await interaction.channel.send(content=f"{self.p1.mention} {self.p2.mention} {mediador_user.mention if mediador_user else ''}", embed=embed)

    @discord.ui.button(label="Cancelar ❌", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction, button):
        if interaction.user.id in [self.p1.id, self.p2.id]:
            self.finalizado = True
            self.stop()
            await interaction.channel.send(f"❌ Aposta cancelada. O tópico será apagado.")
            await asyncio.sleep(5)
            await interaction.channel.delete()

# --- VIEW CENTRAL (MEDIADORES) ---
class ViewCentral(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def atualizar_central(self, interaction):
        embed = interaction.message.embeds[0]
        lista_str = "\n".join([f"• <@{m_id}>" for m_id in fila_mediadores]) if fila_mediadores else "Nenhum mediador online."
        embed.clear_fields()
        embed.add_field(name="🎧 Mediadores Disponíveis", value=lista_str, inline=False)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Entrar na Fila", style=discord.ButtonStyle.success, emoji="✅")
    async def entrar_med(self, interaction, button):
        if interaction.user.id not in mediadores_dados:
            return await interaction.response.send_message("❌ Cadastra o teu Pix primeiro!", ephemeral=True)
        if interaction.user.id in fila_mediadores:
            return await interaction.response.send_message("Já estás na fila!", ephemeral=True)
        
        fila_mediadores.append(interaction.user.id)
        await interaction.response.send_message("Entraste na fila de mediadores!", ephemeral=True)
        await self.atualizar_central(interaction)

    @discord.ui.button(label="Sair da Fila", style=discord.ButtonStyle.danger, emoji="❌")
    async def sair_med(self, interaction, button):
        if interaction.user.id in fila_mediadores:
            fila_mediadores.remove(interaction.user.id)
            await interaction.response.send_message("Saíste da fila!", ephemeral=True)
            await self.atualizar_central(interaction)
        else:
            await interaction.response.send_message("Não estás na fila.", ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", style=discord.ButtonStyle.secondary, emoji="💸")
    async def cad_pix(self, interaction, button):
        await interaction.response.send_modal(ModalCadastroPix())

# --- VIEW JOGADORES ---
class ViewFilaJogadores(discord.ui.View):
    def __init__(self, valor, modo_texto):
        super().__init__(timeout=None)
        self.valor = valor
        self.modo_texto = modo_texto

    async def atualizar_embed(self, interaction, fila):
        embed = interaction.message.embeds[0]
        jogadores_str = "\n".join([p.mention for p in fila]) if fila else "Ninguém"
        embed.clear_fields()
        embed.add_field(name="💰 Valor", value=f"R$ {self.valor},00", inline=True)
        embed.add_field(name="👥 Aguardando", value=jogadores_str, inline=True)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Entrar na Fila ✅", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, button):
        chave = (interaction.channel.id, self.valor)
        if chave not in dados_filas_jogadores: dados_filas_jogadores[chave] = []
        fila = dados_filas_jogadores[chave]

        if interaction.user in fila: return await interaction.response.send_message("Já estás na fila!", ephemeral=True)

        fila.append(interaction.user)
        await interaction.response.send_message(f"Entraste na fila ({self.modo_texto}) de R$ {self.valor}!", ephemeral=True)
        await self.atualizar_embed(interaction, fila)

        if len(fila) >= 2:
            p1, p2 = fila.pop(0), fila.pop(0)
            await self.atualizar_embed(interaction, fila)
            canal_dest = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
            if canal_dest:
                msg = await canal_dest.send(f"⚠️ **Aposta {self.modo_texto} Iniciada:** {p1.mention} vs {p2.mention}")
                thread = await msg.create_thread(name=f"R${self.valor} - {self.modo_texto} ({p1.display_name} vs {p2.display_name})")
                
                embed_aviso = discord.Embed(title=f"🔥 SALA DE APOSTA - {self.modo_texto}", description="Confirmem abaixo para chamar o mediador.", color=0xFFA500)
                await thread.send(content=f"{p1.mention} {p2.mention}", embed=embed_aviso, view=ViewConfirmacaoAposta(p1, p2, self.valor))

    @discord.ui.button(label="Sair da Fila ❌", style=discord.ButtonStyle.danger)
    async def sair(self, interaction, button):
        chave = (interaction.channel.id, self.valor)
        fila = dados_filas_jogadores.get(chave, [])
        if interaction.user in fila:
            fila.remove(interaction.user)
            await interaction.response.send_message("Saíste da fila.", ephemeral=True)
            await self.atualizar_embed(interaction, fila)

# --- COMANDOS ---
@bot.event
async def on_ready():
    bot.add_view(ViewCentral())
    print(f'✅ SISTEMA ONLINE')

@bot.command()
async def sync(ctx):
    fmt = await bot.tree.sync()
    await ctx.send(f"✅ Sincronizados {len(fmt)} comandos!")

@bot.tree.command(name="central", description="Painel dos Mediadores")
async def central(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ CENTRAL DE MEDIADORES", color=0x2f3136)
    embed.add_field(name="🎧 Mediadores Disponíveis", value="Nenhum mediador online.", inline=False)
    await interaction.response.send_message(embed=embed, view=ViewCentral())

@bot.tree.command(name="atualizar_filas", description="Gera painéis")
@app_commands.checks.has_permissions(administrator=True)
async def atualizar_filas(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ A gerar...", ephemeral=True)
    canais = [c for c in interaction.guild.text_channels if "fila" in c.name.lower()]
    for canal in canais:
        await canal.purge(limit=50)
        nome = canal.name.lower()
        if "4x4" in nome or "4v4" in nome: modo = "4v4"
        elif "3x3" in nome or "3v3" in nome: modo = "3v3"
        elif "2x2" in nome or "2v2" in nome: modo = "2v2"
        else: modo = "1v1"
        for v in valores_lista:
            embed = discord.Embed(title=f"⚔️ {modo} APOSTADO", color=0xFF4500)
            embed.add_field(name="💰 Valor", value=f"R$ {v},00", inline=True)
            embed.add_field(name="👥 Aguardando", value="Ninguém", inline=True)
            await canal.send(embed=embed, view=ViewFilaJogadores(v, modo))

# --- COMANDO /WIN (RESULTADO NO CANAL SEUS-APOSTADOS-AQUI) ---
@bot.tree.command(name="win", description="Registra vitória (Exclusivo cargo ADM)")
@app_commands.describe(ganhador="Quem venceu", perdedor="Quem perdeu", valor="Valor da aposta")
@app_commands.checks.has_role("ADM") 
async def win(interaction: discord.Interaction, ganhador: discord.Member, perdedor: discord.Member, valor: str):
    await interaction.response.defer(ephemeral=True)

    # ALTERAÇÃO AQUI: Agora envia para 'seus-apostados-aqui📌'
    canal = discord.utils.get(interaction.guild.text_channels, name="seus-apostados-aqui📌")
    
    if not canal:
        return await interaction.followup.send("❌ Erro: O canal `seus-apostados-aqui📌` não existe!")
    
    embed = discord.Embed(title="🏆 FIM DA APOSTA", color=0x00FF00)
    embed.add_field(name="👑 Vencedor", value=ganhador.mention, inline=True)
    embed.add_field(name="💀 Perdedor", value=perdedor.mention, inline=True)
    embed.add_field(name="💰 Valor", value=f"R$ {valor}", inline=False)
    if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f"Registrado por: {interaction.user.display_name}")

    try:
        await canal.send(embed=embed)
        await interaction.followup.send("✅ Resultado postado em `seus-apostados-aqui📌`!")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao enviar a mensagem: {e}")

@win.error
async def win_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message("❌ Precisas de ter o cargo **ADM** para usar este comando!", ephemeral=True)

keep_alive()
bot.run(os.environ['TOKEN'])
