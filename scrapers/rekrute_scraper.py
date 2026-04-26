"""
Scraper ReKrute.com
- Scrape 5 pages d'offres pour le mot-clé 'data'
- Récupère la description complète de chaque offre
- Insère les données brutes dans bronze.rekrute_raw
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
                  "Chrome/120.0.0.0 Safari/537.36"
}


def get_offer_description(url):
    """Récupère la description complète sur la page de détail d'une offre."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        # La description est dans un div qui contient le texte du poste
        desc_block = soup.find("div", class_="content")
        if desc_block:
            return desc_block.get_text(separator=" ", strip=True)
        return ""
    except Exception as e:
        print(f"   ⚠️  Erreur description : {e}")
        return ""


def scrape_page(page_num):
    """Scrape une page de résultats ReKrute."""
    url = f"{BASE_URL}?keyword={KEYWORD}&p={page_num}"
    print(f"\n📄 Page {page_num} : {url}")

    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "lxml")

    # Récupérer la liste des offres : <ul id="post-data"> > <li class="post-id">
    job_list = soup.find("ul", id="post-data")
    if not job_list:
        print("   ❌ Aucune liste d'offres trouvée")
        return []

    offers = job_list.find_all("li", class_="post-id")
    print(f"   ✅ {len(offers)} offres trouvées sur cette page")

    results = []
    for i, offer in enumerate(offers, 1):
        try:
            # Titre + URL
            title_tag = offer.find("h2")
            title = title_tag.get_text(strip=True) if title_tag else None
            link_tag = title_tag.find("a") if title_tag else None
            offer_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
            if offer_url and not offer_url.startswith("http"):
                offer_url = "https://www.rekrute.com" + offer_url

            # Résumé (premier div info)
            info_div = offer.find("div", class_="info")
            summary = info_div.get_text(separator=" ", strip=True) if info_div else None

            # Date de publication
            date_tag = offer.find("em", class_="date")
            posted_date = date_tag.get_text(strip=True) if date_tag else None

            # Détails (secteur, fonction, expérience, contrat...) sont dans des <li>
            details = {}
            for li in offer.find_all("li"):
                txt = li.get_text(separator=":", strip=True)
                if "Secteur" in txt:
                    details["sector"] = txt.replace("Secteur d'activité :", "").strip()
                elif "Fonction" in txt:
                    details["function"] = txt.replace("Fonction :", "").strip()
                elif "Expérience" in txt:
                    details["experience"] = txt.replace("Expérience requise :", "").strip()
                elif "Niveau d'étude" in txt:
                    details["education"] = txt.replace("Niveau d'étude demandé :", "").strip()
                elif "Type de contrat" in txt:
                    details["contract_type"] = txt.replace("Type de contrat proposé :", "").strip()

            # Description complète (page détail)
            description = ""
            if offer_url:
                print(f"   [{i}/{len(offers)}] {title[:60] if title else 'sans titre'}...")
                description = get_offer_description(offer_url)
                time.sleep(0.5)  # politesse

            # Extraire la ville depuis le titre (souvent "... | Ville (Maroc)")
            location = None
            if title and "|" in title:
                parts = title.split("|")
                if len(parts) > 1:
                    location = parts[-1].strip()

            results.append({
                "job_title": title,
                "company": None,  # ReKrute n'affiche pas toujours l'entreprise
                "location": location,
                "summary": summary,
                "description": description,
                "sector": details.get("sector"),
                "function": details.get("function"),
                "experience": details.get("experience"),
                "education": details.get("education"),
                "contract_type": details.get("contract_type"),
                "posted_date": posted_date,
                "url": offer_url,
                "source": "rekrute",
                "scraped_at": datetime.now()
            })

        except Exception as e:
            print(f"   ⚠️  Erreur sur une offre : {e}")
            continue

    return results


def main():
    print("=" * 60)
    print("🚀 SCRAPER REKRUTE - Démarrage")
    print(f"   Mot-clé : '{KEYWORD}' | Pages : {NB_PAGES}")
    print("=" * 60)

    all_offers = []
    for page in range(1, NB_PAGES + 1):
        offers = scrape_page(page)
        all_offers.extend(offers)
        time.sleep(1)  # politesse entre les pages

    if not all_offers:
        print("\n❌ Aucune offre récupérée. Vérifie la structure du site.")
        return

    # Convertir en DataFrame
    df = pd.DataFrame(all_offers)
    print(f"\n📊 Total scrapé : {len(df)} offres")

    # Insertion dans BRONZE
    df.to_sql(
        "rekrute_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"✅ {len(df)} offres insérées dans bronze.rekrute_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()