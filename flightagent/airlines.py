"""Official booking domains for major airlines, keyed by IATA airline code.

Used when the user has no airline preference: the agent may then check out on
an airline's own site, but only the site that belongs to an airline actually
flying the itinerary. A look-alike, a different airline's site, or a travel
agency is refused unless the user listed it.

An airline that is missing here is not blocked silently: validate says so, and
the user can add its site with `intake --set extra_sellers=<domain>`.
Corrections welcome: one line per airline, domains only.
"""
from __future__ import annotations

REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    # North America
    "AA": ("American Airlines", ("aa.com",)),
    "DL": ("Delta Air Lines", ("delta.com",)),
    "UA": ("United Airlines", ("united.com",)),
    "WN": ("Southwest Airlines", ("southwest.com",)),
    "AS": ("Alaska Airlines", ("alaskaair.com",)),
    "B6": ("JetBlue", ("jetblue.com",)),
    "NK": ("Spirit Airlines", ("spirit.com",)),
    "F9": ("Frontier Airlines", ("flyfrontier.com",)),
    "HA": ("Hawaiian Airlines", ("hawaiianairlines.com",)),
    "G4": ("Allegiant Air", ("allegiantair.com",)),
    "SY": ("Sun Country Airlines", ("suncountry.com",)),
    "MX": ("Breeze Airways", ("flybreeze.com",)),
    "AC": ("Air Canada", ("aircanada.com",)),
    "WS": ("WestJet", ("westjet.com",)),
    "PD": ("Porter Airlines", ("flyporter.com",)),
    "TS": ("Air Transat", ("airtransat.com",)),
    "AM": ("Aeromexico", ("aeromexico.com",)),
    "Y4": ("Volaris", ("volaris.com",)),
    # Latin America
    "LA": ("LATAM Airlines", ("latamairlines.com",)),
    "AV": ("Avianca", ("avianca.com",)),
    "CM": ("Copa Airlines", ("copaair.com",)),
    "AR": ("Aerolineas Argentinas", ("aerolineas.com.ar",)),
    # Europe
    "BA": ("British Airways", ("britishairways.com",)),
    "VS": ("Virgin Atlantic", ("virginatlantic.com",)),
    "AF": ("Air France", ("airfrance.com", "airfrance.us")),
    "KL": ("KLM", ("klm.com", "klm.us")),
    "LH": ("Lufthansa", ("lufthansa.com",)),
    "LX": ("SWISS", ("swiss.com",)),
    "OS": ("Austrian Airlines", ("austrian.com",)),
    "SN": ("Brussels Airlines", ("brusselsairlines.com",)),
    "EW": ("Eurowings", ("eurowings.com",)),
    "IB": ("Iberia", ("iberia.com",)),
    "VY": ("Vueling", ("vueling.com",)),
    "AY": ("Finnair", ("finnair.com",)),
    "SK": ("SAS", ("flysas.com",)),
    "DY": ("Norwegian", ("norwegian.com",)),
    "FI": ("Icelandair", ("icelandair.com",)),
    "TP": ("TAP Air Portugal", ("flytap.com",)),
    "EI": ("Aer Lingus", ("aerlingus.com",)),
    "AZ": ("ITA Airways", ("ita-airways.com",)),
    "LO": ("LOT Polish Airlines", ("lot.com",)),
    "A3": ("Aegean Airlines", ("aegeanair.com",)),
    "TK": ("Turkish Airlines", ("turkishairlines.com",)),
    "PC": ("Pegasus Airlines", ("flypgs.com",)),
    "FR": ("Ryanair", ("ryanair.com",)),
    "U2": ("easyJet", ("easyjet.com",)),
    "W6": ("Wizz Air", ("wizzair.com",)),
    # Middle East and Africa
    "EK": ("Emirates", ("emirates.com",)),
    "QR": ("Qatar Airways", ("qatarairways.com",)),
    "EY": ("Etihad Airways", ("etihad.com",)),
    "FZ": ("flydubai", ("flydubai.com",)),
    "G9": ("Air Arabia", ("airarabia.com",)),
    "GF": ("Gulf Air", ("gulfair.com",)),
    "WY": ("Oman Air", ("omanair.com",)),
    "SV": ("Saudia", ("saudia.com",)),
    "KU": ("Kuwait Airways", ("kuwaitairways.com",)),
    "RJ": ("Royal Jordanian", ("rj.com",)),
    "LY": ("El Al", ("elal.com",)),
    "MS": ("EgyptAir", ("egyptair.com",)),
    "ET": ("Ethiopian Airlines", ("ethiopianairlines.com",)),
    "KQ": ("Kenya Airways", ("kenya-airways.com",)),
    "SA": ("South African Airways", ("flysaa.com",)),
    "AT": ("Royal Air Maroc", ("royalairmaroc.com",)),
    # South Asia
    "AI": ("Air India", ("airindia.com",)),
    "IX": ("Air India Express", ("airindiaexpress.com",)),
    "6E": ("IndiGo", ("goindigo.in",)),
    "SG": ("SpiceJet", ("spicejet.com",)),
    "QP": ("Akasa Air", ("akasaair.com",)),
    "UL": ("SriLankan Airlines", ("srilankan.com",)),
    "PK": ("Pakistan International Airlines", ("piac.com.pk",)),
    "BG": ("Biman Bangladesh Airlines", ("biman-airlines.com",)),
    # East and Southeast Asia, Oceania
    "SQ": ("Singapore Airlines", ("singaporeair.com",)),
    "TR": ("Scoot", ("flyscoot.com",)),
    "CX": ("Cathay Pacific", ("cathaypacific.com",)),
    "JL": ("Japan Airlines", ("jal.co.jp", "jal.com")),
    "NH": ("ANA", ("ana.co.jp",)),
    "KE": ("Korean Air", ("koreanair.com",)),
    "OZ": ("Asiana Airlines", ("flyasiana.com",)),
    "CI": ("China Airlines", ("china-airlines.com",)),
    "BR": ("EVA Air", ("evaair.com",)),
    "CA": ("Air China", ("airchina.com.cn", "airchina.com")),
    "MU": ("China Eastern", ("ceair.com",)),
    "CZ": ("China Southern", ("csair.com",)),
    "TG": ("Thai Airways", ("thaiairways.com",)),
    "MH": ("Malaysia Airlines", ("malaysiaairlines.com",)),
    "GA": ("Garuda Indonesia", ("garuda-indonesia.com",)),
    "PR": ("Philippine Airlines", ("philippineairlines.com",)),
    "5J": ("Cebu Pacific", ("cebupacificair.com",)),
    "VN": ("Vietnam Airlines", ("vietnamairlines.com",)),
    "AK": ("AirAsia", ("airasia.com",)),
    "QF": ("Qantas", ("qantas.com",)),
    "JQ": ("Jetstar", ("jetstar.com",)),
    "VA": ("Virgin Australia", ("virginaustralia.com",)),
    "NZ": ("Air New Zealand", ("airnewzealand.com", "airnewzealand.co.nz")),
}

# Flight search engines. They compare every airline but never sell tickets, so the
# agent searches here and books on the airline's (or a listed agency's) own site.
DEFAULT_SEARCH_SOURCES = ["google.com", "skyscanner.com"]


def name(code: str) -> str:
    entry = REGISTRY.get(code.upper())
    return entry[0] if entry else code


def official_domains(code: str) -> tuple[str, ...]:
    entry = REGISTRY.get(code.upper())
    return entry[1] if entry else ()


def all_official_domains() -> list[str]:
    return sorted({d for _, (_, doms) in REGISTRY.items() for d in doms})


def carriers_of(candidate: dict) -> set[str]:
    """Airline codes that sell or fly this itinerary: the listed carrier plus each flight's prefix."""
    codes = {str(candidate.get("carrier", "")).upper()}
    for seg in candidate.get("segments", []):
        flight = str(seg.get("flight", "")).upper().replace(" ", "")
        if len(flight) >= 3:
            codes.add(flight[:2])
    codes.discard("")
    return codes
