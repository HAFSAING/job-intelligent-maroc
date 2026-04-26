"""
Scraper Indeed.ma - Version multi-keywords
- Scrape 1 page par mot-clé (Indeed bloque les pages suivantes sans login)
- Plusieurs mots-clés pour avoir plus d'offres uniques
- Insère les données brutes dans bronze.indeed_raw
"""

import time
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from config import engine

# Liste des mots-clés à chercher (1 page chacun)
KEYWORDS = [
    "data engineer",
    "data scientist",
    "data analyst",
    "business intelligence",
    "machine learning",
    "big data",
    "power bi",
]


def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options, version_main=147)
    return driver


def get_offer_description(driver, offer_url):
    try:
        driver.get(offer_url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "lxml")
        desc = soup.find("div", id="jobDescriptionText")
        return desc.get_text(separator=" ", strip=True) if desc else ""
    except Exception as e:
        print(f"   ⚠️  Erreur description : {e}")
        return ""


def scrape_keyword(driver, keyword):
    """Scrape la première page de résultats pour un mot-clé."""
    url = f"https://ma.indeed.com/jobs?q={keyword.replace(' ', '+')}&start=0"
    print(f"\n🔍 Recherche : '{keyword}'")
    print(f"   URL : {url}")

    driver.get(url)
    time.sleep(5)

    if "Just a moment" in driver.title or "Cloudflare" in driver.page_source[:2000]:
        print("   ⏳ Cloudflare détecté, attente 10s...")
        time.sleep(10)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.css-1ac2h1w"))
        )
    except Exception:
        print("   ⚠️  Liste non trouvée. Page bloquée ou vide.")
        return []

    soup = BeautifulSoup(driver.page_source, "lxml")
    cards = soup.find_all("li", class_="css-1ac2h1w")
    print(f"   ✅ {len(cards)} offres trouvées")

    results = []
    for i, card in enumerate(cards, 1):
        try:
            title_link = card.find("a", attrs={"data-jk": True})
            if not title_link:
                continue
            data_jk = title_link.get("data-jk")
            title_span = card.find("span", id=lambda x: x and x.startswith("jobTitle"))
            title = title_span.get_text(strip=True) if title_span else None
            offer_url = f"https://ma.indeed.com/viewjob?jk={data_jk}"

            company_tag = card.find("span", attrs={"data-testid": "company-name"})
            company = company_tag.get_text(strip=True) if company_tag else None

            location_tag = card.find("div", attrs={"data-testid": "text-location"})
            location = location_tag.get_text(strip=True) if location_tag else None

            contract_type = None
            meta = card.find("div", class_="jobMetaDataGroup")
            if meta:
                contract_type = meta.get_text(separator=" | ", strip=True)

            print(f"   [{i}/{len(cards)}] {title[:60] if title else 'sans titre'}...")
            description = get_offer_description(driver, offer_url)

            results.append({
                "job_title": title,
                "company": company,
                "location": location,
                "summary": None,
                "description": description,
                "sector": None,
                "function": None,
                "experience": None,
                "education": None,
                "contract_type": contract_type,
                "posted_date": None,
                "url": offer_url,
                "source": "indeed",
                "search_keyword": keyword,
                "scraped_at": datetime.now()
            })

        except Exception as e:
            print(f"   ⚠️  Erreur sur une offre : {e}")
            continue

    return results


def main():
    print("=" * 60)
    print("🚀 SCRAPER INDEED.MA - Multi-keywords")
    print(f"   Mots-clés : {len(KEYWORDS)}")
    print("=" * 60)

    driver = init_driver()
    all_offers = []

    try:
        for keyword in KEYWORDS:
            offers = scrape_keyword(driver, keyword)
            all_offers.extend(offers)
            time.sleep(3)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if not all_offers:
        print("\n❌ Aucune offre récupérée.")
        return

    df = pd.DataFrame(all_offers)
    print(f"\n📊 Total scrapé (avec doublons) : {len(df)} offres")

    # Suppression des doublons par URL
    df_unique = df.drop_duplicates(subset=["url"], keep="first")
    print(f"📊 Total unique (par URL) : {len(df_unique)} offres")

    df_unique.to_sql(
        "indeed_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"✅ {len(df_unique)} offres insérées dans bronze.indeed_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()