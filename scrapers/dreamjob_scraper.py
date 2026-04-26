"""
Scraper Dreamjob.ma
- Scrape 5 pages d'offres pour le mot-clé 'data'
- Récupère la description complète de chaque offre
- Insère les données brutes dans bronze.dreamjob_raw
"""

import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from config import engine

KEYWORD = "data"
NB_PAGES = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def get_offer_details(url):
    """Récupère la description complète + métadonnées sur la page de détail."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        # Le contenu principal de l'article
        content = soup.find("div", class_="content-inner")
        description = content.get_text(separator=" ", strip=True) if content else ""
        return description
    except Exception as e:
        print(f"   ⚠️  Erreur détail : {e}")
        return ""


def build_url(page_num):
    """Construit l'URL pour une page donnée."""
    if page_num == 1:
        return f"https://www.dreamjob.ma/?s={KEYWORD}"
    return f"https://www.dreamjob.ma/page/{page_num}/?s={KEYWORD}"


def scrape_page(page_num):
    """Scrape une page de résultats Dreamjob."""
    url = build_url(page_num)
    print(f"\n📄 Page {page_num} : {url}")

    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "lxml")

    # Toutes les offres : <article class="jeg_post ...">
    articles = soup.find_all("article", class_="jeg_post")
    print(f"   ✅ {len(articles)} offres trouvées sur cette page")

    results = []
    for i, article in enumerate(articles, 1):
        try:
            # Titre + URL (dans <h3 class="jeg_post_title">)
            title_tag = article.find("h3", class_="jeg_post_title")
            if not title_tag:
                continue
            link = title_tag.find("a")
            title = link.get_text(strip=True) if link else None
            offer_url = link["href"] if link and link.has_attr("href") else None

            # Date (dans <div class="jeg_meta_date">)
            date_div = article.find("div", class_="jeg_meta_date")
            posted_date = date_div.get_text(strip=True) if date_div else None

            # Résumé (dans <div class="jeg_post_excerpt"><p>)
            excerpt_div = article.find("div", class_="jeg_post_excerpt")
            summary = excerpt_div.get_text(separator=" ", strip=True) if excerpt_div else None

            # Récupération du détail complet
            description = ""
            if offer_url:
                print(f"   [{i}/{len(articles)}] {title[:70] if title else 'sans titre'}...")
                description = get_offer_details(offer_url)
                time.sleep(0.5)

            results.append({
                "job_title": title,
                "company": None,        # à extraire de la description en silver
                "location": None,       # à extraire de la description en silver
                "summary": summary,
                "description": description,
                "sector": None,
                "function": None,
                "experience": None,
                "education": None,
                "contract_type": None,
                "posted_date": posted_date,
                "url": offer_url,
                "source": "dreamjob",
                "scraped_at": datetime.now()
            })

        except Exception as e:
            print(f"   ⚠️  Erreur sur une offre : {e}")
            continue

    return results


def main():
    print("=" * 60)
    print("🚀 SCRAPER DREAMJOB - Démarrage")
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
    print(f"\n📊 Total scrapé : {len(df)} offres")

    df.to_sql(
        "dreamjob_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"✅ {len(df)} offres insérées dans bronze.dreamjob_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()