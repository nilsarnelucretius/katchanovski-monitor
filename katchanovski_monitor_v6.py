#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPBM Paper - Katchanovski Case Network Monitor v6
==================================================
Full symmetric tracking of BOTH networks with eight capabilities:

  1. Daily scheduler             - daemon or cron; fires every 24h
  2. Growth measurement          - 24h deltas for all key metrics
  3. Network node ledger         - time-series snapshots per run
  4. New-node detection          - emerging amplifiers + Russian OSINT-mimic
  5. Podcast & joint-appearance  - Network A: Katchanovski appearances
  6. Counterspeech appearance    - Network B: symmetric tracking
  7. Norwegian sub-network       - Norway A vs B compressed SPBM test
  8. Broadcast TV module         - NRK / ARD / ZDF as cross-pollination
     (NEW v6)                       nodes: the ONLY format where A- and B-network
                                    audiences share the same information space
                                    simultaneously. TV debate appearances are
                                    tracked as high-priority overlap events.
                                    Audience figures: NRK1 ~1.8M daily (Norway);
                                    ARD Tagesschau ~9.6M daily (Germany);
                                    ZDF Markus Lanz ~4M per episode (Germany)

Usage:
    python3 katchanovski_monitor_v6.py              # One full cycle
    python3 katchanovski_monitor_v6.py daemon       # Continuous 24h loop
    python3 katchanovski_monitor_v6.py compare      # A vs B comparison
    python3 katchanovski_monitor_v6.py growth       # 24h growth table
    python3 katchanovski_monitor_v6.py nodes        # Node ledger dump
    python3 katchanovski_monitor_v6.py appearances  # Network A co-appearance log
    python3 katchanovski_monitor_v6.py counterspeech # Network B appearance log
    python3 katchanovski_monitor_v6.py overlap      # Cross-pollination report
    python3 katchanovski_monitor_v6.py norway       # Norwegian sub-network report
    python3 katchanovski_monitor_v6.py tv           # Broadcast TV report
    python3 katchanovski_monitor_v6.py summary      # Recent run log

Requirements:
    pip install requests beautifulsoup4

Scheduling:
    cron:  0 8 * * * python3 /path/to/katchanovski_monitor_v6.py >> cron.log 2>&1

