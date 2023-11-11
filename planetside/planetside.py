import asyncio
from datetime import datetime
from time import time
import logging

import aiohttp
import discord
from redbot.core import Config, app_commands, commands

from .static.utils import FACTIONS, SERVER_IDS, CLASSES
from .static.implants import IMPLANTS
from .static.weapons import WEAPONS, WEAPON_NAMES


class Player():
    def __init__(self):
        self.characterID = dict()
        self.character = dict()
        self.hist = dict()
        self.stats = dict()
        self.honuData = dict()
        self.honuMeta = dict()
        self.weaponStats = dict()


def CofUpdated(CoF):
    return CoF != ['?', '?', '?', '?', '?', '?']


def StandingOnly(CoF):
    return CoF[0] != "?" and CoF[1] == "?" and CoF[2] == "?" and CoF[3] == "?" and CoF[4] == "?" and CoF[5] == "?"


class Planetside(commands.Cog):
    """
        Planetside Cog. Contains command for the game Planetside 2.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2162678924, force_registration=True)

        self.honuUrl = "https://wt.honu.pw"

        self.config.register_global(
            serviceId=False
        )

    async def division(self, a, b):
        return a / b if b else 0

    async def getByName(self, username: str, server=None):
        """
            Gets characters stats.
        """
        char = Player()
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self.honuUrl}/api/characters/search/{username}?censusTimeout=true") as response:
                if response.status != 200:
                    logging.info("Honu failed to respond. Code:", response.status, "Content:", await response.text())
                    return None

                responseJson = await response.json()

                if len(responseJson) == 0:
                    return None

                if server is not None:
                    for index, x in enumerate(responseJson):
                        if x["worldID"] != server:
                            responseJson.pop(index)

                char.characterID = responseJson[0]["id"]
                # If exact name found use instead of the last online
                for x in responseJson:
                    if x["name"].lower() == username:
                        char.characterID = x["id"]

            tasks = [
                session.get(url=f"{self.honuUrl}/api/character/{char.characterID}"),
                session.get(url=f"{self.honuUrl}/api/character/{char.characterID}/stats"),
                session.get(url=f"{self.honuUrl}/api/character/{char.characterID}/history_stats"),
                session.get(url=f"{self.honuUrl}/api/character/{char.characterID}/honu-data"),
                session.get(url=f"{self.honuUrl}/api/character/{char.characterID}/metadata"),
                session.get(url=f"{self.honuUrl}/api/character/{char.characterID}/weapon_stats")
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for response in responses:
                # Because return_exceptions we have to 
                # check that the reponse hasnt failed
                if not hasattr(response, 'status'):
                    continue

                if response.status != 200:
                    continue

                endpoint = response.url.path

                if endpoint == f"/api/character/{char.characterID}":
                    char.character = await response.json()
                elif endpoint == f"/api/character/{char.characterID}/stats":
                    char.stats = await response.json()
                elif endpoint == f"/api/character/{char.characterID}/history_stats":
                    char.hist = await response.json()
                elif endpoint == f"/api/character/{char.characterID}/honu-data":
                    char.honuData = await response.json()
                elif endpoint == f"/api/character/{char.characterID}/metadata":
                    char.honuMeta = await response.json()
                elif endpoint == f"/api/character/{char.characterID}/weapon_stats":
                    char.weaponStats = await response.json()

        return char

    @app_commands.command()
    @app_commands.describe(username="Look up a player's stats.")
    async def stats(self, interaction: discord.Interaction, username: str):
        """
            Get stats for a PlanetSide player.
        """
        # Using defer because census responses are sometimes slow
        await interaction.response.defer(thinking=True)

        startTime = time()

        char = await self.getByName(username.lower())

        if char is None:
            await interaction.edit_original_response(
                embed=discord.Embed(title=f"Failed to find player '{username}'", color=0xed333b)
            )
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return

        onlineIcon = "🔴"
        if "online" in char.honuData:
            if char.honuData["online"]:
                onlineIcon = "🟢"

        factionEmoji = FACTIONS[char.character['factionID']]['emoji']
        factionName = FACTIONS[char.character['factionID']]['name']
        factionColor = FACTIONS[char.character['factionID']]['color']
        serverName = SERVER_IDS[char.character['worldID']]

        # If in outfit display outfit in [91AR]
        outfitTag = ""
        if char.character["outfitTag"] is not None:
            outfitTag = f"[{char.character['outfitTag']}] "

        prestige = ""
        if char.character["prestige"] > 0:
            prestige = f"~{char.character['prestige']}"

        # @TODO Character title is missing not provided by honu 😥
        embed = discord.Embed(
            title=f"{onlineIcon} {factionEmoji} {outfitTag}{char.character['name']}",
            description=f"""Of {serverName}'s {factionName}
