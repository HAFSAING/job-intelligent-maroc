import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from config import engine

KEYWORDS = [
    "data engineer",
    "data scientist",
    "data analyst",
    "business intelligence",
    "machine learning",
]
LOCATION = "Morocco"
NB_PAGES = 3  # 3 pages × 25 offres = ~75 offres par mot-clé

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def get_offer_description(url):
    """Récupère la description complète de l'offre via la page publique."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        desc = soup.find("div", class_="show-more-less-html__markup")
        return desc.get_text(separator=" ", strip=True) if desc else ""
    except Exception as e:
        print(f"   ⚠️  Erreur description : {e}")
        return ""


def scrape_keyword_page(keyword, start):
    """Scrape une page (25 offres) pour un mot-clé via l'endpoint public."""
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={keyword.replace(' ', '%20')}"
        f"&location={LOCATION}"
        f"&start={start}"
    )
    print(f"   📄 start={start} → {url[:90]}...")

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"   ⚠️  HTTP {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "lxml")
        cards = soup.find_all("div", class_="base-card")
        return cards
    except Exception as e:
        print(f"   ⚠️  Erreur : {e}")
        return []


def parse_card(card, keyword):
    """Extrait les infos d'une carte d'offre."""
    try:
        # Titre
        title_tag = card.find("h3", class_="base-search-card__title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Entreprise
        company_tag = card.find("h4", class_="base-search-card__subtitle")
        company = company_tag.get_text(strip=True) if company_tag else None

        # Localisation
        loc_tag = card.find("span", class_="job-search-card__location")
        location = loc_tag.get_text(strip=True) if loc_tag else None

        # URL offre
        link_tag = card.find("a", class_="base-card__full-link")
        offer_url = link_tag["href"].split("?")[0] if link_tag and link_tag.has_attr("href") else None

        # Date publication
        time_tag = card.find("time", class_="job-search-card__listdate")
        if not time_tag:
            time_tag = card.find("time", class_="job-search-card__listdate--new")
        posted_date = time_tag.get("datetime") if time_tag else None

        return {
            "title": title,
            "company": company,
            "location": location,
            "url": offer_url,
            "posted_date": posted_date,
            "keyword": keyword,
        }
    except Exception as e:
        print(f"   ⚠️  Erreur parsing : {e}")
        return None


def scrape_keyword(keyword):
    """Scrape NB_PAGES pour un mot-clé."""
    print(f"\n🔍 Recherche : '{keyword}'")
    all_cards = []
    for page in range(NB_PAGES):
        start = page * 25
        cards = scrape_keyword_page(keyword, start)
        if not cards:
            break
        all_cards.extend(cards)
        time.sleep(2)
    print(f"   ✅ {len(all_cards)} offres trouvées pour '{keyword}'")
    return all_cards


def main():
    print("=" * 60)
    print("🚀 SCRAPER LINKEDIN - Multi-keywords")
    print(f"   Mots-clés : {len(KEYWORDS)} | Pages/mot-clé : {NB_PAGES}")
    print("=" * 60)

    all_offers = []
    seen_urls = set()

    for keyword in KEYWORDS:
        cards = scrape_keyword(keyword)
        for card in cards:
            parsed = parse_card(card, keyword)
            if parsed and parsed["url"] and parsed["url"] not in seen_urls:
                seen_urls.add(parsed["url"])
                all_offers.append(parsed)

    print(f"\n📊 Total uniques (avant description) : {len(all_offers)}")

    # Récupérer les descriptions complètes
    print("\n⬇️  Récupération des descriptions complètes...")
    final_data = []
    for i, offer in enumerate(all_offers, 1):
        print(f"   [{i}/{len(all_offers)}] {offer['title'][:60] if offer['title'] else 'sans titre'}...")
        description = get_offer_description(offer["url"])
        time.sleep(0.5)

        final_data.append({
            "job_title": offer["title"],
            "company": offer["company"],
            "location": offer["location"],
            "summary": None,
            "description": description,
            "sector": None,
            "function": None,
            "experience": None,
            "education": None,
            "contract_type": None,
            "posted_date": offer["posted_date"],
            "url": offer["url"],
            "source": "linkedin",
            "search_keyword": offer["keyword"],
            "scraped_at": datetime.now()
        })

    if not final_data:
        print("\n❌ Aucune offre récupérée.")
        return

    df = pd.DataFrame(final_data)
    print(f"\n📊 Total final : {len(df)} offres")

    df.to_sql(
        "linkedin_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"✅ {len(df)} offres insérées dans bronze.linkedin_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()