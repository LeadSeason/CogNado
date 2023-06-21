import discord
import auraxium
import asyncio
from time import time
from auraxium import ps2
from redbot.core import Config, commands, app_commands


class Planetside(commands.Cog):
    """
        Planetside Cog. Contains command for the game Planetside 2.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2162678924, force_registration=True)

        self.config.register_global(
            serviceId=False
        )

    @commands.command()
    @commands.is_owner()
    async def setserviceid(self, ctx, newServiceId):
        await self.config.serviceId.set(newServiceId)
        await ctx.reply("Service ID has ben set", delete_after=10, ephemeral=True)

    @commands.command()
    @commands.is_owner()
    async def getserviceid(self, ctx):
        serviceId = await self.config.serviceId()
        await ctx.reply(f"Service ID is {serviceId}", delete_after=10, ephemeral=True)

    @app_commands.command()
    @app_commands.describe(username=" of the Player")
    async def playerstats(self, interaction: discord.Interaction, username: str):
        """
            Get stats for a planetside player
        """
        # Using defer because sensus reponses are sometimes slow
        await interaction.response.defer(thinking=True)

        startTime = time()

        serviceId = await self.config.serviceId()
        if serviceId is False:
            # Maybe add some error here? maybe from redbot
            return

        async with auraxium.Client(service_id=f"s:{serviceId}") as client:
            try:
                char = await client.get_by_name(ps2.Character, username.lower())
            except auraxium.errors.ServiceUnavailableError:
                await interaction.edit_original_response(
                    embed=discord.Embed(title="Failed to connect to census api", color=0xed333b)
                )
                await asyncio.sleep(5)
                await interaction.delete_original_response()
                return

            if char is None:
                await interaction.edit_original_response(
                    embed=discord.Embed(title=f"Failed to find player '{username}'", color=0xed333b)
                )
                await asyncio.sleep(5)
                await interaction.delete_original_response()
                return

            onlineIcon = "🔴"
            if await char.is_online():
                onlineIcon = "🟢"

            if char.faction_id == 1:
                # faction_name = "VS"
                faction_color = 0xc061cb
                faction_emoji = "<:vs:441405448113881098>"
            elif char.faction_id == 2:
                # faction_name = "NC"
                faction_color = 0x62a0ea
                faction_emoji = "<:nc:441405432091901972>"
            elif char.faction_id == 3:
                # faction_name = "TR"
                faction_color = 0xed333b
                faction_emoji = "<:tr:1104394643145232395>"
            else:
                # faction_name = "NSO"
                faction_color = 0x777777
                faction_emoji = "<:nso:938862172522573904>"

            outfit = await char.outfit()
            charTitle = await char.title()

            # If in outfit display outfit in [OFIT]
            outfitTag = ""
            if outfit is not None:
                outfitTag = f"[{outfit.tag}] "

            prestige = ""
            if char.prestige_level > 0:
                prestige = f"~{char.prestige_level}"

            if charTitle is None:
                charTitle = ""

            """
                🟢 :nc: Character
                Title BR 120
            """
            embed = discord.Embed(
                title=f"{onlineIcon} {faction_emoji} {outfitTag}{char.name}",
                description=f"{charTitle} BR {char.battle_rank.value}{prestige}",
                color=faction_color
            )

            if outfit is not None:
                embed.add_field(name="Outfit", value=f"{outfitTag} {outfit.name}")

            embed.add_field(name="Time played", value=f"{char.times.minutes_played // 60} Hours, {char.times.minutes_played % 60} Minutes")
            embed.add_field(name="Player creation", value=f"<t:{char.times.creation}:D>")
            embed.add_field(name="Last logon", value=f"<t:{char.times.last_save}:R>")

            embed.set_footer(text=f"Process time: {round(time() - startTime, 2)} seconds.", icon_url="https://cdn.tims.host/2/ucsQnspf70JR7FQ.png")

            await interaction.edit_original_response(embed=embed)