"""
import json, re, time, datetime, hashlib, sys, os
from pathlib import Path
from collections import defaultdict

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False
    print("WARNING: 'requests' or 'beautifulsoup4' not installed. "
          "Install with: pip install requests beautifulsoup4")

# -- File paths ----------------------------------------------------------------
OUTPUT_DIR   = Path(__file__).parent
LOG_FILE     = OUTPUT_DIR / "katchanovski_monitor_log.jsonl"
REPORT_FILE  = OUTPUT_DIR / "katchanovski_monitor_report.md"
HASHES_FILE  = OUTPUT_DIR / "katchanovski_seen_hashes.json"
NODE_LEDGER    = OUTPUT_DIR / "katchanovski_node_ledger.jsonl"
GROWTH_FILE    = OUTPUT_DIR / "katchanovski_growth.jsonl"
NEW_NODES      = OUTPUT_DIR / "katchanovski_new_nodes.jsonl"
APPEARANCES    = OUTPUT_DIR / "katchanovski_appearances.jsonl"       # Network A
CS_APPEARANCES = OUTPUT_DIR / "katchanovski_cs_appearances.jsonl"    # NEW v4: Network B
OVERLAP_LOG    = OUTPUT_DIR / "katchanovski_overlap.jsonl"           # NEW v4: cross-pollination
TV_LOG         = OUTPUT_DIR / "katchanovski_tv_appearances.jsonl"    # NEW v6: broadcast TV

RUN_INTERVAL_HOURS = 24   # Change to e.g. 6 for more frequent checks

# ==============================================================================
# NETWORK A - PRO-BOOK AMPLIFICATION (SPBM narrative spread)
# ==============================================================================

NETWORK_A_AMPLIFIERS = {
    # Principal tier
    "musk":       {"handle": "@elonmusk",          "followers": 200_000_000,
                   "tier": "principal",
                   "role": "Platform owner; GoFundMe supporter; personal X amplification",
                   "platforms": ["X"],
                   "check_url": None},
    "sacks":      {"handle": "@davidsacks47",       "followers": 800_000,
                   "tier": "principal",
                   "role": "White House AI/Crypto advisor; $5,000 GoFundMe donor",
                   "platforms": ["X"],
                   "check_url": None},
    # Layer 2/3 amplifiers
    "carlson":    {"handle": "@TuckerCarlson",      "followers": 15_000_000,
                   "tier": "amplifier",
                   "role": "G_right; Tucker on X; Putin interview 2024",
                   "platforms": ["X", "YouTube"],
                   "check_url": None},
    "greenwald":  {"handle": "@ggreenwald",         "followers": 2_000_000,
                   "tier": "amplifier",
                   "role": "G_left; System Update; Guardian background",
                   "platforms": ["X", "YouTube", "Substack"],
                   "check_url": None},
    "sachs_j":    {"handle": "@JeffDSachs",         "followers": 500_000,
                   "tier": "amplifier",
                   "role": "G_hybrid; Columbia professor; anti-NATO framing",
                   "platforms": ["X"],
                   "check_url": None},
    "macgregor":  {"handle": "@Douglas_Macgregor",  "followers": 600_000,
                   "tier": "amplifier",
                   "role": "G_right; retired colonel; Carlson regular",
                   "platforms": ["X", "YouTube"],
                   "check_url": None},
    "napolitano": {"handle": "@JudgeNap",           "followers": 800_000,
                   "tier": "amplifier",
                   "role": "G_right; Judging Freedom YouTube; hosts Mearsheimer/Sachs/Macgregor",
                   "platforms": ["X", "YouTube"],
                   "check_url": None},
    "diesen":     {"handle": "@Glenn_Diesen",       "followers": 100_000,
                   "tier": "amplifier",
                   "role": "G_hybrid Norway; NOK 7.8M revenue 2025; hosts Mearsheimer/Dugin",
                   "platforms": ["X", "YouTube", "Substack", "Rumble"],
                   "check_url": None},
    "mearsheimer":{"handle": None,                  "followers": 500_000,
                   "tier": "amplifier",
                   "role": "G_hybrid; 28M+ YouTube views; Chicago professor",
                   "platforms": ["YouTube"],
                   "check_url": None},
    "haiphong":   {"handle": "@SpiritofHo",         "followers": 200_000,
                   "tier": "amplifier",
                   "role": "G_left; YouTube; RT amplification",
                   "platforms": ["X", "YouTube"],
                   "check_url": None},

    # -- Norwegian A-network nodes (NEW v5) ------------------------------------
    # Diesen is already above; these are additional Norwegian nodes
    "peace_justice_no": {
        "handle": None, "followers": 5_000,
        "tier": "amplifier",
        "role": "Norwegian political party; Peace and Justice (FOR); Diesen campaign vehicle; "
                "documented Russian narrative proxy; opposed to Norwegian arms to Ukraine; "
                "funding transparency questions (1.4M NOK campaign, 50k NOK reported donation)",
        "platforms": ["X", "Facebook"],
        "check_url": None,
        "country": "NO",
        "note": "Governing Mayor of Oslo called campaign 'echo of Russian propaganda'"},
    "nistad_no": {
        "handle": None, "followers": 3_000,
        "tier": "peripheral",
        "role": "Norwegian historian; runs pro-Kremlin blog; Crimea annexation defender; "
                "compares Crimea annexation to Norwegian history",
        "platforms": ["blog"],
        "check_url": None,
        "country": "NO"},

    # -- Russian OSINT-mimic / Telegram infrastructure (NEW v5) ---------------
    # These are Russian-side 'weaponised OSINT' nodes that amplify A-network
    # narratives through the appearance of independent analysis
    "war_on_fakes": {
        "handle": "@waronfakes",    "followers": 1_000_000,
        "tier": "ru_infrastructure",
        "role": "Russian state-adjacent OSINT-mimic; apes Bellingcat aesthetics to spread "
                "Kremlin narratives; claimed Bucha massacre was staged; active on Telegram/VK; "
                "'participatory propaganda' network",
        "platforms": ["Telegram", "VKontakte"],
        "check_url": None,
        "country": "RU"},
    "rybar_tg": {
        "handle": "@rybar",         "followers": 1_300_000,
        "tier": "ru_infrastructure",
        "role": "Russian Telegram military channel; run by Mikhail Zvinchuk (former defence analyst); "
                "perceived proximity to frontline = authority; feeds Kremlin preferred narratives",
        "platforms": ["Telegram"],
        "check_url": None,
        "country": "RU"},
    "readovka_tg": {
        "handle": "@readovkanews",  "followers": 850_000,
        "tier": "ru_infrastructure",
        "role": "Russian Telegram channel; parallel newsroom feeding Kremlin narratives",
        "platforms": ["Telegram"],
        "check_url": None,
        "country": "RU"},
    "pravda_network": {
        "handle": None,             "followers": None,
        "tier": "ru_infrastructure",
        "role": "DFRLab-identified pro-Kremlin fake news network (pravda-fr.com, pravda-de.com etc.); "
                "poisons OSINT gathering and AI training datasets; "
                "used to launder A-network narratives through fake local news sites",
        "platforms": ["web", "Telegram"],
        "check_url": None,
        "country": "RU"},
}

NETWORK_A_URLS = {
    "springer_accesses": {
        "url": "https://link.springer.com/book/10.1007/978-3-031-98724-3",
        "pattern": r'(\d[\d,k]+)\s*[Aa]ccess',
        "baseline_value": 248000,
        "baseline_label": "248k (March 31, 2026)",
        "description": "Springer book access count",
        "metric_key": "springer_accesses",
    },
    "gofundme": {
        "url": "https://www.gofundme.com/f/openaccess-book-russiaukraine-war-its-origin",
        "pattern": r'(\d[\d,]+)\s*(donors?|contributions?)',
        "baseline_value": 325,
        "baseline_label": "325+ contributors",
        "description": "GoFundMe donor count",
        "metric_key": "gofundme_donors",
    },
}

NETWORK_A_SEARCHES = [
    "Katchanovski Musk X amplification",
    "Katchanovski Carlson Greenwald",
    "Katchanovski Mearsheimer Sachs",
    "Katchanovski Palgrave book spread",
    "Katchanovski BSW AfD Wagenknecht",
    "Katchanovski Stortinget Bundestag congress",
    "Katchanovski Diesen Varwick Norway",
    '"Russia Ukraine War Origins" Katchanovski viral',
    # Norwegian A-network (NEW v5)
    "Katchanovski Diesen Fred Rettferdighet Norway",
    "Katchanovski Peace Justice party Norway FOR",
    "Katchanovski Nistad Norway blog",
    "Diesen Katchanovski Greater Eurasia Podcast",
    # Russian OSINT-mimic amplification (NEW v5)
    "Katchanovski Rybar Telegram",
    "Katchanovski War on Fakes WarFakes",
    "Katchanovski Readovka Telegram Russia",
    "Katchanovski Pravda network disinformation site",
    "Katchanovski RT Sputnik Russia state media 2026",
]

# ==============================================================================
# NETWORK B - COUNTERSPEECH (Mchangama framework test)
# ==============================================================================

NETWORK_B_AMPLIFIERS = {
    "umland":         {"handle": "@UmlandAndreas",           "followers": None,
                       "tier": "initiator",
                       "role": "Petition initiator; NaUKMA; Democratic Platform",
                       "platforms": ["X"],
                       "outlets": ["Ukrainska Pravda", "Deutsche Welle"]},
    "aslund":         {"handle": "@anders_aslund",           "followers": 357_000,
                       "tier": "amplifier",
                       "role": "Highest-reach signatory; Atlantic Council; daily poster",
                       "platforms": ["X", "Bluesky"],
                       "outlets": ["FT", "Politico", "Atlantic Council", "NYT"],
                       "note": "324.9k X + 32k Bluesky = 357k combined"},
    "finnin":         {"handle": "@RoryFinnin",              "followers": None,
                       "tier": "amplifier",
                       "role": "Cambridge Ukrainian Studies; UK media",
                       "platforms": ["X"],
                       "outlets": ["UK broadsheets", "Times Higher Ed"]},
    "fish":           {"handle": None,                       "followers": None,
                       "tier": "amplifier",
                       "role": "UC Berkeley; US policy media",
                       "platforms": [],
                       "outlets": ["US academic/policy media"]},
    "etkind":         {"handle": None,                       "followers": None,
                       "tier": "amplifier",
                       "role": "CEU Vienna; Russian studies",
                       "platforms": [],
                       "outlets": ["European academic media"]},
    "grabowicz":      {"handle": None,                       "followers": None,
                       "tier": "amplifier",
                       "role": "Harvard Ukrainian Research Institute",
                       "platforms": [],
                       "outlets": ["Harvard media; US academic"]},
    "gentile":        {"handle": None,                       "followers": None,
                       "tier": "amplifier",
                       "role": "University of Oslo - ONLY NORWEGIAN SIGNATORY",
                       "platforms": [],
                       "outlets": ["Aftenposten", "Dagbladet", "NRK"],
                       "note": "Critical for Norwegian case study"},
    "budjeryn":       {"handle": None,                       "followers": None,
                       "tier": "amplifier",
                       "role": "MIT Nuclear Security; arms control media",
                       "platforms": [],
                       "outlets": ["Arms Control Today", "Bulletin of Atomic Scientists"]},
    "aslund_bluesky": {"handle": "andersaslund.bsky.social", "followers": 32_000,
                       "tier": "amplifier",
                       "role": "Aslund Bluesky channel",
                       "platforms": ["Bluesky"],
                       "note": "Non-Musk platform; counterspeech structural advantage"},

    # -- Norwegian B-network signatories and media critics (NEW v5) ------------
    "heier_no": {
        "handle": None, "followers": 10_000,
        "tier": "signatory_NO",
        "role": "Professor Military Strategy & Operations, Forsvarets hogskole; "
                "Guest Researcher Boston University; 32 years Norwegian Army officer; "
                "regular Ukrainapodden and Forsvarspodden guest; cited in SPBM paper",
        "platforms": ["podcast"],
        "country": "NO",
        "outlets": ["Forsvarspodden", "Ukrainapodden", "Aftenposten"]},
    "mjor_no": {
        "handle": None, "followers": 5_000,
        "tier": "academic_counterspeech_NO",
        "role": "Kare Johan Mjor - Russian studies scholar; Vagant review documented "
                "Diesen's work as propaganda; selective sources; lacks scholarly rigour",
        "platforms": ["academic"],
        "country": "NO",
        "outlets": ["Vagant", "academic journals"]},
    "holtsmark_no": {
        "handle": None, "followers": 5_000,
        "tier": "academic_counterspeech_NO",
        "role": "Sven G. Holtsmark - historian; documented Diesen's misrepresentation "
                "of sources; argues claims mirror Kremlin propaganda; called for "
                "university research ethics board investigation",
        "platforms": ["academic"],
        "country": "NO",
        "outlets": ["academic journals", "Aftenposten", "NRK"]},
    "berger_no": {
        "handle": "@BjornJBerger",  "followers": 8_000,
        "tier": "OSINT_media_critic_NO",
        "role": "Bjorn Johan Berger - Norwegian independent OSINT analyst and media critic; "
                "economist and public debater; board member Norwegian-Ukrainian friendship assoc.; "
                "UNIQUE FUNCTION: documents how NRK and mainstream Norwegian media "
                "inadvertently whitewash Russian narratives through legitimate coverage; "
                "has forced multiple NRK corrections (Diesen 2022, Avdiivka 2024, "
                "cluster munitions 2023, referendum interviews 2022); "
                "primary platforms: LinkedIn, Facebook, X; "
                "impact-per-follower disproportionately high - NRK-level corrections",
        "platforms": ["X", "LinkedIn", "Facebook"],
        "country": "NO",
        "outlets": ["Stratagem", "Medier24", "LinkedIn"],
        "note": "Closest international equivalents: Kamil Galeev (RU internal), "
                "Oliver Alexander (DK military OSINT) - but Berger's specific function "
                "(mainstream media whitewashing critic) is unique at individual level"},

    # -- Counter-OSINT institutional nodes (NEW v5) ----------------------------
    "bellingcat": {
        "handle": "@bellingcat",    "followers": 500_000,
        "tier": "counter_OSINT",
        "role": "Bellingcat - Netherlands-based OSINT investigative journalism; "
                "gold standard: MH17, Skripal, Navalny; 30+ staff in 20 countries; "
                "banned as undesirable organisation by Russia 2022; "
                "expanding to US 2025; Olof Palme Prize 2024; "
                "most likely to investigate Katchanovski amplification network",
        "platforms": ["web", "X", "YouTube"],
        "country": "NL"},
    "dfrlab": {
        "handle": "@DFRLab",        "followers": 200_000,
        "tier": "counter_OSINT",
        "role": "Digital Forensic Research Lab (Atlantic Council); "
                "documented Doppelganger, Secondary Infektion, Pravda Network; "
                "Foreign Interference Attribution Tracker (FIAT); "
                "specific expertise in Russian influence network mapping",
        "platforms": ["web", "X"],
        "country": "US"},
    "euvsdisinfo": {
        "handle": "@EUvsDisinfo",   "followers": 120_000,
        "tier": "counter_OSINT",
        "role": "EU External Action Service FIMI monitoring unit; "
                "tracks FIMI operations systematically; Democracy Shield instrument; "
                "covered 2025 as year of 'iceberg and galaxy' disinformation frameworks",
        "platforms": ["web", "X"],
        "country": "EU"},
    "cir_eyes_russia": {
        "handle": "@InfoResearch",  "followers": 50_000,
        "tier": "counter_OSINT",
        "role": "Centre for Information Resilience - UK-based; "
                "runs Eyes on Russia project; "
                "Russian disinformation campaign documentation; "
                "Ukraine office led by Yuliia Chykolba",
        "platforms": ["web", "X"],
        "country": "UK"},
    "osint_for_ukraine": {
        "handle": "@OSINTua",       "followers": 30_000,
        "tier": "counter_OSINT",
        "role": "OSINT For Ukraine - Hague-registered foundation; "
                "war crimes investigation + disinformation research (CIDER project); "
                "Project Mariupol; trains OSINT investigators",
        "platforms": ["web", "X"],
        "country": "NL"},

    # -- Fact-checkers (NEW v5) -------------------------------------------------
    "correctiv_de": {
        "handle": "@correctiv_org", "followers": 150_000,
        "tier": "fact_checker",
        "role": "CORRECTIV - Germany; first non-profit investigative newsroom in German-speaking world; "
                "HIGHEST PRIORITY fact-checker for SPBM: documented Doppelganger, "
                "100 fake election websites Jan 2025, AfD/far-right meetings (Secret Plan 2024); "
                "designated undesirable organisation in Russia 2025; "
                "BSW/Katchanovski connection is natural Correctiv story",
        "platforms": ["web", "X"],
        "country": "DE",
        "note": "Has not yet covered Katchanovski - monitoring for first coverage"},
    "faktisk_no": {
        "handle": "@faktisk",       "followers": 40_000,
        "tier": "fact_checker",
        "role": "Faktisk.no - Norway; collaboration of NRK, VG, Dagbladet, TV2; "
                "STRUCTURAL TENSION: NRK is both Faktisk co-owner and platform "
                "criticised by Berger for spreading Russian narratives; "
                "Faktisk coverage of Katchanovski = NRK's own fact-checking arm "
                "assessing a case where NRK has been criticised; "
                "50% of Norwegian population aware of Faktisk",
        "platforms": ["web", "X"],
        "country": "NO"},
    "politifact_us": {
        "handle": "@PolitiFact",    "followers": 1_200_000,
        "tier": "fact_checker",
        "role": "PolitiFact - US; covers Ukraine-related viral claims (Zelensky yachts, "
                "USAID spending etc.); has NOT covered Katchanovski academic book; "
                "outside their typical methodology (viral claims vs academic publishing); "
                "monitor for Musk/Sacks GoFundMe angle which IS in their scope",
        "platforms": ["web", "X"],
        "country": "US"},
    "full_fact_uk": {
        "handle": "@FullFact",      "followers": 180_000,
        "tier": "fact_checker",
        "role": "Full Fact - UK; UK political claims focus; "
                "has NOT covered Katchanovski; outside typical scope; "
                "monitor for UK political angle (Boris Johnson/Istanbul claims)",
        "platforms": ["web", "X"],
        "country": "UK"},
}

NETWORK_B_URLS = {
    "umland_petition": {
        "url": "https://www.pravda.com.ua/eng/articles/2026/04/28/8032087/",
        "pattern": r'(\d+)\s*(scholar|signator)',
        "baseline_value": 107,
        "baseline_label": "107 signatories (April 28, 2026)",
        "description": "Umland petition signatories",
        "metric_key": "petition_signatories",
    },
    "altmetric_book": {
        "url": "https://link.altmetric.com/details/182006045",
        "pattern": r'(\d[\d,]+)\s*[Xx]\s*posts?',
        "baseline_value": 3174,
        "baseline_label": "3,174 X posts (April 1, 2026)",
        "description": "Altmetric / X post count for book",
        "metric_key": "altmetric_x_posts",
    },
    "bluesky_check": {
        "url": "https://bsky.app/search?q=Katchanovski",
        "pattern": r'(\d+)\s*results?',
        "baseline_value": 5,
        "baseline_label": "5 results (April 1, 2026) - platform asymmetry indicator",
        "description": "Bluesky search results for Katchanovski",
        "metric_key": "bluesky_results",
    },
}

NETWORK_B_SEARCHES = [
    "Umland Katchanovski petition scholars",
    "Aslund Katchanovski warning",
    '"collective warning" Katchanovski Palgrave',
    "Katchanovski journal review academic",
    "Katchanovski Palgrave Springer publisher response",
    "Katchanovski retract correction editorial",
    "Katchanovski Norway Gentile Oslo",
    "Katchanovski Times Higher Education review",
    # Norwegian B-network (NEW v5)
    "Katchanovski Ukrainapodden Nettavisen Norway",
    "Katchanovski Forsvarspodden Norway defense",
    "Katchanovski Berger NRK Norway media criticism",
    "Katchanovski Heier Norway Forsvarets hogskole",
    "Katchanovski Holtsmark Mjor Norway",
    "Katchanovski Faktisk Norway fact-check",
    "Diesen Katchanovski Norway counterspeech",
    "Katchanovski Aftenposten NRK Norwegian coverage",
    # Counter-OSINT searches (NEW v5)
    "Katchanovski Bellingcat OSINT investigation",
    "Katchanovski DFRLab Atlantic Council investigation",
    "Katchanovski EUvsDisinfo FIMI disinformation",
    "Katchanovski Correctiv Germany fact-check investigation",
    "Katchanovski amplification network Musk Sacks OSINT",
    "Katchanovski influence operation academic publishing",
    # Russian infrastructure monitoring (NEW v5) - B watches A's infrastructure
    "Katchanovski Rybar WarFakes amplification Russia",
    "Katchanovski Pravda network fake sites",
    "Diesen Peace Justice Norway Kremlin proxy investigation",
    # Broadcast TV cross-pollination signals (NEW v6)
    # These are the highest-quality overlap events: genuine shared audience
    'Katchanovski NRK Debatten debate Norway',
    'Diesen Katchanovski NRK Dagsrevyen Norway TV',
    'Katchanovski ZDF Markus Lanz debate Germany',
    'Katchanovski ARD Tagesschau Germany television report',
    'Varwick Katchanovski ZDF ARD Germany television',
    'Wagenknecht Katchanovski ZDF ARD debate Germany',
    'Katchanovski television NRK ARD ZDF debate 2026',
]

# TV channel names for overlap detection - separate from A/B nodes
TV_NODE_NAMES = {
    "NRK", "NRK Debatten", "NRK Urix", "Dagsrevyen", "NRK Nyheter",
    "Helgemorgen", "TV 2", "TV2",
    "Tagesschau", "ARD", "ZDF", "Markus Lanz", "heute-journal",
    "Maybrit Illner", "Hart aber fair", "Phoenix", "Tagesthemen",
    "Brennpunkt", "ZDFinfo", "ZDF Spezial",
}


# ==============================================================================
# BROADCAST TV MODULE  (NEW v6)
# ==============================================================================
#
# TV debate formats are qualitatively different from all other nodes because
# they are the ONLY format where A-network and B-network audiences share the
# same information space simultaneously - genuine audience overlap, not proxy.
#
# ANALYTICAL SIGNIFICANCE FOR SPBM PAPER:
#   A TV debate where Katchanovski/Diesen appears alongside a counter-voice
#   is direct empirical evidence of the SPBM cross-spectrum dynamic in the
#   mass public sphere - not confined to pre-sorted echo-chamber audiences.
#
# Verified audience figures (2024/2025):
#   NRK1 (Norway):         ~1.8M daily viewers (35.2% market share 2023)
#   ARD Tagesschau 20:00:  ~9.6M average daily (2024); 11.1M election night
#   ZDF Markus Lanz:       ~3-4M per episode
#   ARD/ZDF joint debates: up to 12.9M (election night Feb 2025)
#   TV 2 (Norway):         ~850k daily (17.2% market share 2023)
# ------------------------------------------------------------------------------

BROADCAST_NODES = {
    "NRK": {
        "key": "nrk_norway", "country": "NO", "language": "NO",
        "audience_daily": 1_800_000,
        "audience_note": "NRK1 35.2% market share 2023; NRK total 42% combined",
        "key_formats": ["NRK Nyheter", "NRK Debatten", "NRK Urix",
                        "NRK Helgemorgen", "Dagsrevyen"],
        "spbm_relevance": "DUAL ROLE: A-network whitewashing vector (Berger mechanism; "
                          "Diesen given uncritical platform) AND potential B-network coverage. "
                          "Faktisk co-owner. Most important Norwegian TV node.",
        "x_handle": "@NRK",
        "tier": "tier_1_broadcast",
    },
    "TV2_Norway": {
        "key": "tv2_norway", "country": "NO", "language": "NO",
        "audience_daily": 850_000,
        "audience_note": "TV 2 Direkte 17.2% market share 2023; second largest Norway",
        "key_formats": ["TV 2 Nyhetskanalen", "God morgen Norge", "Debatten"],
        "spbm_relevance": "Commercial Norwegian broadcaster; second largest; "
                          "Ukraine/Russia coverage; potential Katchanovski/Diesen venue",
        "x_handle": "@TV2Norge",
        "tier": "tier_2_broadcast",
    },
    "ARD_Das_Erste": {
        "key": "ard_das_erste", "country": "DE", "language": "DE",
        "audience_daily": 9_600_000,
        "audience_note": "Tagesschau 20:00 avg 9.6M daily (2024); 11.1M election night Feb 2025; "
                         "ARD/ZDF joint debate 12.9M; Tagesschau most trusted German news",
        "key_formats": ["Tagesschau", "Tagesthemen", "Brennpunkt",
                        "Maybrit Illner", "Hart aber fair"],
        "spbm_relevance": "Varwick is regular ARD guest (Deutschlandfunk, BR, SWR, ARD Mitreden); "
                          "BSW/AfD MPs appear in debates; Correctiv Secret Plan scoop triggered "
                          "massive ARD coverage. Most likely German TV venue for Katchanovski.",
        "x_handle": "@ARD_Presse",
        "tier": "tier_1_broadcast",
    },
    "ZDF": {
        "key": "zdf_germany", "country": "DE", "language": "DE",
        "audience_daily": 4_500_000,
        "audience_note": "heute-journal 3-5M per episode; Markus Lanz ~3-4M; 13% market share; "
                         "Putins Agenten docuseries broadcast Feb 24, 2026 (3 x 30 min, "
                         "Russian intelligence operations)",
        "key_formats": ["heute-journal", "Markus Lanz", "ZDF Spezial",
                        "Terra X", "ZDFinfo", "Putins Agenten"],
        "spbm_relevance": "Putins Agenten (Feb 24, 2026) = ZDF already covering Russian "
                          "intelligence operations. Markus Lanz features Ukraine war experts "
                          "and BSW critics regularly. Wagenknecht appears in ZDF political debates.",
        "x_handle": "@ZDF",
        "tier": "tier_1_broadcast",
    },
    "Phoenix": {
        "key": "phoenix_ard_zdf", "country": "DE", "language": "DE",
        "audience_daily": 700_000,
        "audience_note": "ARD/ZDF joint news channel; ~1-2% market share; policy-focused; "
                         "co-broadcast ARD/ZDF election debate Feb 2025 (12.9M combined)",
        "key_formats": ["Phoenix Runde", "Vor Ort", "Unter den Linden"],
        "spbm_relevance": "Policy audience; live Bundestag and election debate coverage; "
                          "Varwick and BSW guests appear; co-broadcast ARD/ZDF joint debates.",
        "x_handle": "@phoenix_de",
        "tier": "tier_2_broadcast",
    },
}

# TV-specific search terms - broadcast coverage detection
TV_SEARCHES = [
    # Norway - NRK specific formats
    'Katchanovski NRK Debatten Norway television',
    'Katchanovski NRK Dagsrevyen Norway TV news',
    'Katchanovski NRK Urix Ukraine Norway',
    'Katchanovski NRK Helgemorgen Norway debate',
    'Diesen NRK Norway television debate 2026',
    'Katchanovski "TV 2" Norway television coverage',
    '"NRK" "Katchanovski" OR "Diesen" 2026 debatt',
    # Norway - NRK whitewashing via TV (Berger mechanism)
    'Berger NRK Katchanovski whitewash Norway TV criticism',
    # Germany - ARD
    'Katchanovski ARD Tagesschau Germany television',
    'Katchanovski ARD "Maybrit Illner" OR "Hart aber fair"',
    'Katchanovski ARD Brennpunkt Ukraine Germany',
    'Varwick Katchanovski ARD television debate Germany',
    'Wagenknecht BSW Katchanovski ARD debate Germany',
    # Germany - ZDF
    'Katchanovski ZDF "Markus Lanz" Germany television',
    'Katchanovski ZDF "heute-journal" Germany Ukraine',
    'Katchanovski ZDF "Putins Agenten" influence operations',
    'Varwick Katchanovski ZDF Markus Lanz television',
    'Diesen ZDF ARD Germany debate Ukraine 2026',
    # Phoenix / joint debates
    'Katchanovski Phoenix ARD ZDF debate Germany',
    '"Katchanovski" "Phoenix Runde" Ukraine Russia',
    # Highest-priority cross-network TV events
    '"Katchanovski" Tagesschau OR "heute-journal" OR "NRK Nyheter"',
    '"Katchanovski" "Markus Lanz" OR "Maybrit Illner" OR "NRK Debatten"',
    # TV coverage of Umland petition
    'Umland petition NRK ZDF ARD television coverage',
    'Katchanovski book television debate Norway Germany 2026',
]

# ==============================================================================
# NEW-NODE DETECTION - searches for emerging amplifiers (NEW in v2)
# ==============================================================================
# These searches look for patterns suggesting coordinated new amplification -
# politicians, media outlets, academics, or influencers suddenly engaging
# with the Katchanovski book who were not previously in the network.

NEW_NODE_SEARCHES = [
    # Political amplification signals (most important)
    'Katchanovski Stortinget',
    'Katchanovski Bundestag OR Bundesrat',
    'Katchanovski congress senate',
    'Katchanovski BSW Wagenknecht Lafontaine',
    'Katchanovski AfD Gauland Chrupalla',
    'Katchanovski RN Le Pen Bardella',
    'Katchanovski Kremlin state media',
    # Academic amplification signals
    'Katchanovski professor university review endorsement',
    'Katchanovski syllabus course required reading',
    'Katchanovski academic journal citation 2026',
    # Media amplification signals
    'Katchanovski RT Sputnik TASS 2026',
    'Katchanovski interview podcast 2026',
    'Katchanovski Dugin Prilepin',
    # Publisher signals
    'Palgrave Katchanovski publisher statement',
    'Springer Katchanovski retract withdraw',
    # Counterspeech escalation signals
    'Katchanovski Mchangama free speech censorship',
    'Katchanovski petition cancel culture',
    'Katchanovski academic freedom Carlson Greenwald',
    # Norwegian-specific (SPBM paper priority)
    'Katchanovski Diesen Varwick Norwegian parliament',
    'Katchanovski Heier Wilhelmsen Norway',
    'Katchanovski NRK Aftenposten Dagbladet',
    # Norwegian political party signals (NEW v5)
    'Katchanovski "Fred og Rettferdighet" Norway',
    'Katchanovski "Peace and Justice" Norway Stortinget',
    'Diesen "Peace and Justice" Katchanovski campaign',
    # Russian OSINT-mimic amplification (NEW v5)
    'Katchanovski Rybar Telegram Russia',
    'Katchanovski WarFakes "War on Fakes" Russia',
    'Katchanovski Readovka Telegram',
    'Katchanovski "Pravda network" disinformation',
    '"Katchanovski" site:pravda-de.com OR site:pravda-fr.com',
    # Counter-OSINT investigation signals (NEW v5)
    'Katchanovski Bellingcat investigation 2026',
    'Katchanovski DFRLab influence operation 2026',
    'Katchanovski Correctiv investigation Germany 2026',
]

# Keyword patterns that flag a result as a potential new node
NEW_NODE_INDICATORS = [
    # New political actors
    r'\b(senator|congressman|MP|MEP|stortingsrepresentant|Bundestag)\b',
    r'\b(minister|secretary|chancellor|president)\b',
    # New media outlets
    r'\b(RT|Sputnik|TASS|RIA Novosti|Izvestia)\b',
    r'\b(Fox News|MSNBC|CNN|BBC|Guardian|NYT)\b',
    # New academic actors
    r'\b(professor|PhD|university|institute|think.?tank)\b',
    # New influencer signals
    r'\b(\d[\d,]+)\s*(followers?|subscribers?|views?)\b',
    # Platform signals
    r'\b(viral|trending|thread|goes viral|retweet|share)\b',
    # Russian OSINT-mimic infrastructure (NEW v5)
    r'\b(Rybar|WarFakes|War on Fakes|Readovka|Voenny Osvedomitel|WarGonzo)\b',
    r'\b(Telegram channel|mil.?blog|military blogger)\b',
    r'\bpravda-\w+\.com\b',
    # Norwegian political (NEW v5)
    r'\b(Fred og Rettferdighet|Peace and Justice|FOR party|Stortinget)\b',
    r'\b(NRK|Aftenposten|Dagbladet|Nettavisen|VG)\b',
    # Counter-OSINT investigation signals (NEW v5)
    r'\b(Bellingcat|DFRLab|EUvsDisinfo|Correctiv|Faktisk)\b',
    r'\b(influence operation|FIMI|disinformation network|fake news network)\b',
]

# ==============================================================================
# PODCAST & JOINT-APPEARANCE MODULE  (NEW v3)
# ==============================================================================
#
# Purpose: track every podcast, interview, or joint appearance Katchanovski
# makes - especially ones involving identified SPBM nodes from the paper.
# Each confirmed co-appearance is a documented network edge, and its reach
# can be estimated from the host's known audience size. Over time this builds
# a dynamic co-appearance graph showing how Katchanovski's amplification
# network grows through repeated joint appearances.
#
# SPBM analytical logic: a co-appearance with Sachs (500k followers) or
# Mearsheimer (28M YouTube views) is not just reach addition - it is
# cross-audience legitimation. The two actors' audiences partially overlap
# but each brings a distinct ideological cluster (G_left, G_right, G_hybrid).
# Repeated co-appearances build the mutual-endorsement dynamic documented
# in Section 6.8 (Message A) of the SPBM paper.
# ------------------------------------------------------------------------------

# Known SPBM nodes - used to classify co-appearances by SPBM tier
SPBM_NODES = {
    # Name fragment -> node metadata for matching in search results
    "Sachs":       {"key": "sachs_j",    "tier": "amplifier", "cluster": "G_hybrid",
                    "followers": 500_000,  "platforms": ["X", "podcast"],
                    "note": "Columbia professor; anti-NATO framing"},
    "Mearsheimer": {"key": "mearsheimer","tier": "amplifier", "cluster": "G_hybrid",
                    "followers": 500_000,  "platforms": ["YouTube"],
                    "note": "28M+ YouTube views; Chicago; structural realism"},
    "Diesen":      {"key": "diesen",     "tier": "amplifier", "cluster": "G_hybrid_NO",
                    "followers": 100_000,  "platforms": ["YouTube","Substack","Rumble"],
                    "note": "Norway; NOK 7.8M revenue; hosts Mearsheimer/Dugin"},
    "Carlson":     {"key": "carlson",    "tier": "amplifier", "cluster": "G_right",
                    "followers": 15_000_000, "platforms": ["X","YouTube"],
                    "note": "Tucker on X; Putin interview 2024"},
    "Greenwald":   {"key": "greenwald",  "tier": "amplifier", "cluster": "G_left",
                    "followers": 2_000_000, "platforms": ["X","YouTube","Substack"],
                    "note": "System Update; civil liberties anti-NATO"},
    "Napolitano":  {"key": "napolitano", "tier": "amplifier", "cluster": "G_right",
                    "followers": 800_000,  "platforms": ["YouTube"],
                    "note": "Judging Freedom; hosts Mearsheimer/Sachs/Macgregor"},
    "MacGregor":   {"key": "macgregor",  "tier": "amplifier", "cluster": "G_right",
                    "followers": 600_000,  "platforms": ["X","YouTube"],
                    "note": "Retired colonel; Carlson regular"},
    "Haiphong":    {"key": "haiphong",   "tier": "amplifier", "cluster": "G_left",
                    "followers": 200_000,  "platforms": ["YouTube"],
                    "note": "G_left; YouTube; RT amplification"},
    "Musk":        {"key": "musk",       "tier": "principal", "cluster": "principal",
                    "followers": 200_000_000, "platforms": ["X"],
                    "note": "Platform owner; GoFundMe supporter"},
    "Sacks":       {"key": "sacks",      "tier": "principal", "cluster": "principal",
                    "followers": 800_000,  "platforms": ["X"],
                    "note": "White House advisor; $5k GoFundMe donor"},
    "Varwick":     {"key": "varwick",    "tier": "amplifier", "cluster": "G_hybrid_DE",
                    "followers": 50_000,   "platforms": ["podcast","YouTube"],
                    "note": "German academic; anti-NATO; Diesen connection"},
    "Wagenknecht": {"key": "wagenknecht","tier": "amplifier", "cluster": "G_hybrid_DE",
                    "followers": 300_000,  "platforms": ["X","YouTube"],
                    "note": "BSW; Querfront; eastern German constituency"},
    "Dugin":       {"key": "dugin",      "tier": "amplifier", "cluster": "G_hybrid_RU",
                    "followers": 200_000,  "platforms": ["Telegram"],
                    "note": "Foundations of Geopolitics; Querfront ideologue"},
    # Podcast platforms hosting known SPBM nodes
    "Judging Freedom":   {"key": "napolitano", "tier": "amplifier", "cluster": "G_right",
                          "followers": 800_000, "platforms": ["YouTube"],
                          "note": "Napolitano's show - regular Mearsheimer/Sachs host"},
    "System Update":     {"key": "greenwald",  "tier": "amplifier", "cluster": "G_left",
                          "followers": 2_000_000, "platforms": ["YouTube","Substack"],
                          "note": "Greenwald's show"},
    "Tucker on X":       {"key": "carlson",    "tier": "amplifier", "cluster": "G_right",
                          "followers": 15_000_000, "platforms": ["X"],
                          "note": "Carlson's X show"},
    "Dialogue Works":    {"key": "diesen",     "tier": "amplifier", "cluster": "G_hybrid_NO",
                          "followers": 100_000,  "platforms": ["YouTube"],
                          "note": "Diesen's YouTube channel"},
    "Greater Eurasia Podcast": {"key": "diesen", "tier": "amplifier", "cluster": "G_hybrid_NO",
                          "followers": 50_000,   "platforms": ["podcast","Apple","Spotify"],
                          "note": "Diesen's daily podcast - separate from Dialogue Works YouTube"},
    # Norwegian A-network (NEW v5)
    "Peace and Justice": {"key": "peace_justice_no", "tier": "amplifier",
                          "cluster": "G_hybrid_NO",
                          "followers": 5_000,    "platforms": ["X","Facebook"],
                          "note": "Norwegian party; Diesen candidate; 'echo of Russian propaganda'"},
}

# Search terms targeting Katchanovski's podcast/interview/joint appearances
APPEARANCE_SEARCHES = [
    # Direct appearance searches - Katchanovski + known host/show
    'Katchanovski Sachs interview podcast',
    'Katchanovski Mearsheimer podcast interview',
    'Katchanovski Diesen interview podcast',
    'Katchanovski Carlson Tucker interview',
    'Katchanovski Greenwald interview podcast',
    'Katchanovski Napolitano "Judging Freedom"',
    'Katchanovski MacGregor interview',
    'Katchanovski Haiphong interview',
    'Katchanovski Wagenknecht BSW',
    'Katchanovski Varwick interview',
    'Katchanovski Dugin interview',
    # Platform-specific appearance searches
    'Katchanovski YouTube interview 2025 2026',
    'Katchanovski podcast episode 2026',
    'Katchanovski Substack 2026',
    'Katchanovski Rumble interview',
    # Joint publication / co-authorship / joint statements
    'Katchanovski Sachs Mearsheimer joint statement',
    'Katchanovski Diesen Varwick article',
    # Panel appearances
    'Katchanovski conference panel Mearsheimer Sachs',
    'Katchanovski APSA ISA panel 2026',
    # Russian state media joint appearances
    'Katchanovski RT interview 2026',
    'Katchanovski Sputnik interview 2026',
    'Katchanovski TASS RIA statement',
    # Norwegian-specific (SPBM paper priority)
    'Katchanovski Diesen Norway interview Norwegian',
    'Katchanovski NRK Aftenposten interview',
    # New/unknown podcast appearances (catch-all)
    '"Katchanovski" interview OR podcast OR "joint appearance" 2026',
]

# Keywords that confirm an appearance (used to classify search hits)
APPEARANCE_CONFIRMED_PATTERNS = [
    r'\binterview\b', r'\bpodcast\b', r'\bepisode\b', r'\bappear\b',
    r'\bguest\b', r'\bpanel\b', r'\bdiscuss\b', r'\bjoin\b',
    r'\bspoke with\b', r'\btalks? with\b', r'\bconversation\b',
    r'\bjoint\b', r'\bco-author\b', r'\bco-sign\b',
    r'\byoutube\.com\b', r'\brumble\.com\b', r'\bsubstack\.com\b',
    r'\bspotify\.com\b', r'\bopen\.spotify\b',
]

# Reach tier classification - used in appearance scoring
REACH_TIERS = [
    (10_000_000, "TIER-1 MEGA",   "⚡⚡⚡"),   # Carlson / Musk level
    (1_000_000,  "TIER-2 HIGH",   "⚡⚡"),
    (100_000,    "TIER-3 MID",    "⚡"),
    (0,          "TIER-4 LOW",    ""),
]


def classify_appearance_reach(followers):
    """Return (tier_label, emoji) based on host followers."""
    if followers is None:
        return "TIER-?", "?"
    for threshold, label, emoji in REACH_TIERS:
        if followers >= threshold:
            return label, emoji
    return "TIER-4 LOW", ""


# ==============================================================================
# NETWORK B APPEARANCE MODULE - COUNTERSPEECH (NEW v4)
# ==============================================================================
#
# Symmetric counterpart to Network A's podcast/appearance module.
# Tracks two event types:
#   Type 1 - PLATFORM COVERAGE: Any of the 7 pro-Ukraine podcasts/outlets
#             covering the Katchanovski book or Umland petition.
#             Equivalent to: Katchanovski appearing on Napolitano's show.
#   Type 2 - SIGNATORY AMPLIFICATION: Key petition signatories publishing
#             op-eds, giving interviews, or posting on X/Bluesky specifically
#             about Katchanovski or the petition.
#             Equivalent to: Mearsheimer co-appearing with Katchanovski.
#
# MCHANGAMA TEST METRIC:
#   Compare Network A cumulative reach (sum of SPBM_NODE followers across
#   all confirmed appearances) with Network B cumulative reach (sum of
#   B_NODES followers/audiences across all confirmed B events).
#   The ratio is the quantitative test of counterspeech effectiveness.
# ------------------------------------------------------------------------------

# Network B platform nodes - pro-Ukraine podcasts and outlets
B_PLATFORM_NODES = {
    # Tier 1 - mass audience
    "Ukraine: The Latest": {
        "key": "telegraph_ukraine", "tier": "platform_T1",
        "audience": 140_000_000,   # cumulative downloads (self-reported)
        "language": "EN",
        "hosts": ["Dominic Nicholls", "Francis Dearnley"],
        "platforms": ["podcast", "YouTube", "Apple", "Spotify"],
        "url": "https://www.telegraph.co.uk/podcasts/ukraine-the-latest/",
        "note": "World's #1 Ukraine podcast; 140M cumulative downloads",
        "x_handle": "@UkraineLatest",
    },
    "Ukrainecast": {
        "key": "bbc_ukrainecast", "tier": "platform_T1",
        "audience": 500_000,       # estimated weekly listeners (BBC does not publish)
        "language": "EN",
        "hosts": ["Victoria Derbyshire", "Vitaly Shevchenko"],
        "platforms": ["podcast", "BBC Sounds", "Apple", "Spotify"],
        "url": "https://www.bbc.co.uk/programmes/p09d2kdq",
        "note": "BBC only Ukraine-dedicated English podcast; 41M Twitter network",
        "x_handle": "@BBCUkrainecast",
    },
    # Tier 2 - specialist/academic audience
    "Sicherheitshalber": {
        "key": "sicherheitshalber", "tier": "platform_T2",
        "audience": 50_000,        # estimated; German-language security audience
        "language": "DE",
        "hosts": ["Carlo Masala", "Ulrike Franke", "Frank Sauer", "Thomas Wiegold"],
        "platforms": ["podcast", "Apple", "Spotify", "YouTube"],
        "url": "https://sicherheitspod.de/",
        "note": "Mother of German security podcasts; 107 eps; Bundeswehr/ECFR/LMU hosts",
        "x_handle": "@sicherheitspod",
    },
    "Ukraine Die Lage Masala": {
        "key": "stern_masala", "tier": "platform_T2",
        "audience": 200_000,       # estimated; stern/Audio Alliance broad German public
        "language": "DE",
        "hosts": ["Carlo Masala", "Stefan Schmitz"],
        "platforms": ["podcast", "Spotify", "Apple"],
        "url": "https://podcasts.apple.com/us/podcast/ukraine-die-lage-mit-carlo-masala/id1613173261",
        "note": "Twice weekly; stern magazine; broad German public audience",
        "x_handle": None,
    },
    "Battleground": {
        "key": "battleground_goalhanger", "tier": "platform_T2",
        "audience": 150_000,       # estimated; Goalhanger strong history audience
        "language": "EN",
        "hosts": ["Patrick Bishop", "Saul David", "Roger Moorhouse"],
        "platforms": ["podcast", "Spotify", "Apple"],
        "url": "https://open.spotify.com/show/0v96h51r7KZU4OH02khvf1",
        "note": "Military historians; strong Ukraine and history framing; Friday Ukraine eps",
        "x_handle": None,
    },
    "Die Lage International Molling": {
        "key": "molling_dgap", "tier": "platform_T2",
        "audience": 30_000,        # estimated; DGAP policy community
        "language": "DE",
        "hosts": ["Christian Molling"],
        "platforms": ["podcast", "Spotify", "Apple"],
        "url": "https://rephonic.com/podcasts/ukraine-die-lage-mit-carlo-masala",
        "note": "DGAP Research Director; co-subscribed with Sicherheitshalber audience",
        "x_handle": None,
    },
    # Norwegian B-platforms (NEW v5)
    "Ukrainapodden": {
        "key": "ukrainapodden_no", "tier": "platform_T2",
        "audience": 35_000,        # estimated; Nettavisen prize-winning podcast
        "language": "NO",
        "hosts": ["Tormod Malvin Saether", "Jorn Sund-Henriksen"],
        "platforms": ["podcast", "Spotify", "Apple"],
        "url": "https://open.spotify.com/show/5uxBBr1NmbOgo6Eyu6iNwq",
        "note": "Prize-winning Norwegian Ukraine war podcast; Nettavisen; daily; "
                "guests incl. Defence Chief Kristoffersen, Heier, researchers; "
                "Jorn Sund-Henriksen also leads Norwegian-Ukrainian friendship assoc.",
        "x_handle": None,
    },
    "Forsvarspodden": {
        "key": "forsvarspodden_no", "tier": "platform_T2",
        "audience": 25_000,        # estimated; official Norwegian Armed Forces podcast
        "language": "NO",
        "hosts": ["Norwegian Armed Forces (Forsvaret)"],
        "platforms": ["podcast", "Spotify", "Apple", "Acast"],
        "url": "https://www.forsvaret.no/aktuelt-og-presse/podkast/forsvarspodden",
        "note": "Official Norwegian Armed Forces podcast; Prix Norge nominated 2023+2024; "
                "weekly; Heier regular guest; institutional B-node; "
                "directly counterweights Peace and Justice/Diesen narrative",
        "x_handle": None,
    },
    "Krig og Sann": {
        "key": "krig_sann_forsvarets_forum", "tier": "platform_T2",
        "audience": 15_000,        # estimated from 65k magazine circulation
        "language": "NO",
        "hosts": ["Forsvarets forum"],
        "platforms": ["podcast"],
        "url": "https://www.forsvaret.no/",
        "note": "Forsvarets forum magazine podcast; 65k print circulation; "
                "security-focused; pro-NATO framing",
        "x_handle": None,
    },
}

# Network B signatory nodes - key petition signatories as amplifiers
B_SIGNATORY_NODES = {
    "Aslund": {
        "key": "aslund", "tier": "signatory_T1",
        "followers": 357_000,      # 324.9k X + 32k Bluesky
        "platforms": ["X", "Bluesky"],
        "affiliation": "Atlantic Council / Stockholm Free World Forum",
        "note": "Highest-reach signatory; daily poster; still on X - critical",
        "x_handle": "@anders_aslund",
    },
    "Snyder": {
        "key": "snyder", "tier": "signatory_T1",
        "followers": 500_000,      # 300k+ Substack + X combined
        "platforms": ["Substack", "X", "Yale podcast"],
        "affiliation": "Yale University",
        "note": "Highest academic prestige; On Tyranny Substack 300k+; "
                "direct analytical equivalent to Mearsheimer on A side",
        "x_handle": "@TimothyDSnyder",
    },
    "Finnin": {
        "key": "finnin", "tier": "signatory_T2",
        "followers": 20_000,       # estimated X followers
        "platforms": ["X"],
        "affiliation": "Cambridge Ukrainian Studies",
        "note": "UK broadsheets; Times Higher Ed; Cambridge imprimatur",
        "x_handle": "@RoryFinnin",
    },
    "Fish": {
        "key": "fish", "tier": "signatory_T2",
        "followers": 10_000,       # estimated
        "platforms": ["X"],
        "affiliation": "UC Berkeley",
        "note": "US academic/policy media; Stanford/Berkeley prestige",
        "x_handle": None,
    },
    "Grabowicz": {
        "key": "grabowicz", "tier": "signatory_T2",
        "followers": 5_000,        # estimated
        "platforms": [],
        "affiliation": "Harvard Ukrainian Research Institute",
        "note": "Harvard imprimatur; US academic audience",
        "x_handle": None,
    },
    "Etkind": {
        "key": "etkind", "tier": "signatory_T2",
        "followers": 10_000,       # estimated
        "platforms": ["X"],
        "affiliation": "CEU Vienna / Helsinki",
        "note": "Russian studies; European academic media",
        "x_handle": None,
    },
    "Gentile": {
        "key": "gentile_oslo", "tier": "signatory_T2",
        "followers": 5_000,        # estimated
        "platforms": ["X"],
        "affiliation": "University of Oslo",
        "note": "ONLY NORWEGIAN SIGNATORY - critical for SPBM Norwegian case",
        "x_handle": None,
    },
    "Umland": {
        "key": "umland", "tier": "signatory_T1",
        "followers": 15_000,       # estimated X followers
        "platforms": ["X"],
        "affiliation": "NaUKMA / Democratic Platform",
        "note": "Petition initiator; large within Ukrainian studies community",
        "x_handle": "@UmlandAndreas",
    },
    "Budjeryn": {
        "key": "budjeryn", "tier": "signatory_T2",
        "followers": 10_000,       # estimated
        "platforms": ["X"],
        "affiliation": "MIT Nuclear Security Center",
        "note": "Arms control media; Bulletin of Atomic Scientists",
        "x_handle": None,
    },
    # Norwegian B-network (NEW v5)
    "Heier": {
        "key": "heier_no", "tier": "signatory_NO",
        "followers": 10_000,
        "platforms": ["podcast"],
        "affiliation": "Forsvarets hogskole / Boston University",
        "note": "Norwegian military professor; SPBM paper source; "
                "Forsvarspodden and Ukrainapodden regular; "
                "32 years Norwegian Army; PhD King's College London",
        "x_handle": None,
    },
    "Mjor": {
        "key": "mjor_no", "tier": "academic_counterspeech_NO",
        "followers": 3_000,
        "platforms": ["academic"],
        "affiliation": "Russian studies scholar (Norway)",
        "note": "Documented Diesen = propaganda in Vagant; "
                "Norwegian-specific Diesen counter-node",
        "x_handle": None,
    },
    "Holtsmark": {
        "key": "holtsmark_no", "tier": "academic_counterspeech_NO",
        "followers": 3_000,
        "platforms": ["academic"],
        "affiliation": "Historian (Norway)",
        "note": "Documented Diesen misrepresents sources; "
                "called for university ethics board investigation; "
                "directly counters Diesen in Norwegian academic discourse",
        "x_handle": None,
    },
    "Berger": {
        "key": "berger_no", "tier": "OSINT_media_critic_NO",
        "followers": 8_000,
        "platforms": ["X", "LinkedIn", "Facebook"],
        "affiliation": "Independent Norwegian analyst / Norwegian-Ukrainian friendship assoc.",
        "note": "Unique function: documents NRK whitewashing Russian narratives; "
                "forced NRK corrections: Diesen 2022, Avdiivka 2024, "
                "cluster munitions 2023, referendum interviews 2022; "
                "directly relevant to SPBM κi suppression mechanism; "
                "κi suppression through legitimate media documented",
        "x_handle": "@BjornJBerger",
    },
    # Counter-OSINT nodes as B-network signatories (NEW v5)
    "Bellingcat": {
        "key": "bellingcat", "tier": "counter_OSINT",
        "followers": 500_000,
        "platforms": ["web", "X", "YouTube"],
        "affiliation": "Bellingcat (Netherlands)",
        "note": "Gold standard OSINT; banned by Russia 2022; "
                "has NOT covered Katchanovski yet - monitoring for first investigation",
        "x_handle": "@bellingcat",
    },
    "DFRLab": {
        "key": "dfrlab", "tier": "counter_OSINT",
        "followers": 200_000,
        "platforms": ["web", "X"],
        "affiliation": "Atlantic Council Digital Forensic Research Lab",
        "note": "Documented Doppelganger + Pravda Network; "
                "most technically equipped to map Katchanovski amplification network",
        "x_handle": "@DFRLab",
    },
    "EUvsDisinfo": {
        "key": "euvsdisinfo", "tier": "counter_OSINT",
        "followers": 120_000,
        "platforms": ["web", "X"],
        "affiliation": "EU External Action Service",
        "note": "EU authority on FIMI; Democracy Shield instrument; "
                "tracks Russian information manipulation systematically",
        "x_handle": "@EUvsDisinfo",
    },
    "Correctiv": {
        "key": "correctiv_de", "tier": "fact_checker",
        "followers": 150_000,
        "platforms": ["web", "X"],
        "affiliation": "CORRECTIV (Germany)",
        "note": "HIGHEST PRIORITY fact-checker: documented Doppelganger, "
                "100 fake election sites, AfD/far-right meetings; "
                "banned in Russia 2025; BSW/Katchanovski = natural Correctiv story",
        "x_handle": "@correctiv_org",
    },
    "Faktisk": {
        "key": "faktisk_no", "tier": "fact_checker",
        "followers": 40_000,
        "platforms": ["web", "X"],
        "affiliation": "Faktisk.no (Norway) - NRK/VG/Dagbladet/TV2 collaboration",
        "note": "Structural tension: NRK is Faktisk co-owner AND platform "
                "criticised for spreading Russian narratives; "
                "50% of Norwegians know Faktisk",
        "x_handle": "@faktisk",
    },
}

# Search terms for Network B Type 1 - platform coverage of book/petition
CS_PLATFORM_SEARCHES = [
    # Direct coverage searches - petition/book + known platform
    'Katchanovski "Ukraine The Latest" Telegraph',
    'Katchanovski Ukrainecast BBC',
    'Katchanovski Sicherheitshalber Masala podcast',
    'Katchanovski stern Masala podcast',
    'Katchanovski Battleground podcast',
    'Katchanovski "Die Lage" Molling',
    # Broader platform coverage
    'Katchanovski book review podcast Ukraine 2026',
    'Umland petition podcast coverage Ukraine 2026',
    '"collective warning" Katchanovski podcast',
    # Key host name searches
    'Katchanovski Masala interview',
    'Katchanovski Nicholls Telegraph interview',
    'Katchanovski Derbyshire BBC interview',
    # Publisher response coverage
    'Palgrave Katchanovski podcast discussion',
    'Springer Katchanovski academic podcast',
    # Norwegian platform searches (NEW v5)
    'Katchanovski Ukrainapodden Nettavisen podcast',
    'Katchanovski Forsvarspodden Norway',
    'Katchanovski Saether Sund-Henriksen Norway',
    'Katchanovski "Krig og Sann" Norway defense',
    '"Katchanovski" Ukraine Norway podkast',
    # Counter-OSINT platform searches (NEW v5)
    'Katchanovski Bellingcat investigation',
    'Katchanovski DFRLab Atlantic Council report',
    'Katchanovski EUvsDisinfo FIMI report',
    'Katchanovski Correctiv investigation Germany',
    'Katchanovski Faktisk fact-check Norway',
    'Katchanovski "influence operation" investigation 2026',
]

# Search terms for Network B Type 2 - signatory amplification events
CS_SIGNATORY_SEARCHES = [
    # High-reach signatory X/Bluesky posts
    'Aslund Katchanovski X post',
    'Aslund Katchanovski Twitter warning',
    '"Timothy Snyder" Katchanovski',
    'Snyder Katchanovski Substack',
    'Finnin Katchanovski Cambridge',
    'Grabowicz Katchanovski Harvard',
    'Gentile Katchanovski Oslo Norway',
    'Etkind Katchanovski Vienna Helsinki',
    'Umland Katchanovski interview media',
    # Outlet-specific signatory coverage
    'Aslund Katchanovski Atlantic Council',
    'Aslund Katchanovski Financial Times',
    'Aslund Katchanovski Politico',
    'Snyder Katchanovski New Yorker Atlantic',
    # Norwegian media (high SPBM priority)
    'Katchanovski Gentile Aftenposten NRK',
    'Katchanovski Oslo University Norway',
    # Academic journal coverage
    'Katchanovski review journal Ukrainian Studies',
    'Katchanovski "Times Higher Education"',
    'Katchanovski Slavic Review journal',
    # Norwegian B-signatory amplification (NEW v5)
    'Katchanovski Heier Norway Forsvarets',
    'Katchanovski Holtsmark historian Norway',
    'Katchanovski Mjor Vagant Norway',
    'Katchanovski Berger NRK whitewash Norway media',
    'Berger NRK Russia disinformation Norway',
    'Holtsmark Diesen Katchanovski Norway',
    'Katchanovski Norway "russisk propaganda"',
    # Counter-OSINT signatory events (NEW v5)
    'Bellingcat Katchanovski Musk amplification investigation',
    'DFRLab Katchanovski Diesen Norwegian influence',
    'EUvsDisinfo Katchanovski academic publishing',
    'Correctiv Katchanovski BSW AfD Wagenknecht',
    'Faktisk Katchanovski Diesen NRK Norway',
    # Catch-all
    '"Umland" "Katchanovski" interview OR podcast OR article 2026',
    '"Berger" "NRK" "Katchanovski" OR "Diesen" 2026',
]

# Combined B-network node lookup for matching in search results
B_ALL_NODES = {}
B_ALL_NODES.update({k: {**v, "node_type": "platform"} for k, v in B_PLATFORM_NODES.items()})
B_ALL_NODES.update({k: {**v, "node_type": "signatory"} for k, v in B_SIGNATORY_NODES.items()})


def detect_cs_appearances(search_results):
    """
    Scan search results for Network B counterspeech appearance events.
    Uses identical logic to detect_appearances() for methodological symmetry.
    Returns list of cs_appearance dicts with same schema as Network A appearances.
    """
    appearances = []
    seen_urls = set()

    for item in search_results:
        title = item.get("title", "")
        url   = item.get("url", "")
        if not title or item.get("type") == "search_error":
            continue
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        confirmed = any(
            re.search(p, title, re.IGNORECASE)
            for p in APPEARANCE_CONFIRMED_PATTERNS
        )

        matched_node_name = None
        node_meta = {}
        for node_name, meta in B_ALL_NODES.items():
            if node_name.lower() in title.lower():
                matched_node_name = node_name
                node_meta = meta
                break

        if not confirmed and not matched_node_name:
            continue

        # Resolve audience/follower figure - platforms use 'audience', signatories 'followers'
        audience = node_meta.get("audience") or node_meta.get("followers")
        reach_tier, reach_emoji = classify_appearance_reach(audience)

        # High-priority: T1 platforms (140M downloads) or T1 signatories (Aslund, Snyder)
        is_hp = (
            node_meta.get("tier") in ("platform_T1", "signatory_T1")
            or (matched_node_name in ("Ukraine: The Latest", "Ukrainecast",
                                       "Aslund", "Snyder"))
        )

        appearances.append({
            "network":          "B",
            "event_type":       "platform_coverage" if node_meta.get("node_type") == "platform"
                                else "signatory_amplification",
            "title":            title,
            "url":              url,
            "pubDate":          item.get("pubDate", ""),
            "query":            item.get("query", ""),
            "matched_node":     matched_node_name,
            "node_key":         node_meta.get("key"),
            "node_tier":        node_meta.get("tier"),
            "node_type":        node_meta.get("node_type"),
            "node_audience":    audience,
            "node_language":    node_meta.get("language"),
            "node_platforms":   node_meta.get("platforms", []),
            "reach_tier":       reach_tier,
            "reach_emoji":      reach_emoji,
            "confirmed":        confirmed,
            "is_hp":            is_hp,
            "timestamp":        datetime.datetime.now().isoformat(),
        })

    appearances.sort(key=lambda x: x.get("node_audience") or 0, reverse=True)
    return appearances


def run_cs_appearance_module():
    """
    Run the full Network B counterspeech appearance search cycle.
    Symmetric counterpart to run_appearance_module() for Network A.
    Returns (all_appearances, new_appearances).
    """
    print("\n-- Network B: counterspeech appearances --")

    seen_urls = set()
    if CS_APPEARANCES.exists():
        for line in CS_APPEARANCES.read_text().splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    if rec.get("url"):
                        seen_urls.add(rec["url"])
                except Exception:
                    pass

    cs_news = []
    for term in CS_PLATFORM_SEARCHES + CS_SIGNATORY_SEARCHES:
        items = news_search(term, max_results=5)
        for it in items:
            it.update({"type": "news", "network": "B_appearances", "query": term})
            cs_news.append(it)
        time.sleep(2.0)

    all_appearances = detect_cs_appearances(cs_news)
    new_appearances = [a for a in all_appearances if a.get("url") not in seen_urls]

    if new_appearances:
        print(f"  📢  {len(new_appearances)} new counterspeech event(s) "
              f"({len(all_appearances)} total):")
        for ap in new_appearances[:10]:
            node    = ap.get("matched_node", "?")
            emoji   = ap.get("reach_emoji", "")
            tier    = ap.get("reach_tier", "")
            etype   = "PLATFORM" if ap["event_type"] == "platform_coverage" else "signatory"
            conf    = "✓" if ap["confirmed"] else "~"
            hp_flag = " ⚠️ HP" if ap["is_hp"] else ""
            aud     = ap.get("node_audience", 0) or 0
            a_str   = f"{aud/1e6:.1f}M" if aud >= 1e6 else f"{aud/1e3:.0f}k"
            print(f"    {emoji} [{tier}][{etype}]{hp_flag} {conf} - {node} ({a_str})")
            print(f"       {ap['title'][:85]}")
    else:
        print(f"  ✓ No new counterspeech events this run "
              f"({len(all_appearances)} total, all previously seen)")

    if new_appearances:
        with open(CS_APPEARANCES, "a") as f:
            for ap in new_appearances:
                f.write(json.dumps(ap) + "\n")
        print(f"  Saved -> {CS_APPEARANCES.name}")

    return all_appearances, new_appearances


def print_cs_appearance_log():
    """Print the full Network B counterspeech appearance log with analysis."""
    if not CS_APPEARANCES.exists():
        print("No counterspeech appearance log yet. Run monitor first.")
        return

    records = []
    for line in CS_APPEARANCES.read_text().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except Exception:
                pass

    if not records:
        print("No counterspeech events logged yet.")
        return

    platform_recs   = [r for r in records if r.get("event_type") == "platform_coverage"]
    signatory_recs  = [r for r in records if r.get("event_type") == "signatory_amplification"]

    print("\n" + "="*75)
    print(f"NETWORK B COUNTERSPEECH APPEARANCE LOG  ({len(records)} entries)")
    print("="*75)

    # Platform coverage
    print(f"\n  PLATFORM COVERAGE EVENTS ({len(platform_recs)})")
    print(f"  {'Platform':<30} {'Lang':>4} {'Events':>6} {'Audience':>12}  Tier")
    print("  " + "-"*65)
    by_platform = defaultdict(list)
    for r in platform_recs:
        by_platform[r.get("matched_node") or "?"].append(r)
    for pname, recs in sorted(by_platform.items(),
                               key=lambda x: B_PLATFORM_NODES.get(x[0], {}).get("audience", 0),
                               reverse=True):
        meta    = B_PLATFORM_NODES.get(pname, {})
        aud     = meta.get("audience", 0) or 0
        lang    = meta.get("language", "?")
        a_str   = f"{aud/1e6:.0f}M" if aud >= 1e6 else f"{aud/1e3:.0f}k"
        _, emoji = classify_appearance_reach(aud)
        print(f"  {pname:<30} {lang:>4} {len(recs):>6} {a_str:>12}  {emoji}")

    # Signatory amplification
    print(f"\n  SIGNATORY AMPLIFICATION EVENTS ({len(signatory_recs)})")
    print(f"  {'Signatory':<22} {'Platform':<10} {'Events':>6} {'Followers':>12}  Note")
    print("  " + "-"*65)
    by_sig = defaultdict(list)
    for r in signatory_recs:
        by_sig[r.get("matched_node") or "?"].append(r)
    for sname, recs in sorted(by_sig.items(),
                               key=lambda x: B_SIGNATORY_NODES.get(x[0], {}).get("followers", 0),
                               reverse=True):
        meta = B_SIGNATORY_NODES.get(sname, {})
        fol  = meta.get("followers", 0) or 0
        plat = "/".join(meta.get("platforms", [])[:2])
        f_str = f"{fol/1e6:.1f}M" if fol >= 1e6 else f"{fol/1e3:.0f}k" if fol >= 1000 else "?"
        note = meta.get("note", "")[:35]
        print(f"  {sname:<22} {plat:<10} {len(recs):>6} {f_str:>12}  {note}")

    # Cumulative reach summary
    unique_platform_nodes = {r.get("matched_node") for r in platform_recs if r.get("matched_node")}
    unique_sig_nodes      = {r.get("matched_node") for r in signatory_recs if r.get("matched_node")}
    total_platform_reach  = sum(B_PLATFORM_NODES.get(n, {}).get("audience", 0) or 0
                                 for n in unique_platform_nodes)
    total_sig_reach       = sum(B_SIGNATORY_NODES.get(n, {}).get("followers", 0) or 0
                                 for n in unique_sig_nodes)
    total_b_reach         = total_platform_reach + total_sig_reach

    print(f"\n  NETWORK B REACH SUMMARY")
    print(f"  Platform coverage reach (unique platforms × audience): "
          f"{total_platform_reach/1e6:.1f}M")
    print(f"  Signatory amplification reach (unique signatories × followers): "
          f"{total_sig_reach/1e3:.0f}k")
    print(f"  Combined B network reach (upper bound): {total_b_reach/1e6:.1f}M")

    # Timeline
    print(f"\n  TIMELINE (most recent first):")
    sorted_recs = sorted(records,
                         key=lambda x: x.get("pubDate") or x.get("timestamp") or "",
                         reverse=True)
    for r in sorted_recs[:20]:
        ts    = (r.get("pubDate") or r.get("timestamp") or "?")[:10]
        node  = r.get("matched_node") or "?"
        emoji = r.get("reach_emoji", "")
        conf  = "✓" if r.get("confirmed") else "~"
        etype = "P" if r.get("event_type") == "platform_coverage" else "S"
        print(f"    {ts}  {conf}{etype} {emoji} {node:<25}  {r['title'][:50]}")


# ==============================================================================
# CROSS-POLLINATION / OVERLAP MODULE  (NEW v4)
# ==============================================================================
#
# Three overlap dimensions tracked:
#   1. NODE OVERLAP      - individuals or outlets appearing in BOTH networks
#                          (e.g. a B-network signatory who also appears in
#                          A-network searches, or vice versa)
#   2. PLATFORM OVERLAP  - shared platforms used by both networks
#                          (both use YouTube / X / Spotify)
#   3. AUDIENCE PROXIES  - indirect signals of audience overlap:
#                          cross-network citations, shared outlet coverage,
#                          mentions of one network by the other
# ------------------------------------------------------------------------------

# Searches specifically designed to surface cross-pollination signals
OVERLAP_SEARCHES = [
    # A-network nodes referencing B-network content (inversion / weaponisation)
    'Carlson Greenwald Katchanovski petition censorship cancel',
    'Diesen Katchanovski Umland petition',
    'Mearsheimer Katchanovski petition academic freedom',
    'Sachs Katchanovski scholars warning',
    'Musk Katchanovski censorship petition',
    # B-network nodes engaging with A-network content
    'Aslund Musk Katchanovski X amplification',
    'Snyder Tucker Carlson Katchanovski',
    'Sicherheitshalber Katchanovski Diesen Varwick',
    'Telegraph Ukraine Katchanovski Musk Sacks',
    'BBC Katchanovski Musk Sacks amplification',
    # Shared outlet coverage (outlets covering BOTH networks)
    'Financial Times Katchanovski Umland petition',
    'Guardian Katchanovski petition Umland',
    'Politico Katchanovski book petition',
    'New York Times Katchanovski Umland',
    'Foreign Affairs Katchanovski book review',
    # Academic cross-references (either side citing the other)
    'Katchanovski Mearsheimer Umland academic',
    'Katchanovski Sachs Grabowicz Harvard',
    # Platform overlap signals (Bluesky mentions of A-network; X mentions of B)
    'Katchanovski Bluesky Aslund Snyder',
    'Katchanovski X Twitter Umland petition reach',
    # The Marples / "cancel" inversion signal
    'Katchanovski Marples petition unfair',
    'Katchanovski academic freedom cancel culture',
    # Norwegian overlap signals (NEW v5)
    'Diesen Katchanovski Berger NRK Norway',
    'Katchanovski Diesen Heier Norway',
    'Katchanovski Peace Justice Holtsmark Norway',
    'Katchanovski Norway Ukrainapodden Diesen',
    'Diesen Peace Justice "Russian propaganda" Norway',
    '"Fred og Rettferdighet" NRK Katchanovski',
    'Katchanovski Mjor Holtsmark Diesen academic Norway',
    # Counter-OSINT / fact-checker overlap signals (NEW v5)
    'Katchanovski Bellingcat DFRLab influence operation',
    'Correctiv Katchanovski BSW AfD disinformation Germany',
    'Faktisk Katchanovski NRK Norway whitewash',
    'DFRLab Katchanovski Musk Sacks network',
    'EUvsDisinfo Katchanovski academic publishing influence',
    # Russian OSINT-mimic amplifying Katchanovski (NEW v5)
    'Katchanovski Rybar Telegram Russia amplify',
    'Katchanovski WarFakes Russia propaganda book',
    'Katchanovski "Pravda network" disinformation academic',
]

# Node name sets for overlap detection
A_NODE_NAMES = set(SPBM_NODES.keys()) | {
    "Katchanovski", "Musk", "Sacks", "Tucker", "Carlson",
    "Napolitano", "Judging Freedom", "Haiphong", "MacGregor",
    # Norwegian A-nodes (NEW v5)
    "Peace and Justice", "Fred og Rettferdighet", "Nistad",
    # Russian OSINT-mimic (NEW v5)
    "Rybar", "WarFakes", "War on Fakes", "Readovka", "Pravda network",
}
B_NODE_NAMES = set(B_ALL_NODES.keys()) | {
    "Umland", "Aslund", "Snyder", "Finnin", "Grabowicz",
    "Gentile", "Sicherheitshalber", "Masala", "Ukrainecast",
    "BBC", "Telegraph",
    # Norwegian B-nodes (NEW v5)
    "Heier", "Berger", "Holtsmark", "Mjor", "Mjor",
    "Ukrainapodden", "Forsvarspodden",
    # Counter-OSINT (NEW v5)
    "Bellingcat", "DFRLab", "EUvsDisinfo", "Correctiv", "Faktisk",
    "CIR", "OSINT for Ukraine",
}

# Shared outlets (present in both network's information environment)
SHARED_OUTLETS = [
    "Financial Times", "Guardian", "New York Times", "Politico",
    "Foreign Affairs", "Atlantic", "New Yorker", "Washington Post",
    "BBC", "Reuters", "AP",
    # Broadcast TV - highest-quality cross-pollination indicators (NEW v6)
    # TV debate formats genuinely mix A and B network audiences
    "NRK", "NRK Debatten", "NRK Urix", "Dagsrevyen", "TV 2",
    "Tagesschau", "ARD", "ZDF", "Markus Lanz", "heute-journal",
    "Maybrit Illner", "Hart aber fair", "Phoenix",
]


def detect_overlap(search_results):
    """
    Scan results for cross-pollination signals across three dimensions:
      1. node_overlap    - both an A and B node appear in the same item
      2. inversion       - A-network weaponising B-network counterspeech
      3. shared_outlet   - a major outlet covering both sides
    Returns list of overlap dicts.
    """
    overlaps = []
    seen_urls = set()

    for item in search_results:
        title = item.get("title", "")
        url   = item.get("url", "")
        if not title or item.get("type") == "search_error":
            continue
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        title_lower = title.lower()

        # Find which A-nodes are mentioned
        a_hits = [n for n in A_NODE_NAMES if n.lower() in title_lower]
        # Find which B-nodes are mentioned
        b_hits = [n for n in B_NODE_NAMES if n.lower() in title_lower]
        # Find which shared outlets are mentioned
        outlet_hits = [o for o in SHARED_OUTLETS if o.lower() in title_lower]
        # Find which TV channels are mentioned (NEW v6)
        tv_hits = [t for t in TV_NODE_NAMES if t.lower() in title_lower]

        # Inversion patterns - A-network framing B-network as censorship
        inversion_patterns = [
            r'\b(censor|cancel|silence|suppress|academic freedom)\b',
            r'\b(unfair|attack|witch.?hunt|McCarthyism)\b',
            r'\bpetition.*censor\b', r'\bcensor.*petition\b',
        ]
        inversion_hit = any(
            re.search(p, title, re.IGNORECASE) for p in inversion_patterns
        )

        # TV appearance: Katchanovski/Diesen/A-node on major public TV (NEW v6)
        # These are highest-quality cross-pollination events
        tv_appearance = bool(tv_hits) and (
            "Katchanovski" in title or "Diesen" in title or
            any(n.lower() in title_lower for n in ["Varwick", "Wagenknecht", "BSW", "AfD"])
        )

        overlap_type = None
        if tv_appearance and tv_hits:
            overlap_type = "tv_appearance"       # highest priority - genuine shared audience
        elif a_hits and b_hits:
            overlap_type = "node_overlap"
        elif inversion_hit and (a_hits or b_hits):
            overlap_type = "inversion_signal"
        elif outlet_hits and ("Katchanovski" in title or "Umland" in title):
            overlap_type = "shared_outlet"

        if not overlap_type:
            continue

        overlaps.append({
            "overlap_type":   overlap_type,
            "title":          title,
            "url":            url,
            "pubDate":        item.get("pubDate", ""),
            "query":          item.get("query", ""),
            "a_nodes_hit":    a_hits,
            "b_nodes_hit":    b_hits,
            "outlets_hit":    outlet_hits,
            "tv_hits":        tv_hits,          # NEW v6
            "inversion":      inversion_hit,
            "is_hp":          overlap_type in ("node_overlap", "inversion_signal",
                                               "tv_appearance"),  # tv_appearance always HP
            "timestamp":      datetime.datetime.now().isoformat(),
        })

    return overlaps


def run_overlap_module():
    """Run the cross-pollination detection cycle."""
    print("\n-- Cross-pollination / overlap detection --")

    seen_urls = set()
    if OVERLAP_LOG.exists():
        for line in OVERLAP_LOG.read_text().splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    if rec.get("url"):
                        seen_urls.add(rec["url"])
                except Exception:
                    pass

    ov_news = []
    for term in OVERLAP_SEARCHES + TV_SEARCHES:   # TV_SEARCHES added v6
        items = news_search(term, max_results=4)
        for it in items:
            it.update({"type": "news", "network": "overlap", "query": term})
            ov_news.append(it)
        time.sleep(2.0)

    all_overlaps = detect_overlap(ov_news)
    new_overlaps = [o for o in all_overlaps if o.get("url") not in seen_urls]

    if new_overlaps:
        inv_count  = sum(1 for o in new_overlaps if o["overlap_type"] == "inversion_signal")
        node_count = sum(1 for o in new_overlaps if o["overlap_type"] == "node_overlap")
        out_count  = sum(1 for o in new_overlaps if o["overlap_type"] == "shared_outlet")
        tv_count   = sum(1 for o in new_overlaps if o["overlap_type"] == "tv_appearance")

        print(f"  🔗  {len(new_overlaps)} new overlap signal(s): "
              f"{node_count} node-overlap, {inv_count} inversion, "
              f"{out_count} shared-outlet, {tv_count} TV-appearance")
        for ov in new_overlaps[:8]:
            otype  = ov["overlap_type"].upper()
            a_str  = ", ".join(ov["a_nodes_hit"][:2])
            b_str  = ", ".join(ov["b_nodes_hit"][:2])
            tv_str = ", ".join(ov.get("tv_hits", [])[:2])
            hp_tag = " ⚠️ HP" if ov["is_hp"] else ""
            if ov["overlap_type"] == "tv_appearance":
                print(f"    📺 [{otype}]{hp_tag}  TV:[{tv_str}]  {ov['title'][:65]}")
            else:
                print(f"    [{otype}]{hp_tag}  A:[{a_str}] ↔ B:[{b_str}]")
                print(f"       {ov['title'][:80]}")
        with open(OVERLAP_LOG, "a") as f:
            for ov in new_overlaps:
                f.write(json.dumps(ov) + "\n")
        print(f"  Saved -> {OVERLAP_LOG.name}")
    else:
        print(f"  ✓ No new overlap signals ({len(all_overlaps)} total, all previously seen)")

    return all_overlaps, new_overlaps


def print_overlap_report():
    """Print full cross-pollination analysis."""
    if not OVERLAP_LOG.exists():
        print("No overlap log yet. Run monitor first.")
        return

    records = []
    for line in OVERLAP_LOG.read_text().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except Exception:
                pass

    if not records:
        print("No overlap signals logged yet.")
        return

    by_type = defaultdict(list)
    for r in records:
        by_type[r["overlap_type"]].append(r)

    print("\n" + "="*75)
    print(f"CROSS-POLLINATION REPORT  ({len(records)} signals)")
    print("="*75)

    print(f"\n  SIGNAL COUNTS BY TYPE")
    for otype, recs in sorted(by_type.items(), key=lambda x: -len(x[1])):
        flag = " 📺 HIGHEST PRIORITY - genuine shared audience" if otype == "tv_appearance" else ""
        print(f"  {otype:<25} {len(recs):>4} signals{flag}")

    # TV appearances - genuine audience overlap (NEW v6)
    tv_recs = by_type.get("tv_appearance", [])
    if tv_recs:
        print(f"\n  📺 TV APPEARANCE EVENTS - GENUINE SHARED AUDIENCE ({len(tv_recs)})")
        print(f"  (A and B network audiences watch the same programme simultaneously)")
        print(f"  {'Date':<12} {'TV Channel':<20} Title")
        print("  " + "-"*70)
        for r in sorted(tv_recs, key=lambda x: x.get("pubDate",""), reverse=True)[:12]:
            ts  = (r.get("pubDate") or r.get("timestamp","?"))[:10]
            tvs = ", ".join(r.get("tv_hits", ["?"])[:2])
            print(f"  {ts:<12} {tvs:<20} {r['title'][:42]}")
        print(f"\n  Audience figures: NRK ~1.8M daily | ARD Tagesschau ~9.6M | ZDF Markus Lanz ~4M")
        print(f"  TV appearances are the highest-quality cross-pollination signal available.")

    node_overlaps = by_type.get("node_overlap", [])
    if node_overlaps:
        print(f"\n  NODE OVERLAP EVENTS - same item mentions A and B nodes")
        print(f"  {'Title':<55}  A-nodes    B-nodes")
        print("  " + "-"*75)
        for r in node_overlaps[:15]:
            a_str = "+".join(r["a_nodes_hit"][:2])
            b_str = "+".join(r["b_nodes_hit"][:2])
            print(f"  {r['title'][:55]:<55}  {a_str:<10} {b_str}")

    inversions = by_type.get("inversion_signal", [])
    if inversions:
        print(f"\n  ⚠️  INVERSION SIGNALS - A-network weaponising B-network counterspeech")
        print(f"  (These are the highest-risk events: B's democratic legitimacy becomes")
        print(f"  A's narrative of censorship - Streisand effect risk)")
        for r in inversions[:10]:
            ts = r.get("pubDate", r.get("timestamp", "?"))[:10]
            a_str = ", ".join(r["a_nodes_hit"][:2])
            print(f"    {ts}  [{a_str}]  {r['title'][:70]}")

    shared = by_type.get("shared_outlet", [])
    if shared:
        print(f"\n  SHARED OUTLET COVERAGE - same outlet covers both networks")
        print(f"  (These are audience-overlap proxies: same readers may see both)")
        outlet_counts = defaultdict(int)
        for r in shared:
            for o in r.get("outlets_hit", []):
                outlet_counts[o] += 1
        for outlet, count in sorted(outlet_counts.items(), key=lambda x: -x[1]):
            print(f"    {outlet:<25} {count} items")

    # Platform overlap analysis (static, from node definitions)
    print(f"\n  PLATFORM OVERLAP ANALYSIS (structural)")
    a_platforms = set()
    for meta in SPBM_NODES.values():
        a_platforms.update(meta.get("platforms", []))
    b_platforms = set()
    for meta in B_PLATFORM_NODES.values():
        b_platforms.update(meta.get("platforms", []))
    for meta in B_SIGNATORY_NODES.values():
        b_platforms.update(meta.get("platforms", []))

    shared_platforms = a_platforms & b_platforms
    a_only = a_platforms - b_platforms
    b_only = b_platforms - a_platforms

    print(f"  Shared platforms (potential audience overlap): "
          f"{', '.join(sorted(shared_platforms))}")
    print(f"  A-network only: {', '.join(sorted(a_only))}")
    print(f"  B-network only: {', '.join(sorted(b_only))}")
    print(f"\n  KEY FINDING: X is present in both networks but with radically")
    print(f"  different scale (A: 6.6M upper-bound followers; B: Aslund 325k).")
    print(f"  YouTube is present in both. Bluesky, Substack, BBC Sounds, Spotify")
    print(f"  are B-dominant - they reach the already-converted, not A's audience.")

    print(f"\n  AUDIENCE OVERLAP ASSESSMENT (qualitative)")
    print(f"  Direct measurement: NOT POSSIBLE without platform analytics access.")
    print(f"  Proxy evidence from this monitor:")
    print(f"    - Shared outlet items (same readers may see both): {len(shared)}")
    print(f"    - Node overlap events (same discourse mentions both): {len(node_overlaps)}")
    print(f"    - Inversion events (A weaponises B): {len(inversions)}")
    print(f"  Analytical prior: LOW audience overlap predicted by SPBM model.")
    print(f"  Platform segregation (X vs Bluesky; populist podcasts vs security")
    print(f"  podcasts) suggests the two networks operate in largely separate")
    print(f"  information spaces - which is precisely the asymmetry the SPBM")


def detect_appearances(search_results):
    """
    Scan news search results for confirmed podcast/interview/joint appearances.

    Returns a list of appearance dicts, each containing:
      - title, url, pubDate, query
      - matched_node: which SPBM node is involved (if identifiable)
      - node_metadata: tier, cluster, followers
      - reach_tier, reach_emoji
      - confirmed: True if appearance pattern matched (vs. mere mention)
      - is_hp: True if involves a Tier-1/2 node or is a new appearance
      - timestamp
    """
    appearances = []
    seen_urls = set()

    for item in search_results:
        title = item.get("title", "")
        url   = item.get("url", "")
        if not title or item.get("type") == "search_error":
            continue
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Check for appearance-confirmation patterns
        confirmed = any(
            re.search(p, title, re.IGNORECASE)
            for p in APPEARANCE_CONFIRMED_PATTERNS
        )

        # Identify which SPBM node is involved
        matched_node_name = None
        node_meta = {}
        for node_name, meta in SPBM_NODES.items():
            if node_name.lower() in title.lower():
                matched_node_name = node_name
                node_meta = meta
                break

        # Only record if we have either a confirmed appearance pattern
        # OR a known SPBM node involved
        if not confirmed and not matched_node_name:
            continue

        followers = node_meta.get("followers")
        reach_tier, reach_emoji = classify_appearance_reach(followers)

        is_hp = (
            reach_tier in ("TIER-1 MEGA", "TIER-2 HIGH")
            or (matched_node_name in ("Carlson", "Musk", "Greenwald", "Mearsheimer",
                                      "Sachs", "Tucker on X", "System Update"))
        )

        appearances.append({
            "title":            title,
            "url":              url,
            "pubDate":          item.get("pubDate", ""),
            "query":            item.get("query", ""),
            "matched_node":     matched_node_name,
            "node_key":         node_meta.get("key"),
            "node_tier":        node_meta.get("tier"),
            "node_cluster":     node_meta.get("cluster"),
            "node_followers":   followers,
            "node_platforms":   node_meta.get("platforms", []),
            "reach_tier":       reach_tier,
            "reach_emoji":      reach_emoji,
            "confirmed":        confirmed,
            "is_hp":            is_hp,
            "timestamp":        datetime.datetime.now().isoformat(),
        })

    # Sort by follower count descending (highest-reach first)
    appearances.sort(key=lambda x: x.get("node_followers") or 0, reverse=True)
    return appearances


def run_appearance_module():
    """
    Run the full podcast/joint-appearance search cycle.
    Returns (appearances_found, new_appearances) where new_appearances
    are ones not seen in any previous run.
    """
    print("\n-- Podcast & joint-appearance module --")

    # Load previously seen appearance URLs
    seen_urls = set()
    if APPEARANCES.exists():
        for line in APPEARANCES.read_text().splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    if rec.get("url"):
                        seen_urls.add(rec["url"])
                except Exception:
                    pass

    # Run searches
    ap_news = []
    for term in APPEARANCE_SEARCHES:
        items = news_search(term, max_results=5)
        for it in items:
            it.update({"type": "news", "network": "appearances", "query": term})
            ap_news.append(it)
        time.sleep(2.0)

    # Detect appearances from results
    all_appearances = detect_appearances(ap_news)

    # Separate new vs previously seen
    new_appearances = [a for a in all_appearances if a.get("url") not in seen_urls]

    # Print summary
    if new_appearances:
        print(f"  🎙  {len(new_appearances)} new appearance(s) detected "
              f"({len(all_appearances)} total this run):")
        for ap in new_appearances[:10]:
            node   = ap.get("matched_node", "unknown host")
            emoji  = ap.get("reach_emoji", "")
            tier   = ap.get("reach_tier", "")
            conf   = "✓ confirmed" if ap["confirmed"] else "~ possible"
            hp_flag = " ⚠️ HIGH-REACH" if ap["is_hp"] else ""
            followers = ap.get("node_followers")
            f_str = f"{followers/1e6:.1f}M" if followers and followers >= 1e6 \
                    else (f"{followers/1e3:.0f}k" if followers else "?")
            print(f"    {emoji} [{tier}]{hp_flag} - {node} ({f_str}) - {conf}")
            print(f"       {ap['title'][:85]}")
    else:
        print(f"  ✓ No new appearances this run "
              f"({len(all_appearances)} total results, all previously seen)")

    # Append new appearances to log
    if new_appearances:
        with open(APPEARANCES, "a") as f:
            for ap in new_appearances:
                f.write(json.dumps(ap) + "\n")
        print(f"  Saved -> {APPEARANCES.name}")

    return all_appearances, new_appearances


def print_appearance_log():
    """Print the full co-appearance log with network analysis."""
    if not APPEARANCES.exists():
        print("No appearance log yet. Run monitor first.")
        return

    records = []
    for line in APPEARANCES.read_text().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except Exception:
                pass

    if not records:
        print("No appearances logged yet.")
        return

    print("\n" + "="*75)
    print(f"KATCHANOVSKI CO-APPEARANCE LOG  ({len(records)} entries)")
    print("="*75)

    # Group by matched node
    by_node = defaultdict(list)
    for rec in records:
        node = rec.get("matched_node") or "unknown"
        by_node[node].append(rec)

    # Print per-node summary
    print(f"\n{'NODE':<22} {'CLUSTER':<14} {'APPEARANCES':>11} {'REACH':>12}  TIER")
    print("-"*75)
    node_totals = []
    for node_name, recs in by_node.items():
        meta = SPBM_NODES.get(node_name, {})
        cluster   = meta.get("cluster", "?")
        followers = meta.get("followers", 0) or 0
        f_str = f"{followers/1e6:.1f}M" if followers >= 1e6 \
                else (f"{followers/1e3:.0f}k" if followers >= 1000 else "?")
        _, emoji = classify_appearance_reach(followers if followers else None)
        node_totals.append((followers, node_name, cluster, len(recs), f_str, emoji))

    node_totals.sort(reverse=True)
    for followers, node_name, cluster, count, f_str, emoji in node_totals:
        print(f"  {node_name:<20} {cluster:<14} {count:>11}  {f_str:>12}  {emoji}")

    # Print cumulative potential reach
    # (sum of unique node followers across all co-appearances - rough upper bound)
    unique_nodes = {n for n in by_node if n != "unknown"}
    total_reach = sum(
        SPBM_NODES.get(n, {}).get("followers", 0) or 0
        for n in unique_nodes
    )
    print(f"\n  Unique SPBM nodes co-appeared with: {len(unique_nodes)}")
    print(f"  Cumulative potential reach (sum of node followers): "
          f"{total_reach/1e6:.1f}M")

    # Print cluster coverage
    clusters = set(
        SPBM_NODES.get(n, {}).get("cluster", "?")
        for n in unique_nodes
    )
    print(f"  Ideological clusters covered: {', '.join(sorted(clusters))}")

    # Print high-reach appearances
    hp_recs = [r for r in records if r.get("is_hp")]
    if hp_recs:
        print(f"\n  HIGH-REACH APPEARANCES ({len(hp_recs)}):")
        for r in hp_recs[:15]:
            ts   = r.get("timestamp", "")[:10]
            node = r.get("matched_node", "?")
            emoji = r.get("reach_emoji", "")
            print(f"    {ts}  {emoji} {node:<18}  {r['title'][:65]}")

    # Print timeline
    print(f"\n  TIMELINE (most recent first):")
    sorted_recs = sorted(records,
                         key=lambda x: x.get("pubDate") or x.get("timestamp") or "",
                         reverse=True)
    for r in sorted_recs[:20]:
        ts    = (r.get("pubDate") or r.get("timestamp") or "?")[:10]
        node  = r.get("matched_node") or "?"
        emoji = r.get("reach_emoji", "")
        conf  = "✓" if r.get("confirmed") else "~"
        print(f"    {ts}  {conf} {emoji} {node:<18}  {r['title'][:55]}")

    print(f"\n  Full log: {APPEARANCES}")

# ==============================================================================
# HIGH-PRIORITY KEYWORDS (symmetric)
# ==============================================================================

HIGH_PRIORITY = [
    # Network A escalation
    "Carlson Katchanovski", "Greenwald Katchanovski",
    "Mearsheimer Katchanovski", "Tucker Katchanovski",
    "BSW Katchanovski", "AfD Katchanovski", "Wagenknecht Katchanovski",
    "Stortinget Katchanovski", "Bundestag Katchanovski",
    "RT Katchanovski", "Sputnik Katchanovski",
    # Network B breakthroughs
    "Palgrave Katchanovski retract", "Palgrave Katchanovski withdraw",
    "Springer Katchanovski response", "Times Higher Katchanovski",
    "Aslund Katchanovski", "Gentile Katchanovski Oslo",
    # Inversion events (Network A weaponises counterspeech)
    "Katchanovski censorship", "Katchanovski cancel",
    "Katchanovski academic freedom", "Katchanovski silenced",
    # Cross-network
    "petition Katchanovski viral",
]

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default

def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2))

def load_hashes():
    return load_json(HASHES_FILE, {})

def save_hashes(h):
    save_json(HASHES_FILE, h)

def item_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]

def parse_number(text):
    """Parse '248k', '3,174', '248000' -> int. Returns None on failure."""
    if not text:
        return None
    t = text.strip().lower().replace(",", "")
    m = re.match(r"([\d.]+)k", t)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.match(r"([\d]+)", t)
    if m:
        return int(m.group(1))
    return None

def check_url(key, cfg, hashes, network):
    """Fetch a URL and extract the tracked metric. Returns result dict."""
    result = {
        "key": key, "network": network,
        "description": cfg["description"],
        "baseline": cfg["baseline_label"],
        "metric_key": cfg.get("metric_key", key),
        "url": cfg["url"],
        "status": "error", "match": None, "value": None, "changed": False,
    }
    if not REQUESTS_OK:
        result["status"] = "no_requests"
        return result
    try:
        r = requests.get(cfg["url"], timeout=8,
                         headers={"User-Agent": "Mozilla/5.0 (academic research monitor)"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        m = re.search(cfg["pattern"], text)
        if m:
            raw = m.group(1)
            result["match"] = raw
            result["value"] = parse_number(raw)
            h = item_hash(raw + key)
            result["changed"] = (h != hashes.get(key))
            hashes[key] = h
        result["status"] = "ok"
    except requests.RequestException as e:
        result["error"] = str(e)[:100]
    return result

def check_urls(url_cfg, hashes, network):
    return [check_url(k, v, hashes, network) for k, v in url_cfg.items()]

def news_search(query, max_results=5):
    """Google News RSS search. Returns list of result dicts."""
    if not REQUESTS_OK:
        return []
    results = []
    try:
        url = "https://news.google.com/rss/search"
        params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        r = requests.get(url, params=params, timeout=5,
                         headers={"User-Agent": "Mozilla/5.0 (academic research monitor)"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item")[:max_results]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate")
            if title:
                hp_match = [kw for kw in HIGH_PRIORITY
                            if kw.lower() in title.get_text().lower()]
                results.append({
                    "type": "news",
                    "title": title.get_text()[:200],
                    "url": link.get_text() if link else "",
                    "pubDate": pub.get_text() if pub else "",
                    "hp": bool(hp_match),
                    "hp_keywords": hp_match,
                    "query": query,
                })
    except requests.exceptions.Timeout:
        # Google News is rate-limiting this runner IP - skip gracefully
        results.append({"type": "search_skipped", "query": query, 
                        "error": "timeout - Google News rate limiting runner IP"})
    except Exception as e:
        results.append({"type": "search_error", "query": query, "error": str(e)[:80]})
    return results

def detect_new_nodes(results):
    """
    Scan search results for text matching new-node indicator patterns.
    Returns list of candidate new-node findings.
    """
    candidates = []
    known_nodes = (
        set(NETWORK_A_AMPLIFIERS.keys()) |
        set(NETWORK_B_AMPLIFIERS.keys()) |
        {"katchanovski", "umland", "palgrave", "springer"}
    )
    for item in results:
        title = item.get("title", "")
        if not title or item.get("type") == "search_error":
            continue
        matched_indicators = []
        for pattern in NEW_NODE_INDICATORS:
            m = re.search(pattern, title, re.IGNORECASE)
            if m:
                matched_indicators.append(m.group(0))
        if matched_indicators:
            candidates.append({
                "title": title,
                "url": item.get("url", ""),
                "pubDate": item.get("pubDate", ""),
                "matched_indicators": matched_indicators,
                "query": item.get("query", ""),
                "hp": item.get("hp", False),
                "timestamp": datetime.datetime.now().isoformat(),
            })
    return candidates

# ==============================================================================
# NETWORK REACH COMPUTATION
# ==============================================================================

def compute_reach(amplifiers):
    known = {k: v["followers"] for k, v in amplifiers.items() if v.get("followers")}
    unknown = [k for k, v in amplifiers.items() if not v.get("followers")]
    return sum(known.values()), unknown, known

# ==============================================================================
# NODE LEDGER - records node state each run for time-series modelling (NEW v2)
# ==============================================================================

def record_node_ledger(ts, url_results):
    """
    Appends a snapshot of all measurable node values to the node ledger.
    This builds the time-series used for network growth modelling.
    """
    snapshot = {"timestamp": ts, "nodes": {}}
    for r in url_results:
        if r["status"] == "ok" and r["value"] is not None:
            snapshot["nodes"][r["metric_key"]] = {
                "value": r["value"],
                "raw": r.get("match"),
                "network": r["network"],
                "description": r["description"],
            }
    with open(NODE_LEDGER, "a") as f:
        f.write(json.dumps(snapshot) + "\n")
    return snapshot

def compute_growth(current_snapshot):
    """
    Compares current node values with the previous run's values.
    Returns a dict of {metric_key: {current, previous, delta, delta_pct}}.
    """
    # Load all previous snapshots
    if not NODE_LEDGER.exists():
        return {}
    runs = []
    for line in NODE_LEDGER.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                runs.append(json.loads(line))
            except Exception:
                pass

    if len(runs) < 2:
        return {}  # Need at least 2 runs to compute growth

    prev = runs[-2]["nodes"]   # second-to-last run
    curr = current_snapshot["nodes"]

    growth = {}
    for key, data in curr.items():
        curr_val = data["value"]
        if key in prev and prev[key]["value"] is not None and curr_val is not None:
            prev_val = prev[key]["value"]
            delta = curr_val - prev_val
            delta_pct = round(100 * delta / prev_val, 2) if prev_val else None
            growth[key] = {
                "current": curr_val,
                "previous": prev_val,
                "delta": delta,
                "delta_pct": delta_pct,
                "description": data["description"],
                "network": data["network"],
            }
    return growth

# ==============================================================================
# MAIN MONITOR RUN
# ==============================================================================

def run_monitor():
    ts = datetime.datetime.now().isoformat()
    print(f"\n{'='*65}")
    print(f"[{ts[:16]}] Katchanovski Network Monitor v6")
    print(f"{'='*65}")

    hashes = load_hashes()
    all_results = []
    all_url_results = []
    search_skip_count = 0  # Track rate-limited queries

    # -- Network A: URLs ----------------------------------------------------
    print("\n-- Network A: pro-book amplification --")
    a_urls = check_urls(NETWORK_A_URLS, hashes, "A")
    all_url_results.extend(a_urls)
    for r in a_urls:
        if r["status"] == "ok":
            chg = "🔄 CHANGED" if r["changed"] else "✓"
            val = f" -> {r['match']}" if r["match"] else " (no match found)"
            print(f"  {chg} {r['description']}{val}")
            print(f"          baseline: {r['baseline']}")
        else:
            print(f"  ✗ {r['description']} - {r.get('error','check failed')}")

    # -- Network A: news searches -------------------------------------------
    a_news = []
    for term in NETWORK_A_SEARCHES:
        items = news_search(term)
        for it in items:
            it.update({"type": "news", "network": "A", "term": term})
            a_news.append(it)
        time.sleep(2.0)   # polite rate limiting (increased to reduce rate-limit risk)
    all_results.extend(a_urls + a_news)

    # -- Network B: URLs ----------------------------------------------------
    print("\n-- Network B: counterspeech --")
    b_urls = check_urls(NETWORK_B_URLS, hashes, "B")
    all_url_results.extend(b_urls)
    for r in b_urls:
        if r["status"] == "ok":
            chg = "🔄 CHANGED" if r["changed"] else "✓"
            val = f" -> {r['match']}" if r["match"] else " (no match found)"
            print(f"  {chg} {r['description']}{val}")
            print(f"          baseline: {r['baseline']}")
        else:
            print(f"  ✗ {r['description']} - {r.get('error','check failed')}")

    # -- Network B: news searches -------------------------------------------
    b_news = []
    for term in NETWORK_B_SEARCHES:
        items = news_search(term)
        for it in items:
            it.update({"type": "news", "network": "B", "term": term})
            b_news.append(it)
        time.sleep(2.0)
    all_results.extend(b_urls + b_news)

    # -- New-node detection (NEW v2) ----------------------------------------
    print("\n-- New-node detection --")
    nn_news = []
    for term in NEW_NODE_SEARCHES:
        items = news_search(term, max_results=3)
        for it in items:
            it.update({"type": "news", "network": "new_node_scan", "term": term})
            nn_news.append(it)
        time.sleep(2.0)

    new_nodes_found = detect_new_nodes(nn_news)
    if new_nodes_found:
        print(f"  ⚡ {len(new_nodes_found)} potential new-node signals detected:")
        for nn in new_nodes_found[:8]:
            hp_flag = " ⚠️ HP" if nn["hp"] else ""
            print(f"    [{nn['matched_indicators'][0]}]{hp_flag} {nn['title'][:90]}")
        # Append to new-nodes log
        with open(NEW_NODES, "a") as f:
            for nn in new_nodes_found:
                f.write(json.dumps(nn) + "\n")
    else:
        print("  ✓ No new-node signals detected this run")

    all_results.extend(nn_news)

    # -- Podcast & joint-appearance module (v3) ----------------------------
    all_appearances, new_appearances = run_appearance_module()
    hp_from_appearances = [
        {**ap, "network": "appearances", "title": ap.get("title", "")}
        for ap in new_appearances if ap.get("is_hp")
    ]

    # -- Counterspeech appearance module (NEW v4) ---------------------------
    all_cs, new_cs = run_cs_appearance_module()
    hp_from_cs = [
        {**ap, "network": "cs_appearances", "title": ap.get("title", "")}
        for ap in new_cs if ap.get("is_hp")
    ]

    # -- Cross-pollination / overlap module (NEW v4) ------------------------
    all_overlaps, new_overlaps = run_overlap_module()
    hp_from_overlaps = [
        {**ov, "network": "overlap", "title": ov.get("title", "")}
        for ov in new_overlaps if ov.get("is_hp")
    ]
    hp_items = [r for r in all_results if r.get("hp") or r.get("hp_keywords")]
    hp_items.extend(hp_from_appearances)
    hp_items.extend(hp_from_cs)
    hp_items.extend(hp_from_overlaps)
    if hp_items:
        print(f"\n  ⚠️  {len(hp_items)} HIGH-PRIORITY items:")
        for r in hp_items[:14]:
            net   = r.get("network", "?")
            title = r.get("title", r.get("name", "?"))
            kws   = ", ".join(r.get("hp_keywords", [])[:2])
            tag   = f"[{r.get('reach_tier','')}]" if "appearances" in net else ""
            print(f"    [{net}]{tag} {title[:78]}  [{kws}]")
    else:
        print("\n  ✓ No high-priority events this run")

    # -- Node ledger snapshot -----------------------------------------------
    snapshot = record_node_ledger(ts, all_url_results)

    # -- Growth computation -------------------------------------------------
    growth = compute_growth(snapshot)
    if growth:
        print("\n-- 24h growth --")
        for key, g in growth.items():
            delta_str = f"{g['delta']:+,d}"
            pct_str   = f" ({g['delta_pct']:+.1f}%)" if g['delta_pct'] is not None else ""
            flag = " ⚡" if abs(g.get("delta", 0)) > 0 else ""
            print(f"  {g['description']:<40} {g['previous']:>8,} -> {g['current']:>8,}"
                  f"  {delta_str}{pct_str}{flag}")
        growth_record = {"timestamp": ts, "growth": growth}
        with open(GROWTH_FILE, "a") as f:
            f.write(json.dumps(growth_record) + "\n")
    else:
        print("\n  (Growth: need ≥2 runs to compute 24h deltas)")

    # -- Save main log ------------------------------------------------------
    run_data = {
        "timestamp":          ts,
        "network_a_items":    len(a_urls) + len(a_news),
        "network_b_items":    len(b_urls) + len(b_news),
        "hp_count":           len(hp_items),
        "new_node_signals":   len(new_nodes_found),
        "appearances_total":  len(all_appearances),
        "appearances_new":    len(new_appearances),
        "cs_total":           len(all_cs),
        "cs_new":             len(new_cs),
        "overlap_total":      len(all_overlaps),
        "overlap_new":        len(new_overlaps),
        "tv_appearances_new": sum(1 for o in new_overlaps              # NEW v6
                                  if o.get("overlap_type") == "tv_appearance"),
        "node_snapshot":      snapshot["nodes"],
        "growth":             growth,
        "results":            all_results,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(run_data) + "\n")

    # -- Generate daily markdown report ------------------------------------
    write_report(ts, run_data, a_urls, b_urls, hp_items, new_nodes_found, growth,
                 new_appearances, new_cs, new_overlaps)

    save_hashes(hashes)
    print(f"\n  Saved -> {LOG_FILE.name}")
    print(f"  Saved -> {REPORT_FILE.name}")
    print(f"  Saved -> {NODE_LEDGER.name}")
    if new_nodes_found:
        print(f"  Saved -> {NEW_NODES.name}")
    if new_appearances:
        print(f"  Saved -> {APPEARANCES.name}")
    if new_cs:
        print(f"  Saved -> {CS_APPEARANCES.name}")
    if new_overlaps:
        print(f"  Saved -> {OVERLAP_LOG.name}")
    if growth:
        print(f"  Saved -> {GROWTH_FILE.name}")

    return run_data

# ==============================================================================
# REPORT WRITER
# ==============================================================================

def write_report(ts, run_data, a_urls, b_urls, hp_items, new_nodes, growth,
                 new_appearances=None, new_cs=None, new_overlaps=None):
    new_appearances = new_appearances or []
    new_cs          = new_cs or []
    new_overlaps    = new_overlaps or []
    lines = [
        f"## [{ts[:10]}] Monitor Run - {ts[11:16]}",
        f"*A:{run_data['network_a_items']} | B:{run_data['network_b_items']} | "
        f"HP:{run_data['hp_count']} | NN:{run_data['new_node_signals']} | "
        f"A-ap:{run_data['appearances_new']} | B-ap:{run_data['cs_new']} | "
        f"Overlap:{run_data['overlap_new']}*",
        "",
        "### Tracked Metrics",
        "| Net | Metric | Current | Baseline | Δ |",
        "|-----|--------|---------|----------|---|",
    ]
    for r in a_urls + b_urls:
        if r["status"] == "ok":
            curr = r.get("match", "n/a")
            delta = ""
            if r["metric_key"] in growth:
                g = growth[r["metric_key"]]
                delta = f"{g['delta']:+,d}" if g['delta'] else "-"
            lines.append(f"| {r['network']} | {r['description']} | "
                         f"{curr} | {r['baseline']} | {delta} |")

    if growth:
        lines += [
            "",
            "### 24h Growth",
            "| Metric | Previous | Current | Δ | Δ% |",
            "|--------|----------|---------|---|-----|",
        ]
        for key, g in growth.items():
            lines.append(
                f"| {g['description']} | {g['previous']:,} | {g['current']:,} | "
                f"{g['delta']:+,d} | {g['delta_pct']:+.1f}% |"
            )

    if hp_items:
        lines += ["", "### ⚠️ High-Priority Events"]
        for r in hp_items[:10]:
            kws = ", ".join(r.get("hp_keywords", [])[:3])
            lines.append(f"- **[{r.get('network','?')}]** {r.get('title','')[:120]}  "
                         f"*(triggers: {kws})*")

    if new_nodes:
        lines += ["", "### ⚡ Potential New Nodes"]
        lines.append("*Emerging actors detected by new-node indicator patterns:*")
        for nn in new_nodes[:10]:
            inds = ", ".join(nn["matched_indicators"][:2])
            lines.append(f"- [{inds}] {nn['title'][:110]}")
            if nn.get("url"):
                lines.append(f"  {nn['url'][:100]}")

    if new_appearances:
        lines += ["", "### 🎙 New Podcast / Joint Appearances"]
        lines.append(
            "| Reach tier | Node | Cluster | Confirmed | Title |"
        )
        lines.append("|------------|------|---------|-----------|-------|")
        for ap in new_appearances[:15]:
            node    = ap.get("matched_node") or "?"
            cluster = ap.get("node_cluster") or "?"
            tier    = ap.get("reach_tier", "?")
            emoji   = ap.get("reach_emoji", "")
            conf    = "✓" if ap.get("confirmed") else "~"
            title   = ap.get("title", "")[:60]
            url     = ap.get("url", "")
            link    = f"[{title}]({url})" if url else title
            lines.append(
                f"| {emoji} {tier} | {node} | {cluster} | {conf} | {link} |"
            )

    if new_cs:
        lines += ["", "### 📢 New Counterspeech Events (Network B)"]
        lines.append("| Type | Node | Tier | Confirmed | Title |")
        lines.append("|------|------|------|-----------|-------|")
        for ap in new_cs[:15]:
            node  = ap.get("matched_node") or "?"
            tier  = ap.get("reach_tier", "?")
            emoji = ap.get("reach_emoji", "")
            etype = "PLATFORM" if ap.get("event_type") == "platform_coverage" else "signatory"
            conf  = "✓" if ap.get("confirmed") else "~"
            title = ap.get("title", "")[:55]
            url   = ap.get("url", "")
            link  = f"[{title}]({url})" if url else title
            lines.append(f"| {etype} | {node} | {emoji}{tier} | {conf} | {link} |")

    if new_overlaps:
        lines += ["", "### 🔗 Cross-Pollination Signals"]
        for ov in new_overlaps[:8]:
            otype = ov["overlap_type"].upper()
            a_str = "+".join(ov["a_nodes_hit"][:2])
            b_str = "+".join(ov["b_nodes_hit"][:2])
            hp    = " ⚠️" if ov.get("is_hp") else ""
            lines.append(f"- [{otype}]{hp} A:[{a_str}] ↔ B:[{b_str}] - {ov['title'][:70]}")

    lines += ["", "---", ""]

    with open(REPORT_FILE, "a") as f:
        f.write("\n".join(lines) + "\n")

# ==============================================================================
# GROWTH DISPLAY
# ==============================================================================

def print_growth_history():
    if not GROWTH_FILE.exists():
        print("No growth data yet. Run monitor at least twice.")
        return
    records = [json.loads(l) for l in GROWTH_FILE.read_text().splitlines() if l.strip()]
    if not records:
        print("No growth records yet.")
        return

    print("\n" + "="*75)
    print("GROWTH HISTORY - ALL RUNS")
    print("="*75)

    # Collect all metric keys across all records
    all_keys = []
    for rec in records:
        for k in rec["growth"]:
            if k not in all_keys:
                all_keys.append(k)

    print(f"\n{'Date':<12}", end="")
    for k in all_keys:
        label = k[:14]
        print(f"  {label:>14}", end="")
    print()
    print("-"*75)

    for rec in records:
        ts = rec["timestamp"][:10]
        print(f"{ts:<12}", end="")
        for k in all_keys:
            if k in rec["growth"]:
                g = rec["growth"][k]
                val = f"{g['current']:,}"
                delta = f"({g['delta']:+,d})"
                cell = f"{val} {delta}"
            else:
                cell = "-"
            print(f"  {cell:>14}", end="")
        print()

# ==============================================================================
# NODE LEDGER DUMP
# ==============================================================================

def print_node_ledger():
    if not NODE_LEDGER.exists():
        print("No node ledger yet. Run monitor first.")
        return
    records = [json.loads(l) for l in NODE_LEDGER.read_text().splitlines() if l.strip()]
    print(f"\n{len(records)} node snapshots in ledger\n")
    print(f"{'Timestamp':<22}  {'Metric':<35}  {'Value':>10}")
    print("-"*72)
    for rec in records:
        ts = rec["timestamp"][:16]
        for key, data in rec["nodes"].items():
            print(f"{ts:<22}  {data['description']:<35}  {data['value']:>10,}")

# ==============================================================================
# A vs B COMPARISON
# ==============================================================================

def print_comparison():
    a_reach, a_unk, a_known = compute_reach(NETWORK_A_AMPLIFIERS)
    b_reach, b_unk, b_known = compute_reach(NETWORK_B_AMPLIFIERS)

    print("\n" + "="*65)
    print("NETWORK A vs B - SYMMETRICAL COMPARISON")
    print("="*65)
    print(f"\n{'METRIC':<38} {'NETWORK A':>13} {'NETWORK B':>13}")
    print("-"*65)
    print(f"{'Total documented reach':<38} {a_reach/1e6:>12.1f}M {b_reach/1000:>12.0f}k")
    print(f"{'Amplifiers with known reach':<38} {len(a_known):>13} {len(b_known):>13}")
    print(f"{'Amplifiers reach TBD':<38} {len(a_unk):>13} {len(b_unk):>13}")
    if b_reach > 0:
        ratio = int(a_reach / b_reach)
        print(f"{'A/B raw reach ratio':<38} {'~'+str(ratio)+':1':>13} {'1:1':>13}")

    print(f"\nPLATFORM PRESENCE")
    print(f"  A: X (primary, Musk-owned), YouTube, Substack, Rumble, Podcast")
    print(f"  B: X, Bluesky (non-Musk), Academic journals, Policy media, Atlantic Council")
    print(f"  Key asymmetry: Book has 3,174 X posts (Apr 1); Bluesky has ~5 results")

    print(f"\nAUDIENCE QUALITY (ri × policy-relevance)")
    print(f"  A: General audience (Musk 200M = low Ukraine policy density)")
    print(f"  B: Policy/academic audience (Aslund 357k = high decision-maker density)")
    print(f"  Prediction: B generates more political impact per follower")

    print(f"\nBOOK ACCESS TRAJECTORY (springer_accesses baseline)")
    print(f"  Dec 31, 2025: 159k  | Growth: +89k in 3 months")
    print(f"  Mar 31, 2026: 248k  | Petition filed: April 28, 2026")
    print(f"  Key question: Does counterspeech petition slow or accelerate access growth?")

    print(f"\nMCHANGAMA FREE SPEECH TEST")
    print(f"  Hypothesis: A scholarly counterspeech campaign (Network B) that")
    print(f"  occupies the same information space - without calling for removal -")
    print(f"  can compete with a high-reach amplification network (Network A).")
    print(f"  Inversion risk: If Carlson/Greenwald frame petition as 'censorship',")
    print(f"  Network B becomes fuel for Network A (Streisand effect).")

    print(f"\nKEY UNKNOWNS (resolved through monitoring)")
    print(f"  1. Does Palgrave/Springer respond to the petition?")
    print(f"  2. Does any academic journal assign a formal review?")
    print(f"  3. Does Michael Gentile (Oslo) generate Norwegian media coverage?")
    print(f"  4. Does Aslund post about Katchanovski on X? (324k reach trigger)")
    print(f"  5. Does Carlson/Greenwald cover the petition? (inversion event)")
    print(f"  6. Does any legislature reference the book?")

    # Appearance-based reach comparison (from logged data)
    print(f"\n{'-'*65}")
    print(f"APPEARANCE-BASED REACH COMPARISON (from logged events)")
    print(f"{'-'*65}")

    def load_reach_from_log(filepath, follower_key):
        if not filepath.exists():
            return 0, 0
        records = [json.loads(l) for l in filepath.read_text().splitlines() if l.strip()]
        unique_nodes = {r.get("matched_node") for r in records if r.get("matched_node")}
        total = sum(r.get(follower_key, 0) or 0 for r in records
                    if r.get(follower_key))
        return len(records), total

    a_count, a_ap_reach = load_reach_from_log(APPEARANCES,    "node_followers")
    b_count, b_ap_reach = load_reach_from_log(CS_APPEARANCES, "node_audience")

    print(f"\n  {'METRIC':<40} {'NET A':>12} {'NET B':>12}")
    print(f"  {'-'*65}")
    print(f"  {'Confirmed appearance events logged':<40} {a_count:>12} {b_count:>12}")
    a_r = f"{a_ap_reach/1e6:.1f}M" if a_ap_reach >= 1e6 else f"{a_ap_reach/1e3:.0f}k"
    b_r = f"{b_ap_reach/1e6:.1f}M" if b_ap_reach >= 1e6 else f"{b_ap_reach/1e3:.0f}k"
    print(f"  {'Cumulative node-reach across events':<40} {a_r:>12} {b_r:>12}")
    if a_ap_reach > 0 and b_ap_reach > 0:
        ratio = a_ap_reach / b_ap_reach
        print(f"  {'A/B reach ratio from logged events':<40} {ratio:>11.0f}:1 {'1:1':>12}")
    elif a_count == 0 and b_count == 0:
        print(f"  (No appearance events logged yet - run monitor to populate)")

    # Cross-pollination summary
    if OVERLAP_LOG.exists():
        ov_records = [json.loads(l) for l in OVERLAP_LOG.read_text().splitlines() if l.strip()]
        inv = sum(1 for r in ov_records if r["overlap_type"] == "inversion_signal")
        node_ov = sum(1 for r in ov_records if r["overlap_type"] == "node_overlap")
        shared_ov = sum(1 for r in ov_records if r["overlap_type"] == "shared_outlet")
        print(f"\n  CROSS-POLLINATION SIGNALS LOGGED")
        print(f"  Node overlap:     {node_ov:>4}  (same item mentions A+B nodes)")
        print(f"  Inversion:        {inv:>4}  ⚠️  (A weaponising B counterspeech)")
        print(f"  Shared outlet:    {shared_ov:>4}  (same outlet covers both networks)")
        print(f"  Run 'overlap' command for full cross-pollination analysis")



# ==============================================================================
# NORWEGIAN SUB-NETWORK REPORT  (NEW v5)
# ==============================================================================

def print_norway_report():
    """
    Norwegian sub-network: Diesen/Peace&Justice/Rybar (A)
    vs Ukrainapodden/Forsvarspodden/Berger/Heier/Mjor/Holtsmark (B).
    A compressed live test of the SPBM model in a single national context.
    """
    print("\n" + "="*75)
    print("NORWEGIAN SUB-NETWORK REPORT")
    print("Compressed live test: Diesen/Peace&Justice/Rybar (A)")
    print("vs Ukrainapodden/Forsvarspodden/Berger/Heier/Mjor/Holtsmark (B)")
    print("="*75)

    print(f"\nNETWORK A - Norwegian nodes")
    print(f"  {'Node':<30} {'Type':<18} {'Followers':>10}  Note")
    print("  " + "-"*72)
    no_a = [
        ("Diesen (Glenn Diesen)",      "amplifier",       100_000, "USN professor; RT; Dialogue Works"),
        ("Peace and Justice (FOR)",    "party",             5_000,  "Diesen campaign; Russian narrative proxy"),
        ("Greater Eurasia Podcast",    "A-platform",       50_000,  "Diesen daily podcast; Apple/Spotify"),
        ("Nistad (Bjorn Nistad)",      "peripheral",        3_000,  "Pro-Kremlin blogger; Crimea defender"),
        ("War on Fakes / WarFakes",    "ru_OSINT_mimic", 1_000_000, "Weaponised OSINT; apes Bellingcat"),
        ("Rybar (Telegram)",           "ru_infra",       1_300_000, "Russian mil. channel; frontline authority"),
        ("Readovka (Telegram)",        "ru_infra",         850_000, "Kremlin narrative Telegram channel"),
    ]
    for node, tier, followers, note in no_a:
        f_str = f"{followers/1e6:.1f}M" if followers >= 1e6 else f"{followers/1e3:.0f}k"
        print(f"  {node:<30} {tier:<18} {f_str:>10}  {note[:40]}")

    print(f"\nNETWORK B - Norwegian nodes")
    print(f"  {'Node':<30} {'Type':<18} {'Followers':>10}  Note")
    print("  " + "-"*72)
    no_b = [
        ("Ukrainapodden (Nettavisen)",  "platform",     35_000, "Prize-winning daily; pro-Ukraine"),
        ("Forsvarspodden (Forsvaret)",  "platform",     25_000, "Official Armed Forces; Prix Norge"),
        ("Krig og Sann (Forsv.forum)", "platform",     15_000, "Defense magazine; 65k circulation"),
        ("Heier (Tormod Heier)",        "signatory",    10_000, "Military professor; SPBM source"),
        ("Berger (Bjorn Johan Berger)", "OSINT_critic",  8_000, "UNIQUE: NRK whitewashing critic"),
        ("Holtsmark (Sven G.)",         "academic",      5_000, "Historian; Diesen misrepresents sources"),
        ("Mjor (Kare Johan)",           "academic",      5_000, "Russian studies; Diesen=propaganda"),
        ("Gentile (Michael)",           "signatory",     5_000, "Univ. Oslo; ONLY Norwegian signatory"),
        ("Faktisk (NRK/VG/Dagbladet)", "fact_checker", 40_000, "50% Norwegian awareness; NRK tension"),
        ("Bellingcat",                  "counter_OSINT", 500_000, "Gold standard; monitoring Katchanovski"),
        ("Correctiv (Germany)",         "fact_checker", 150_000, "BSW/Doppelganger = natural story"),
    ]
    for node, tier, followers, note in no_b:
        f_str = f"{followers/1e6:.1f}M" if followers >= 1e6 else f"{followers/1e3:.0f}k"
        print(f"  {node:<30} {tier:<18} {f_str:>10}  {note[:40]}")

    print(f"\nTHE BERGER / NRK WHITEWASHING MECHANISM (SPBM Sections 4.5 / 7.1)")
    print(f"  Russian narrative -> NRK (kappa_i ~0, trusted broadcaster) -> Norwegian public")
    print(f"  NRK legitimacy suppresses attribution: the SPBM kappa_i mechanism documented.")
    cases = [
        ("Jun 2022", "Diesen on NRK Helgemorgen: NRK admitted inadequate context"),
        ("Sep 2022", "NRK referendum interviews from occupied territories: NRK apologised"),
        ("Jul 2023", "NRK cluster munitions: Berger article in Medier24"),
        ("Feb 2024", "NRK Avdiivka/Shoigu unchallenged claim: NRK issued correction"),
    ]
    for date, case in cases:
        print(f"    {date}: {case}")
    print(f"  No direct international equivalent at individual level found.")

    a_direct   = 100_000 + 5_000 + 50_000 + 3_000
    a_ru_infra = 1_000_000 + 1_300_000 + 850_000
    b_total    = 35_000 + 25_000 + 15_000 + 10_000 + 8_000 + 5_000 + 5_000 + 5_000 + 40_000

    print(f"\n  REACH COMPARISON (Norwegian context)")
    print(f"  A direct nodes (excl. Russian infra):  {a_direct/1e3:.0f}k")
    print(f"  A Russian Telegram infrastructure:      {a_ru_infra/1e6:.1f}M")
    print(f"  B Norwegian nodes combined:             {b_total/1e3:.0f}k")
    print(f"  A/B direct ratio:    {a_direct/b_total:.1f}:1")
    print(f"  A/B including Rybar/WarFakes: {(a_direct+a_ru_infra)/b_total:.0f}:1")
    print(f"\n  MONITORING PRIORITIES")
    print(f"  1. Faktisk fact-check on Katchanovski/Diesen? (NRK structural tension)")
    print(f"  2. Correctiv covers BSW-Katchanovski Germany?")
    print(f"  3. Bellingcat/DFRLab investigates Musk/Sacks amplification network?")
    print(f"  4. Berger forces NRK correction specifically on Katchanovski?")
    print(f"  5. Peace & Justice references Katchanovski in Stortinget?")
    print(f"  6. Rybar or War on Fakes amplifies Katchanovski on Telegram?")


# ==============================================================================
# BROADCAST TV REPORT  (NEW v6)
# ==============================================================================

def print_tv_report():
    """
    Print the broadcast TV sub-report: NRK, ARD, ZDF as cross-pollination nodes.
    TV debates are the only format with genuine shared A/B audience.
    """
    print("\n" + "="*75)
    print("BROADCAST TV REPORT - Cross-Pollination Nodes")
    print("Only format with genuine A+B network audience overlap")
    print("="*75)

    print(f"\nBROADCAST NODES - verified audience figures")
    print(f"  {'Channel':<22} {'Country':>4} {'Daily audience':>15}  Key formats / SPBM relevance")
    print("  " + "-"*75)
    for name, meta in BROADCAST_NODES.items():
        aud = meta["audience_daily"]
        a_str = f"{aud/1e6:.1f}M" if aud >= 1e6 else f"{aud/1e3:.0f}k"
        country = meta["country"]
        formats = ", ".join(meta["key_formats"][:2])
        note = meta["spbm_relevance"][:50]
        print(f"  {name:<22} {country:>4} {a_str:>15}  {formats}")
        print(f"  {'':22} {'':>4} {'':>15}  {note}")

    print(f"\nWHY TV IS ANALYTICALLY DISTINCT")
    print(f"  All other nodes (X, YouTube, Substack, podcasts) serve pre-sorted audiences:")
    print(f"    A-network: populist/anti-NATO audiences seeking confirming content")
    print(f"    B-network: academic/policy audiences already sceptical of Katchanovski")
    print(f"  TV debate formats (NRK Debatten, ZDF Markus Lanz, ARD Hart aber fair)")
    print(f"  are consumed by the GENERAL PUBLIC - not pre-sorted by political stance.")
    print(f"  A Katchanovski reference on Tagesschau reaches 9.6M unfiltered Germans.")
    print(f"  This is the ONLY channel where counterspeech reaches the A-network's audience.")

    print(f"\nSPBM PAPER ANALYTICAL IMPLICATION")
    print(f"  The platform polarisation argument (Section 11.4) predicts LOW audience overlap")
    print(f"  across X/Bluesky and specialist podcast divides. But TV is the exception:")
    print(f"  if the Katchanovski book enters German or Norwegian public TV debate, this")
    print(f"  violates the platform-segregation prediction and would constitute evidence")
    print(f"  that the SPBM's indirect campaign HAS crossed into mainstream information space.")
    print(f"  That would be the paper's most important empirical finding.")

    print(f"\nKEY TV MONITORING ALERTS - triggers for immediate attention")
    alerts = [
        ("NRK Debatten episode on Katchanovski/Diesen",
         "~1.8M Norwegian viewers; genuine A+B overlap; Berger mechanism at scale"),
        ("ZDF Markus Lanz episode mentioning Katchanovski",
         "~4M German viewers; Varwick and BSW guests; highest German TV priority"),
        ("ARD Tagesschau report on Katchanovski amplification",
         "~9.6M German viewers; most trusted German news; would be landmark event"),
        ("ARD/ZDF Brennpunkt special on Russian academic publishing influence",
         "Up to 7-8M special bulletin audience; ZDF Putins Agenten angle"),
        ("NRK Faktasjekk / Faktisk on Katchanovski or Diesen",
         "Structural tension: NRK fact-checks its own platform issue"),
        ("Phoenix Runde debate: Katchanovski/BSW narrative vs counter-voices",
         "~700k policy audience; Bundestag-adjacent; high political density"),
    ]
    for i, (alert, note) in enumerate(alerts, 1):
        print(f"  {i}. {alert}")
        print(f"     -> {note}")

    # Load and display any logged TV appearances
    if OVERLAP_LOG.exists():
        tv_events = []
        for line in OVERLAP_LOG.read_text().splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    if r.get("overlap_type") == "tv_appearance":
                        tv_events.append(r)
                except Exception:
                    pass
        if tv_events:
            print(f"\n  LOGGED TV EVENTS ({len(tv_events)} total):")
            for r in sorted(tv_events, key=lambda x: x.get("pubDate",""), reverse=True)[:10]:
                ts   = (r.get("pubDate") or r.get("timestamp","?"))[:10]
                tvs  = ", ".join(r.get("tv_hits",["?"])[:2])
                print(f"    {ts}  [{tvs}]  {r['title'][:60]}")
        else:
            print(f"\n  No TV appearances logged yet.")
            print(f"  (Monitor is searching; first TV coverage will appear here when detected)")

# ==============================================================================
# DAEMON MODE - built-in 24h scheduler (NEW v2)
# ==============================================================================

def run_daemon():
    """
    Runs continuously, firing a monitor cycle every RUN_INTERVAL_HOURS.
    For server/always-on machines. For cron-based scheduling (preferred
    for personal machines), use: 0 8 * * * python3 this_script.py
    """
    print(f"Daemon mode: firing every {RUN_INTERVAL_HOURS}h")
    print(f"Log: {LOG_FILE}")
    print(f"Press Ctrl-C to stop.\n")

    while True:
        try:
            run_data = run_monitor()
            hp  = run_data.get("hp_count", 0)
            nn  = run_data.get("new_node_signals", 0)
            na  = run_data.get("appearances_new", 0)
            nb  = run_data.get("cs_new", 0)
            nov = run_data.get("overlap_new", 0)
            if hp > 0 or nn > 0 or na > 0 or nb > 0 or nov > 0:
                print(f"\n  *** ALERT: HP={hp} NN={nn} A-ap={na} B-ap={nb} "
                      f"Overlap={nov} ***")
                print(f"  Check {REPORT_FILE.name} for details")
        except KeyboardInterrupt:
            print("\nDaemon stopped by user.")
            break
        except Exception as e:
            print(f"  Run error: {e}. Retrying in 1h.")
            time.sleep(3600)
            continue

        next_run = datetime.datetime.now() + datetime.timedelta(hours=RUN_INTERVAL_HOURS)
        print(f"\n  Next run: {next_run.strftime('%Y-%m-%d %H:%M')}")
        try:
            time.sleep(RUN_INTERVAL_HOURS * 3600)
        except KeyboardInterrupt:
            print("\nDaemon stopped by user.")
            break

# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "daemon":
        run_daemon()
    elif cmd == "compare":
        print_comparison()
    elif cmd == "growth":
        print_growth_history()
    elif cmd == "nodes":
        print_node_ledger()
    elif cmd == "appearances":
        print_appearance_log()
    elif cmd == "counterspeech":
        print_cs_appearance_log()
    elif cmd == "overlap":
        print_overlap_report()

    elif cmd == "norway":
        print_norway_report()

    elif cmd == "tv":
        print_tv_report()
    elif cmd == "summary":
        if LOG_FILE.exists():
            runs = [json.loads(l) for l in LOG_FILE.read_text().splitlines() if l.strip()]
            print(f"\n{len(runs)} monitor runs logged")
            print(f"{'Timestamp':<18} A    B   HP   NN  A-ap  B-ap  Ovlp  Growth")
            print("-" * 72)
            for r in runs[-10:]:
                ts   = r["timestamp"][:16]
                hp   = r.get("hp_count", 0)
                nn   = r.get("new_node_signals", 0)
                na   = r.get("appearances_new", 0)
                nb   = r.get("cs_new", 0)
                nov  = r.get("overlap_new", 0)
                growth = r.get("growth", {})
                g_str = ", ".join(
                    f"{v['description'][:14]} {v['delta']:+,d}"
                    for v in list(growth.values())[:2]
                ) if growth else "-"
                print(f"{ts:<18} {r['network_a_items']:>4} {r['network_b_items']:>4}"
                      f" {hp:>4} {nn:>4} {na:>5} {nb:>5} {nov:>5}  {g_str}")
        else:
            print("No log file yet. Run monitor first.")
    else:
        run_data = run_monitor()
        sys.exit(1 if run_data["hp_count"] > 0 else 0)
