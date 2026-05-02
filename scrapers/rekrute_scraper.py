"""
Scraper ReKrute.com - Version finale
- Toutes les infos sont sur la page de liste
- Extraction du nom d'entreprise via le logo (alt/title)
- Encodage UTF-8 forcé
- Insère dans bronze.rekrute_raw
"""

import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from config import engine

BASE_URL = "https://www.rekrute.com/offres.html"
KEYWORD = "data"
NB_PAGES = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def extract_field_from_li(li, label):
    """
    Extrait la valeur d'un <li> contenant un label texte + des <a>.
    Exemple : <li>"Secteur d'activité : "<a>Agence pub</a> - <a>Conseil</a></li>
    → renvoie "Agence pub - Conseil"
    """
    text = li.get_text(separator=" ", strip=True)
    if label in text:
        values = [a.get_text(strip=True) for a in li.find_all("a")]
        if values:
            return " - ".join(values)
        return text.replace(label, "").strip(" :-")
    return None


def parse_offer(li_offer):
    """Parse un <li class='post-id'> et retourne un dict avec toutes les infos."""

    # === ENTREPRISE (depuis le logo alt/title) ===
    company = None
    logo = li_offer.find("img", class_="photo")
    if logo:
        if logo.has_attr("alt") and logo["alt"].strip():
            company = logo["alt"].strip()
        elif logo.has_attr("title") and logo["title"].strip():
            company = logo["title"].strip()

    # === TITRE + URL ===
    title_tag = li_offer.find("a", class_="titreJob")
    title = title_tag.get_text(strip=True) if title_tag else None

    offer_url = None
    if title_tag and title_tag.has_attr("href"):
        href = title_tag["href"]
        offer_url = href if href.startswith("http") else "https://www.rekrute.com" + href

    # === LOCALISATION (extraite du titre, format "... | Ville (Maroc)") ===
    location = None
    if title and "|" in title:
        location = title.split("|")[-1].strip()
        title = title.split("|")[0].strip()

    # === DESCRIPTION & SUMMARY (depuis les <div class="info">) ===
    info_divs = li_offer.find_all("div", class_="info")
    description = ""
    summary = ""

    if len(info_divs) >= 1:
        # 1er div info = résumé court (mots-clés correspondants à la recherche)
        spans = info_divs[0].find_all("span")
        if spans:
            summary = " ".join(s.get_text(strip=True) for s in spans)

    if len(info_divs) >= 2:
        # 2ème div info = description complète du poste
        spans = info_divs[1].find_all("span")
        if spans:
            description = spans[-1].get_text(separator=" ", strip=True)

    # === DATE DE PUBLICATION ===
    date_tag = li_offer.find("em", class_="date")
    posted_date = None
    if date_tag:
        date_spans = date_tag.find_all("span")
        if len(date_spans) >= 2:
            posted_date = f"du {date_spans[0].get_text(strip=True)} au {date_spans[1].get_text(strip=True)}"

    # === MÉTADONNÉES (Secteur, Fonction, Expérience, Niveau, Contrat) ===
    sector = function = experience = education = contract_type = None

    for ul in li_offer.find_all("ul"):
        for li in ul.find_all("li"):
            txt = li.get_text(separator=" ", strip=True)
            if "Secteur d'activité" in txt:
                sector = extract_field_from_li(li, "Secteur d'activité :")
            elif "Fonction" in txt and "Fonctions" not in txt:
                function = extract_field_from_li(li, "Fonction :")
            elif "Expérience requise" in txt:
                experience = extract_field_from_li(li, "Expérience requise :")
            elif "Niveau d'étude" in txt:
                education = extract_field_from_li(li, "Niveau d'étude demandé :")
            elif "Type de contrat" in txt:
                a_tags = li.find_all("a")
                ct = a_tags[0].get_text(strip=True) if a_tags else None
                if "Télétravail" in txt:
                    if "Hybride" in txt:
                        ct = f"{ct} - Hybride" if ct else "Hybride"
                    elif "Oui" in txt:
                        ct = f"{ct} - Télétravail Oui" if ct else "Télétravail Oui"
                    elif "Non" in txt:
                        ct = f"{ct} - Télétravail Non" if ct else "Télétravail Non"
                contract_type = ct

    return {
        "job_title": title,
        "company": company,
        "location": location,
        "summary": summary,
        "description": description,
        "sector": sector,
        "function": function,
        "experience": experience,
        "education": education,
        "contract_type": contract_type,
        "posted_date": posted_date,
        "url": offer_url,
        "source": "rekrute",
        "scraped_at": datetime.now()
    }


def scrape_page(page_num):
    url = f"{BASE_URL}?keyword={KEYWORD}&p={page_num}"
    print(f"\n📄 Page {page_num} : {url}")

    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"  # Force UTF-8 pour les accents

    soup = BeautifulSoup(r.text, "lxml")

    job_list = soup.find("ul", id="post-data")
    if not job_list:
        print("   ❌ Aucune liste trouvée")
        return []

    offers = job_list.find_all("li", class_="post-id")
    print(f"   ✅ {len(offers)} offres trouvées")

    results = []
    for i, offer in enumerate(offers, 1):
        try:
            data = parse_offer(offer)
            company_str = data['company'] or '???'
            title_str = data['job_title'][:50] if data['job_title'] else 'sans titre'
            print(f"   [{i}/{len(offers)}] [{company_str}] {title_str}")
            results.append(data)
        except Exception as e:
            print(f"   ⚠️  Erreur sur une offre : {e}")
            continue

    return results


def main():
    print("=" * 60)
    print("🚀 SCRAPER REKRUTE - Version finale")
    print(f"   Mot-clé : '{KEYWORD}' | Pages : {NB_PAGES}")
    print("=" * 60)

    all_offers = []
    for page in range(1, NB_PAGES + 1):
        offers = scrape_page(page)
        all_offers.extend(offers)
        time.sleep(1)

    if not all_offers:
        print("\n❌ Aucune offre récupérée.")
        return

    df = pd.DataFrame(all_offers)
    print(f"\n📊 RÉCAPITULATIF")
    print(f"   • Total offres scrapées  : {len(df)}")
    print(f"   • Avec entreprise        : {df['company'].notna().sum()}")
    print(f"   • Avec localisation      : {df['location'].notna().sum()}")
    print(f"   • Avec description (>50) : {df['description'].apply(lambda x: len(x) > 50 if x else False).sum()}")
    print(f"   • Avec secteur           : {df['sector'].notna().sum()}")
    print(f"   • Avec contrat           : {df['contract_type'].notna().sum()}")

    df.to_sql(
        "rekrute_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"\n✅ {len(df)} offres insérées dans bronze.rekrute_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()