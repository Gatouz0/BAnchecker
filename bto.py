import discord
import os
import requests
import json
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timezone
from keepalive import keep_alive

load_dotenv()

print("start")
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())


@bot.event
async def on_ready():
    print("working")
    try:
        synced = await bot.tree.sync()
        print(f"commandes slash synchronisé : {len(synced)}")
        check_bans.start()
    except Exception as e:
        print(e)


previous_results = []
termes = []  # Liste initiale des joueurs

BAN_CHANNEL_ID = 1344758545937203322  # ID du canal pour la liste des bans
STATUS_MESSAGE_ID = None  # ID du message de statut


def load_players():
    try:
        with open('watchlist.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_players():
    with open('watchlist.json', 'w') as file:
        json.dump(termes, file)


termes = load_players()


async def update_bans():
    global STATUS_MESSAGE_ID  # Déclaration de la variable globale au début de la fonction
    print("update_bans() called")
    url_base = 'https://login.strongholdkingdoms.com/ajaxphp/username_search.php?term={}'

    results = []
    for terme in termes:
        print(f"Checking {terme}")
        url = url_base.format(terme)
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            print(f"Response for {terme}: {data}")

            if not any(terme.lower() == player.lower() for player in data):
                results.append(f"{terme} est banni")
        else:
            print(f"Erreur lors de la requête pour {terme}: {response.status_code}")

    global previous_results
    channel = bot.get_channel(BAN_CHANNEL_ID)
    if channel is None:
        print(f"Erreur: le canal avec l'ID {BAN_CHANNEL_ID} n'a pas été trouvé.")
        return

    last_update = datetime.now(timezone.utc)  # Utiliser des objets sensibilisés aux fuseaux horaires
    timestamp = int(last_update.timestamp())  # Convertir en timestamp UNIX
    messages = [message async for message in channel.history(limit=100)]

    embed_message = None
    for message in messages:
        if message.author == bot.user and message.embeds and message.embeds[0].title == "Résultats actuels":
            embed_message = message
            break

    if results != previous_results or embed_message is None:
        previous_results = results

        if embed_message:
            await embed_message.delete()

        if results:  # S'il y a des joueurs bannis à signaler
            embed = discord.Embed(title="Résultats actuels", description="\n".join(results), color=discord.Color.red())
            print(f"Sending embed: {embed.description}")
            await channel.send(embed=embed)
        else:
            embed = discord.Embed(title="Résultats actuels", description="Aucun ban détecté.",
                                  color=discord.Color.green())
            print(f"Sending embed: {embed.description}")
            await channel.send(embed=embed)

    if STATUS_MESSAGE_ID:
        try:
            status_message = await channel.fetch_message(STATUS_MESSAGE_ID)
            await status_message.edit(content=f"Dernière mise à jour : <t:{timestamp}:t>")
        except discord.errors.NotFound:
            status_message = await channel.send(f"Dernière mise à jour : <t:{timestamp}:t>")
            STATUS_MESSAGE_ID = status_message.id
    else:
        status_message = await channel.send(f"Dernière mise à jour : <t:{timestamp}:t>")
        STATUS_MESSAGE_ID = status_message.id


@tasks.loop(minutes=30)
async def check_bans():
    await update_bans()


@bot.tree.command(name="warnguy", description="warn")
async def warn(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message("avertissement envoyé")
    await member.send("tu as reçu un avertissement")


@bot.tree.command(name="check", description="Vérifie si un joueur est banni et l'ajoute à la liste de surveillance s'il n'y est pas")
async def check(interaction: discord.Interaction, player: str):
    await interaction.response.defer()  # Reconnaît l'interaction immédiatement

    # Ajoute le joueur à la liste de surveillance s'il n'y est pas déjà
    if not any(player.lower() == t.lower() for t in termes):
        termes.append(player)
        save_players()
        await interaction.followup.send(f"{player} a été ajouté à la liste de surveillance.")

    url_base = 'https://login.strongholdkingdoms.com/ajaxphp/username_search.php?term={}'
    url = url_base.format(player)
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        if not any(player.lower() == p.lower() for p in data):
            await interaction.followup.send(f"{player} est banni.")
        else:
            found_player = data[0]  # Le premier résultat trouvé
            await interaction.followup.send(f"{found_player} n'est pas banni.")
    else:
        await interaction.followup.send(f"Erreur lors de la requête pour le joueur.")


@bot.tree.command(name="force_update", description="Force the update and display of the current bans")
async def force_update(interaction: discord.Interaction):
    await interaction.response.send_message("Mise à jour forcée des résultats actuels.")
    await update_bans()


@bot.tree.command(name="add_player", description="Add a player to the watch list")
async def add_player(interaction: discord.Interaction, player: str):
    if not any(player.lower() == t.lower() for t in termes):
        termes.append(player)
        save_players()
        await interaction.response.send_message(f"{player} a été ajouté à la liste de surveillance.")
    else:
        await interaction.response.send_message(f"{player} est déjà dans la liste de surveillance.")


@bot.tree.command(name="show_players", description="Show the list of players being watched")
async def show_players(interaction: discord.Interaction):
    if termes:
        await interaction.response.send_message("Liste des joueurs surveillés:\n" + "\n".join(termes))
    else:
        await interaction.response.send_message("Aucun joueur n'est actuellement surveillé.")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))