Battle rank {char.character['battleRank']}{prestige}""",
            color=factionColor
        )

        if "notFoundCount" in char.honuMeta:
            if char.honuMeta["notFoundCount"] > 0:
                embed.add_field(name="Character possibly Deleted", value="This character exists in Honu's database, but not in the Planetside 2 API. Missed {} times".format(char.honuMeta["notFoundCount"]), inline=False)

        if char.character["outfitTag"] is not None:
            embed.add_field(name='Outfit', value=f"[{char.character['outfitTag']}] {char.character['outfitName']}", inline=False)

        # Bit complex but what ever it gets the job done
        playTimePerClass = [0] * 10
        mostPlayedClass = 0
        mostPlayedTime = 0
        for stat in char.stats:
            if stat["statName"] == "play_time":
                classID = stat["profileID"]
                classPlaytime = stat["valueForever"]

                playTimePerClass[classID] = classPlaytime
                if mostPlayedTime <= classPlaytime:
                    mostPlayedClass = classID
                    mostPlayedTime = classPlaytime

        totalPlayTime = sum(playTimePerClass)
        totalPlatTimeMinutes = sum(playTimePerClass) / 60
        totalKills = 0
        totalDeaths = 0
        totalScore = 0

        for x in char.hist:
            if x["type"] == "deaths":
                totalDeaths = x["allTime"]
            if x["type"] == "kills":
                totalKills = x["allTime"]
            if x["type"] == "score":
                totalScore = x["allTime"]

        mostKillsWeaponKills = 0
        mostKillsWeaponID = 0
        for weapon in char.weaponStats:
            if weapon["stat"]["vehicleID"] == 0:
                if mostKillsWeaponKills <= weapon["stat"]["kills"]:
                    mostKillsWeaponKills = weapon["stat"]["kills"]
                    mostKillsWeaponID = int(weapon["itemID"])

        mostUsedVehicle = ""
        mostUsedVehicleTime = 0
        for x in char.weaponStats:
            if x["stat"]["vehicleID"] != 0:
                if mostUsedVehicleTime <= x["stat"]["secondsWith"]:
                    mostUsedVehicle = x["vehicle"]["name"]
                    mostUsedVehicleTime = x["stat"]["secondsWith"]

        embed.add_field(name="K-D ", value=f'{"{:,}".format(totalKills)} - {"{:,}".format(totalDeaths)} = {"{:,}".format(totalKills - totalDeaths)}')
        embed.add_field(name="KDR", value=f"{round(await self.division(totalKills, totalDeaths), 2)}")
        embed.add_field(name="KPM", value=f"{round(await self.division(totalKills, totalPlatTimeMinutes), 2)}")

        embed.add_field(name="Score (SPM)", value=f'{"{:,}".format(totalScore)} ({round(await self.division(totalScore, totalPlatTimeMinutes), 1)})')

        if mostKillsWeaponID in WEAPONS:
            weaponName = WEAPONS[mostKillsWeaponID]["name"]
            embed.add_field(name="Top weapon (Kills)", value=f'{weaponName} ({"{:,}".format(mostKillsWeaponKills)})')

        embed.add_field(name="Time played", value=f"{int(totalPlayTime / 60 // 60)} Hours, {int(totalPlayTime // 60 % 60)} Minutes")

        if "online" in char.honuData:
            if not char.honuData["online"]:
                embed.add_field(name='Last logon', value=f"<t:{char.honuData['latestEventTimestamp'] // 1000}:R>")
        try:
            embed.add_field(name="Player creation", value=f"<t:{datetime.strptime(char.character['dateCreated'], '%Y-%m-%d %H:%M:%SZ').strftime('%s')}:D>")
        except Exception:
            embed.add_field(name="Player creation", value=f"<t:{datetime.strptime(char.character['dateCreated'], '%Y-%m-%dT%H:%M:%SZ').strftime('%s')}:D>")


        if mostPlayedClass != 0:
            embed.add_field(name="Most played class", value=f"**{CLASSES[mostPlayedClass]}** ({int(mostPlayedTime / 60 // 60)}h, {mostPlayedTime // 60 % 60}m) [{round((mostPlayedTime / totalPlayTime) * 100, 1)}%]")

        if mostUsedVehicleTime != 0:
            embed.add_field(
                name="Most used vehicle",
                value=f"{mostUsedVehicle} ({int(mostUsedVehicleTime / 60 // 60)}h, {mostUsedVehicleTime // 60 % 60}m)"
            )
        embed.set_footer(text=f"Process time: {round(time() - startTime, 2)} seconds.", icon_url="https://cdn.tims.host/2/ucsQnspf70JR7FQ.png")

        await interaction.edit_original_response(embed=embed)

    @stats.autocomplete("username")
    async def username_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """
            Autocomplete username results are from honu's character search.
        """
        if len(current) <= 3:
            return []

        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self.honuUrl}/api/characters/search/{current}?censusTimeout=true") as response:
                if response.status != 200:
                    logging.info("Honu failed to respond. Code:", response.status, "Content:", await response.text())
                    return []

                responseJson = await response.json()

        if len(responseJson) == 0:
            return []

        # Move exact match to the first place
        for index, x in enumerate(responseJson):
            if x["name"].lower() == current.lower():
                responseJson.insert(0, responseJson.pop(index))

        autocompleteList = []
        for x in responseJson:
            outfitTag = ""
            if x["outfitTag"] is not None:
                outfitTag = f"[{x['outfitTag']}] "

            autocompleteList.append(app_commands.Choice(name=f'{outfitTag}{x["name"]}', value=x["name"]))

        return autocompleteList[:25]

    @app_commands.command()
    @app_commands.describe(implant="Lookup an implant")
    async def implant(self, interaction: discord.Interaction, implant: str):
        """
            Look up an implant and its stats.
        """
        if implant not in IMPLANTS:
            searchQuery = [x for x in IMPLANTS.keys() if implant.lower() in x.lower()]
            if 0 >= len(searchQuery):
                await interaction.response.send_message(
                    discord.Embed(
                        title=f"Failed to find implant \"{implant}\", Use autocomplete if possible",
                        color=0xed333b
                    )
                )
                return
            else:
                implant = searchQuery[0]

        implant = IMPLANTS[implant]
        embed = discord.Embed(title=implant)

        if "desc" in implant.keys():
            embed.add_field(name="Description", value=implant["desc"], inline=False)
        elif "1" in implant.keys():
            embed.add_field(name="Rank 1", value=implant["1"], inline=False)
            embed.add_field(name="Rank 2", value=implant["2"], inline=False)
            embed.add_field(name="Rank 3", value=implant["3"], inline=False)
            embed.add_field(name="Rank 4", value=implant["4"], inline=False)
            embed.add_field(name="Rank 5", value=implant["5"], inline=False)
        else:
            embed.add_field(name="Lookup failed", value=f"Selected implant \"{implant}\" has data no in it")

        if "image" in implant.keys():
            embed.set_thumbnail(url=f"http://census.daybreakgames.com/files/ps2/images/static/{implant['image']}.png")

        await interaction.response.send_message(embed=embed)

    @implant.autocomplete('implant')
    async def implant_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if current == "":
            return [app_commands.Choice(name=x, value=x) for x in IMPLANTS.keys()][:25]

        return [app_commands.Choice(name=x, value=x) for x in IMPLANTS.keys() if current.lower() in x.lower()][:25]

    @app_commands.command()
    @app_commands.describe(weapon="Lookup an weapon")
    async def weapon(self, interaction: discord.Interaction, weapon: str):
        """
            Look up a weapon and its stats.
        """
        try:
            weaponObj = WEAPONS[int(weapon)]
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title=f"Failed to find Weapon. WeaponID: \"{weapon}\", Use autocomplete if possible",
                    color=0xed333b
                )
            )
            return

        """
        embed = discord.Embed(
            title=weaponObj["name"],
            description=f"```json\n{pprint.pformat(weaponObj, indent=2, width=55)}```"
        )

        await interaction.response.send_message(embed=embed)
        return
        """

        embed = discord.Embed(
            title=weaponObj["name"],
            description=weaponObj["description"]
        )
        embed.set_footer(text=f"Weapon ID: {weapon}")

        if weaponObj["image_id"] != -1:
            embed.set_thumbnail(url=f"http://census.daybreakgames.com/files/ps2/images/static/{weaponObj['image_id']}.png")

        if "category" in weaponObj:
            embed.add_field(name="Category", value=weaponObj["category"])

        if "fireRate" in weaponObj:
            embed.add_field(name="Firerate", value="{} RPM".format(int(60 * (1000 / weaponObj['fireRate']))))

        if "heatCapacity" in weaponObj:
            embed.add_field(name="Heat capacity", value="{}".format(weaponObj["heatCapacity"]))
            embed.add_field(name="Heat per shot", value="{}".format(weaponObj["heatPerShot"]))
            embed.add_field(name="Heat bleed off", value="{}/s".format(weaponObj["heatBleedOff"]))
            embed.add_field(
                name="Recovery delay",
                value=f"""{weaponObj['heatRecoveryDelay']/1000}s
                          {(weaponObj['overheatPenalty'] + weaponObj['heatRecoveryDelay'])/1000} s OverHeat"""
            )
        elif "clip" in weaponObj:
            if "ammo" in weaponObj:
                embed.add_field(
                    name="Ammo",
                    value=f"""Magazine: {weaponObj["clip"]}\nCapacity: {weaponObj["ammo"]}
                    """
                )
            else:
                embed.add_field(
                    name="Ammo",
                    value=f"""Magazine: {weaponObj["clip"]}"""
                )

            if "reload" in weaponObj:
                if "chamber" in weaponObj:
                    embed.add_field(
                        name="Reload",
                        value=f"""Short: {weaponObj["reload"]/1000} s\nLong: {(weaponObj["reload"] + weaponObj["chamber"])/1000} s
                        """
                    )
                else:
                    embed.add_field(
                        name="Reload",
                        value=f"""Reload: {weaponObj["reload"]/1000} s
                        """
                    )
        elif "reload" in weaponObj:
            embed.add_field(
                name="Reload",
                value=f"""Reload: {weaponObj["reload"]/1000} s"""
            )

        if "maxDamage" in weaponObj:
            if "directDamage" in weaponObj:
                if weaponObj["maxDamage"] != weaponObj["directDamage"]:
                    embed.add_field(
                        name="Damage",
                        value=f"""{weaponObj["maxDamage"]} @ {weaponObj["maxDamageRange"]}m\n{weaponObj["minDamage"]} @ {weaponObj["minDamageRange"]}m"""
                    )
                    if "pellets" in weaponObj:
                        embed.add_field(name="Pellets", value=f'{weaponObj["pellets"]}')
                        embed.add_field(name="Pellet spread", value=f'{weaponObj["pelletSpread"]}')

            else:
                embed.add_field(name="Damage", value=f'{weaponObj["maxDamage"]} @ {weaponObj["maxDamageRange"]}m\n{weaponObj["minDamage"]} @ {weaponObj["minDamageRange"]}m')
                if "pellets" in weaponObj:
                    embed.add_field(name="Pellets", value=f'{weaponObj["pellets"]}')
                    embed.add_field(name="Pellet spread", value=f'{weaponObj["pelletSpread"]}')

        if "maxIndirectDamage" in weaponObj and "directDamage" in weaponObj:
            if weaponObj["maxIndirectDamage"] != 0:
                embed.add_field(name="Direct damage", value=f"{weaponObj['directDamage']}")
                embed.add_field(
                    name="Indirect damage",
                    value=f"""{weaponObj["maxIndirectDamage"]} @ {weaponObj["maxIndirectDamageRadius"]}m\n{weaponObj["minIndirectDamage"]} @ {weaponObj["minIndirectDamageRadius"]}m"""
                )
            else:
                embed.add_field(name="Damage", value=f"{weaponObj['directDamage']}")

        elif "maxIndirectDamage" in weaponObj:
            embed.add_field(
                name="Indirect damage",
                value=f"""{weaponObj["maxIndirectDamage"]} @ {weaponObj["maxIndirectDamageRadius"]}m\n{weaponObj["minIndirectDamage"]} @ {weaponObj["minIndirectDamageRadius"]}m"""
            )

        if "speed" in weaponObj:
            embed.add_field(
                name="Muzzle Velocity",
                value="{} m/s".format(weaponObj["speed"])
            )

        if "adsCofRecoil" in weaponObj and "hipCofRecoil" in weaponObj and "verticalRecoil" in weaponObj:
            embed.add_field(
                name="Bloom (hip/ADS)",
                value="{}/{}".format(weaponObj["hipCofRecoil"], weaponObj["adsCofRecoil"])
            )
        elif "hipCofRecoil" in weaponObj and "verticalRecoil" in weaponObj:
            embed.add_field(
                name="Bloom (hip)",
                value="{}".format(weaponObj["hipCofRecoil"])
            )

        if "verticalRecoil" in weaponObj:
            if weaponObj["verticalRecoil"] != 0:
                embed.add_field(
                    name="Vertical Recoil",
                    value="{}".format(weaponObj["verticalRecoil"])
                )
                if "recoilAngleMin" in weaponObj and "recoilAngleMax" in weaponObj:
                    embed.add_field(
                        name="Recoil Angle (Min/Max)",
                        value="{}/{}".format(weaponObj["recoilAngleMin"], weaponObj["recoilAngleMax"])
                    )

        if "recoilHorizontalMin" in weaponObj and "recoilHorizontalMax" in weaponObj:
            embed.add_field(
                name="Horizontal Recoil (min/max)",
                value="{}/{}".format(weaponObj["recoilHorizontalMin"], weaponObj["recoilHorizontalMax"])
            )

        if "recoilHorizontalTolerance" in weaponObj:
            embed.add_field(
                name="Horizontal Tolerance",
                value="{}".format(weaponObj["recoilHorizontalTolerance"])
            )

        if "firstShotMultiplier" in weaponObj:
            embed.add_field(
                name="First Shot Multiplier",
                value="{}".format(weaponObj["firstShotMultiplier"])
            )

        if "fireModes" in weaponObj:
            if len(weaponObj["fireModes"]) != 0:
                embed.add_field(
                    name="Fire Modes",
                    value="\n".join(weaponObj["fireModes"])
                )

        if "headshotMultiplier" in weaponObj:
            embed.add_field(
                name="Headshot Multiplier",
                value="{}x".format(
                    int(weaponObj["headshotMultiplier"]) + 1
                )
            )

        if "defZoom" in weaponObj:
            if weaponObj["defZoom"] != 1:
                embed.add_field(
                    name="Iron Sight Zoom",
                    value="{}x".format(weaponObj["defZoom"])
                )

        hipCOFMin = ["?", "?", "?", "?", "?", "?"]
        hipCOFMax = ["?", "?", "?", "?", "?", "?"]
        adsCOFMin = ["?", "?", "?", "?", "?", "?"]
        adsCOFMax = ["?", "?", "?", "?", "?", "?"]

        if "standingCofMin" in weaponObj:
            hipCOFMin[0] = weaponObj["standingCofMin"]
            hipCOFMax[0] = weaponObj["standingCofMax"]

        if "crouchingCofMin" in weaponObj:
            hipCOFMin[1] = weaponObj["crouchingCofMin"]
            hipCOFMax[1] = weaponObj["crouchingCofMax"]

        if "runningCofMin" in weaponObj:
            hipCOFMin[2] = weaponObj["runningCofMin"]
            hipCOFMax[2] = weaponObj["runningCofMax"]

        if "sprintingCofMin" in weaponObj:
            hipCOFMin[3] = weaponObj["sprintingCofMin"]
            hipCOFMax[3] = weaponObj["sprintingCofMax"]

        if "fallingCofMin" in weaponObj:
            hipCOFMin[4] = weaponObj["fallingCofMin"]
            hipCOFMax[4] = weaponObj["fallingCofMax"]

        if "crouchWalkingCofMin" in weaponObj:
            hipCOFMin[5] = weaponObj["crouchWalkingCofMin"]
            hipCOFMax[5] = weaponObj["crouchWalkingCofMax"]

        if "adsMoveSpeed" in weaponObj:
            embed.add_field(
                name="ADS Move Speed",
                value="{}x".format(weaponObj["adsMoveSpeed"])
            )
            if "standingCofMinADS" in weaponObj:
                adsCOFMin[0] = weaponObj["standingCofMinADS"]
                adsCOFMax[0] = weaponObj["standingCofMaxADS"]

            if "crouchingCofMinADS" in weaponObj:
                adsCOFMin[1] = weaponObj["crouchingCofMinADS"]
                adsCOFMax[1] = weaponObj["crouchingCofMaxADS"]

            if "runningCofMinADS" in weaponObj:
                adsCOFMin[2] = weaponObj["runningCofMinADS"]
                adsCOFMax[2] = weaponObj["runningCofMaxADS"]

            if "sprintingCofMinADS" in weaponObj:
                adsCOFMin[3] = weaponObj["sprintingCofMinADS"]
                adsCOFMax[3] = weaponObj["sprintingCofMaxADS"]

            if "fallingCofMinADS" in weaponObj:
                adsCOFMin[4] = weaponObj["fallingCofMinADS"]
                adsCOFMax[4] = weaponObj["fallingCofMaxADS"]

            if "crouchWalkingCofMinADS" in weaponObj:
                adsCOFMin[5] = weaponObj["crouchWalkingCofMinADS"]
                adsCOFMax[5] = weaponObj["crouchWalkingCofMaxADS"]

        # Convert everything to string so .join() plays nice
        hipCOFMin = [str(x) for x in hipCOFMin]
        hipCOFMax = [str(x) for x in hipCOFMax]
        adsCOFMin = [str(x) for x in adsCOFMin]
        adsCOFMax = [str(x) for x in adsCOFMax]

        if "useInWater" in weaponObj:
            if weaponObj["useInWater"]:
                embed.add_field(
                    name="Usable Underwater",
                    value="Yes"
                )
            else:
                embed.add_field(
                    name="Usable Underwater",
                    value="No"
                )

        if CofUpdated(hipCOFMin) or CofUpdated(adsCOFMin):
            if not StandingOnly(hipCOFMin) or not StandingOnly(adsCOFMin):
                embed.add_field(
                    name="**―――――――――――――――――――**",
                    value="**CoF shown Stand/Crouch/Walk/Sprint/Fall/Crouch Walk**",
                    inline=False
                )

        if CofUpdated(hipCOFMin):
            if StandingOnly(hipCOFMin):
                embed.add_field(
                    name="Hipfire CoF Min",
                    value=hipCOFMin[0]
                )
                embed.add_field(
                    name="Hipfire CoF Max",
                    value=hipCOFMax[0]
                )
                embed.add_field(name="\u200b", value="\u200b")
            else:
                embed.add_field(
                    name="Hipfire CoF Min",
                    value="/".join(hipCOFMin)
                )
                embed.add_field(
                    name="Hipfire CoF Max",
                    value="/".join(hipCOFMax)
                )
                embed.add_field(name="\u200b", value="\u200b")

        if CofUpdated(adsCOFMin):
            if StandingOnly(adsCOFMin):
                embed.add_field(
                    name="ADS CoF Min",
                    value=adsCOFMin[0]
                )
                embed.add_field(
                    name="ADS CoF Max",
                    value=adsCOFMax[0]
                )
                embed.add_field(name="\u200b", value="\u200b")
            else:
                embed.add_field(
                    name="ADS CoF Min",
                    value="/".join(adsCOFMin)
                )
                embed.add_field(
                    name="ADS CoF Max",
                    value="/".join(adsCOFMax)
                )
                embed.add_field(name="\u200b", value="\u200b")

        await interaction.response.send_message(embed=embed)

    @weapon.autocomplete('weapon')
    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if current == "":
            return [app_commands.Choice(name=x, value=str(y)) for y, x in WEAPON_NAMES.items()][:25]

        return [app_commands.Choice(name=x, value=str(y)) for y, x in WEAPON_NAMES.items() if current.lower() in x.lower()][:25]
