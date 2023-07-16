# @TODO Use indexed dict
FACTIONS = [
    {
        # Yeah I know is a dumb solution but hey it works
        "tag": None,
        "name": None,
        "color": 0x000000,
        "emoji": None
    },
    {
        "tag": "VS",
        "name": "Vanu Sovereignty",
        "color": 0xc061cb,
        "emoji": "<:vs:441405448113881098>"
    },
    {
        "tag": "NC",
        "name": "New Conglomerate",
        "color": 0x62a0ea,
        "emoji": "<:nc:441405432091901972>"
    },
    {
        "tag": "TR",
        "name": "Terran Republic",
        "color": 0xed333b,
        "emoji": "<:tr:1104394643145232395>"
    },
    {
        "tag": "NSO",
        "name": "Nanite Systems Operatives",
        "color": 0x777777,
        "emoji": "<:nso:938862172522573904>"
    }
]

CLASSES = {
    1: "Infiltrator",
    3: "Light Assault",
    4: "Combat Medic",
    5: "Engineer",
    6: "Heavy Assault",
    7: "MAX"
}

SERVERS = [
    "connery",
    "miller",
    "cobalt",
    "emerald",
    "jaeger",
    "soltech",
    "genudine",
    "ceres"
]

SERVER_IDS = {
    1: "Connery",
    10: "Miller",
    13: "Cobalt",
    17: "Emerald",
    19: "Jaeger",
    40: "SolTech",
    1000: "Genudine",
    2000: "Ceres"
}
