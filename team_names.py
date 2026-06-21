# Maps Catalan team names (all variants) to the English name ESPN uses
CATALAN_TO_ESPN = {
    "Mèxic": "Mexico",
    "Sud-Àfrica": "South Africa",
    "Corea Sud": "South Korea",
    "Txèquia": "Czechia",
    "Canadà": "Canada",
    "Bosnia": "Bosnia-Herzegovina",
    "EUA": "United States",
    "Paraguay": "Paraguay",
    "Paraguai": "Paraguay",
    "Qatar": "Qatar",
    "Suïssa": "Switzerland",
    "Brasil": "Brazil",
    "Marroc": "Morocco",
    "Haití": "Haiti",
    "Escòcia": "Scotland",
    "Australia": "Australia",
    "Austràlia": "Australia",
    "Turquia": "Türkiye",
    "Alemanya": "Germany",
    "Curaçao": "Curaçao",
    "Països Baixos": "Netherlands",
    "Japó": "Japan",
    "Costa d'Ivori": "Ivory Coast",   # cometa normal '
    "Costa d\u2019Ivori": "Ivory Coast",  # cometa tipogràfica '
    "Equador": "Ecuador",
    "Suècia": "Sweden",
    "Tunísia": "Tunisia",
    "Espanya": "Spain",
    "Cabo Verde": "Cape Verde",
    "Bélgica": "Belgium",
    "Egipte": "Egypt",
    "Aràbia Saudí": "Saudi Arabia",
    "Uruguay": "Uruguay",
    "Uruguai": "Uruguay",
    "Iran": "Iran",
    "Nova Zelanda": "New Zealand",
    "França": "France",
    "Senegal": "Senegal",
    "Iraq": "Iraq",
    "Noruega": "Norway",
    "Argentina": "Argentina",
    "Algèria": "Algeria",
    "Austria": "Austria",
    "Àustria": "Austria",
    "Jordania": "Jordan",
    "Jordània": "Jordan",
    "Portugal": "Portugal",
    "RD Congo": "Congo DR",
    "Anglaterra": "England",
    "Croàcia": "Croatia",
    "Ghana": "Ghana",
    "Panamà": "Panama",
    "Uzbekistan": "Uzbekistan",
    "Colòmbia": "Colombia",
}

ESPN_TO_CATALAN = {v: k for k, v in CATALAN_TO_ESPN.items()}

# Canonical Catalan name per team (used when writing back to CSV)
CANONICAL_CATALAN = {
    "Paraguay": "Paraguay",
    "Uruguay": "Uruguay",
    "Australia": "Austràlia",
    "Austria": "Àustria",
    "Jordan": "Jordania",
}


def catalan_to_espn(name: str) -> str:
    return CATALAN_TO_ESPN.get(name, name)


def espn_to_catalan(name: str) -> str:
    return ESPN_TO_CATALAN.get(name, name)