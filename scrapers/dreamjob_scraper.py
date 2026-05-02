"""
Scraper Dreamjob.ma - Version améliorée (2 étapes)
==================================================
Étape 1 : récupérer les liens des offres depuis la page de recherche
Étape 2 : visiter chaque offre pour extraire les détails complets

Insère dans bronze.dreamjob_raw
"""

import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from config import engine

BASE_URL = "https://www.dreamjob.ma/"
KEYWORD = "data"
NB_PAGES = 5
DELAY = 1.0  # délai entre requêtes (politesse)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# ==== Patterns pour extraction ====
VILLES_MAROC = [
    "Casablanca", "Rabat", "Marrakech", "Tanger", "Fès", "Fes", "Agadir",
    "Meknès", "Meknes", "Oujda", "Kénitra", "Kenitra", "Tétouan", "Tetouan",
    "Salé", "Sale", "El Jadida", "Mohammedia", "Khouribga", "Beni Mellal",
    "Nador", "Settat", "Berrechid", "Laâyoune", "Laayoune", "Dakhla",
    "Témara", "Temara", "Safi", "Essaouira", "Ifrane", "Ouarzazate",
    "Maroc", "Morocco"
]

CONTRATS = {
    "CDI": r"\bCDI\b",
    "CDD": r"\bCDD\b",
    "Stage": r"\bstage(?:s)?\b",
    "Freelance": r"\bfreelance\b",
    "Alternance": r"\balternance\b",
    "Intérim": r"\bint[ée]rim\b",
    "PFE": r"\bPFE\b",
}

# Niveaux d'études fréquents
NIVEAUX_ETUDES = [
    ("Bac+5", r"\bBac\s*\+\s*5\b|\bMaster\b|\bing[ée]nieur\b"),
    ("Bac+3", r"\bBac\s*\+\s*3\b|\bLicence\b"),
    ("Bac+2", r"\bBac\s*\+\s*2\b|\bBTS\b|\bDUT\b"),
    ("Doctorat", r"\bDoctorat\b|\bPhD\b"),
    ("Bac+4", r"\bBac\s*\+\s*4\b"),
]


def clean_text(s):
    """Nettoie un texte (espaces multiples, etc.)"""
    if not s:
        return None
    return re.sub(r"\s+", " ", s).strip()


def extract_company_from_alt(alt):
    """
    Nettoie l'alt de l'image pour extraire le nom de l'entreprise.
    Ex: 'Leyton Emploi Recrutement' -> 'Leyton'
        'Capgemini Engineering Emploi Recrutement' -> 'Capgemini Engineering'
        'CIMR' -> 'CIMR'
    """
    if not alt:
        return None
    cleaned = re.sub(r"\b(Emploi|Recrutement|Maroc|Morocco)\b", "", alt, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—")
    return cleaned if cleaned else None


def extract_company_from_title(title):
    """
    Extrait l'entreprise depuis le titre.
    Ex: 'Leyton lance un recrutement...' -> 'Leyton'
        'CIMR lance un recrutement...' -> 'CIMR'
        'Postes ouverts chez Capgemini Maroc...' -> 'Capgemini Maroc'
        'Recrutement EMSI, postes...' -> 'EMSI'
    """
    if not title:
        return None

    patterns = [
        r"^(.+?)\s+(?:lance|recrute|recherche|ouvre|renforce)\b",
        r"\bchez\s+([A-ZÉÀÈ][\w\s&\-\.]+?)(?:\s+en|\s+pour|\s*$|,|\.|:)",
        r"^Recrutement\s+([A-ZÉÀÈ][\w\s&\-\.]+?)(?:\s*,|\s+postes|\s+pour|\s*:|\s*$)",
        r"^(?:Postes?\s+(?:ouverts?|à pourvoir)\s+(?:chez|à|au))\s+([A-ZÉÀÈ][\w\s&\-\.]+?)(?:\s+en|\s+pour|\s*$|,|\.|:)",
    ]
    for pattern in patterns:
        m = re.search(pattern, title, flags=re.IGNORECASE)
        if m:
            company = m.group(1).strip(" -–—,.:")
            if 2 < len(company) < 60:
                return company
    return None


def extract_location(text):
    """Cherche une ville marocaine dans le texte."""
    if not text:
        return None
    for ville in VILLES_MAROC:
        if re.search(rf"\b{re.escape(ville)}\b", text, flags=re.IGNORECASE):
            return ville
    return None


def extract_contract_type(text):
    """Détecte le type de contrat dans le texte."""
    if not text:
        return None
    found = []
    for label, pattern in CONTRATS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(label)
    return " - ".join(found) if found else None


def extract_education(text):
    """Détecte le niveau d'étude."""
    if not text:
        return None
    for label, pattern in NIVEAUX_ETUDES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def extract_experience(text):
    """
    Cherche un nombre d'années d'expérience.
    Ex: '3 ans d'expérience', 'minimum 5 ans', 'entre 2 et 5 ans'
    """
    if not text:
        return None
    patterns = [
        r"(\d+)\s*(?:à|-|–)\s*(\d+)\s*ans?\s*d['e ]+exp[ée]rience",
        r"(?:minimum\s+)?(\d+)\s*ans?\s*(?:d['e ]+exp[ée]rience|minimum)",
        r"exp[ée]rience\s*(?:de|:)?\s*(\d+)\s*(?:à|-|–)?\s*(\d+)?\s*ans?",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g]
            if len(groups) == 2:
                return f"{groups[0]}-{groups[1]} ans"
            return f"{groups[0]} ans"
    if re.search(r"\bdébutant\b|\bjunior\b|\bsans\s+exp[ée]rience\b", text, flags=re.IGNORECASE):
        return "Débutant / Junior"
    if re.search(r"\bsenior\b|\bconfirm[ée]\b", text, flags=re.IGNORECASE):
        return "Senior / Confirmé"
    return None


def extract_function(title, text):
    """
    Détecte la fonction métier (Data Scientist, Data Engineer, etc.)
    """
    sources = " ".join([t for t in [title, text] if t])
    metiers = [
        "Data Scientist", "Data Engineer", "Data Analyst", "Data Manager",
        "Machine Learning Engineer", "ML Engineer", "BI Developer",
        "Business Intelligence", "Big Data Engineer", "DevOps", "MLOps",
        "Architect", "Architecte Data", "Chef de projet Data",
        "Analyste", "Développeur", "Consultant",
    ]
    found = []
    for m in metiers:
        if re.search(rf"\b{re.escape(m)}\b", sources, flags=re.IGNORECASE):
            found.append(m)
    return " - ".join(found[:3]) if found else None


# ==========================================================
#                       SCRAPING
# ==========================================================

def get_search_url(page_num):
    """URL de la page de recherche."""
    if page_num == 1:
        return f"{BASE_URL}?s={KEYWORD}"
    return f"{BASE_URL}page/{page_num}/?s={KEYWORD}"


def parse_list_page(html):
    """
    Parse la page de liste et retourne les infos de base de chaque offre :
    title, url, posted_date, company (depuis alt), excerpt
    """
    soup = BeautifulSoup(html, "lxml")
    articles = soup.find_all("article", class_="jeg_post")
    offers = []

    for art in articles:
        # Titre + URL
        title_tag = art.select_one("h3.jeg_post_title a")
        if not title_tag:
            continue
        title = clean_text(title_tag.get_text())
        offer_url = title_tag.get("href", "").strip()

        # Date
        date_tag = art.select_one(".jeg_meta_date a")
        posted_date = None
        if date_tag:
            txt = date_tag.get_text(strip=True)
            m = re.search(r"\d{2}/\d{2}/\d{4}", txt)
            if m:
                posted_date = m.group(0)

        # Entreprise (depuis alt de l'image)
        img = art.select_one(".jeg_thumb img")
        company_from_alt = None
        if img:
            alt = img.get("alt", "") or img.get("title", "")
            company_from_alt = extract_company_from_alt(alt)

        # Excerpt
        excerpt_tag = art.select_one(".jeg_post_excerpt p")
        excerpt = clean_text(excerpt_tag.get_text()) if excerpt_tag else ""
        excerpt = excerpt.strip('"').strip()

        offers.append({
            "title": title,
            "url": offer_url,
            "posted_date": posted_date,
            "company_from_alt": company_from_alt,
            "excerpt": excerpt,
        })
    return offers


def fetch_offer_details(url):
    """
    Visite une page d'offre individuelle et extrait le contenu complet.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")

        # Le contenu de l'article est généralement dans .content-inner ou .entry-content
        content_div = (soup.select_one(".content-inner")
                       or soup.select_one(".entry-content")
                       or soup.select_one("article"))

        if not content_div:
            return ""

        # On supprime les scripts/styles/iframes
        for tag in content_div.find_all(["script", "style", "iframe", "noscript"]):
            tag.decompose()

        full_text = content_div.get_text(separator=" ", strip=True)
        return clean_text(full_text)
    except Exception as e:
        print(f"      ⚠️  Erreur fetch détails : {e}")
        return ""


def build_offer_record(base_offer, full_description):
    """
    Combine les infos de la liste + page détail pour produire un enregistrement complet.
    Tente d'extraire un maximum de métadonnées via regex/patterns.
    """
    title = base_offer.get("title")
    excerpt = base_offer.get("excerpt", "")

    # Texte combiné (excerpt + description complète) pour l'extraction
    combined_text = f"{excerpt} {full_description}".strip()

    # Entreprise : on essaie l'alt, puis le titre
    company = base_offer.get("company_from_alt") or extract_company_from_title(title)

    # Localisation : on cherche d'abord dans excerpt puis description
    location = extract_location(excerpt) or extract_location(full_description)

    # Métadonnées extraites
    contract_type = extract_contract_type(combined_text)
    education = extract_education(combined_text)
    experience = extract_experience(combined_text)
    function = extract_function(title, combined_text)

    return {
        "job_title": title,
        "company": company,
        "location": location,
        "summary": excerpt,
        "description": full_description[:5000] if full_description else "",  # limite de taille
        "sector": None,  # rarement explicite sur dreamjob
        "function": function,
        "experience": experience,
        "education": education,
        "contract_type": contract_type,
        "posted_date": base_offer.get("posted_date"),
        "url": base_offer.get("url"),
        "source": "dreamjob",
        "scraped_at": datetime.now(),
    }


def scrape_list_page(page_num):
    """Scrape une page de liste et retourne les offres de base."""
    url = get_search_url(page_num)
    print(f"\n📄 Page liste {page_num} : {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        offers = parse_list_page(r.text)
        print(f"   ✅ {len(offers)} offres trouvées")
        return offers
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return []


def main():
    print("=" * 60)
    print("🚀 SCRAPER DREAMJOB.MA - Version 2 étapes")
    print(f"   Mot-clé : '{KEYWORD}' | Pages : {NB_PAGES}")
    print("=" * 60)

    # === Étape 1 : récupérer toutes les offres de toutes les pages ===
    all_base_offers = []
    for page in range(1, NB_PAGES + 1):
        offers = scrape_list_page(page)
        all_base_offers.extend(offers)
        time.sleep(DELAY)

    if not all_base_offers:
        print("\n❌ Aucune offre récupérée.")
        return

    print(f"\n📋 Total liste : {len(all_base_offers)} offres")
    print(f"\n🔍 Étape 2 : récupération des détails de chaque offre...")

    # === Étape 2 : visiter chaque offre pour les détails ===
    enriched_offers = []
    for i, base in enumerate(all_base_offers, 1):
        title_short = (base.get("title") or "?")[:60]
        print(f"   [{i}/{len(all_base_offers)}] {title_short}")
        full_desc = fetch_offer_details(base["url"]) if base.get("url") else ""
        record = build_offer_record(base, full_desc)
        enriched_offers.append(record)
        time.sleep(DELAY)

    df = pd.DataFrame(enriched_offers)

    # === Récapitulatif ===
    print(f"\n📊 RÉCAPITULATIF")
    print(f"   • Total offres        : {len(df)}")
    print(f"   • Avec entreprise     : {df['company'].notna().sum()}")
    print(f"   • Avec localisation   : {df['location'].notna().sum()}")
    print(f"   • Avec fonction       : {df['function'].notna().sum()}")
    print(f"   • Avec contrat        : {df['contract_type'].notna().sum()}")
    print(f"   • Avec niveau étude   : {df['education'].notna().sum()}")
    print(f"   • Avec expérience     : {df['experience'].notna().sum()}")
    print(f"   • Description >100 c. : {df['description'].apply(lambda x: len(x) > 100 if x else False).sum()}")

    # === Insertion en base ===
    df.to_sql(
        "dreamjob_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"\n✅ {len(df)} offres insérées dans bronze.dreamjob_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()