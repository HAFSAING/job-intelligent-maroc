"""
Scraper LinkedIn - Version définitive (endpoint guest)
- Liste : seeMoreJobPostings
- Détails : jobPosting/{job_id}  ← contient le bloc criteria
- Extrait : description + Niveau hiérarchique + Type d'emploi + Fonction + Secteurs
- Fallback regex pour education/experience
"""

import re
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
NB_PAGES = 3

LIST_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={kw}&location={loc}&start={start}"
)
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

NIVEAUX_ETUDES = [
    ("Doctorat",  r"\bDoctorat\b|\bPhD\b|\bDoctorate\b"),
    ("Bac+5",     r"\bBac\s*\+\s*5\b|\bMaster['s]?\b|\bing[ée]nieur\b|\bengineering\s+degree\b|\bMSc\b"),
    ("Bac+4",     r"\bBac\s*\+\s*4\b"),
    ("Bac+3",     r"\bBac\s*\+\s*3\b|\bLicence\b|\bBachelor['s]?\b|\bBSc\b"),
    ("Bac+2",     r"\bBac\s*\+\s*2\b|\bBTS\b|\bDUT\b|\bAssociate\s+degree\b"),
]


def clean_text(s):
    return re.sub(r"\s+", " ", s).strip() if s else None


def extract_job_id(url):
    if not url:
        return None
    m = re.search(r"-(\d{8,})/?(?:\?|$)", url)
    return m.group(1) if m else None


def extract_education(text):
    if not text:
        return None
    for label, pattern in NIVEAUX_ETUDES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def extract_experience_years(text):
    if not text:
        return None
    patterns = [
        r"(\d+)\s*(?:to|à|-|–)\s*(\d+)\s*(?:years?|ans?)\s*(?:of\s+)?(?:experience|d['e ]+exp[ée]rience)",
        r"(?:minimum\s+|at\s+least\s+)?(\d+)\+?\s*(?:years?|ans?)\s*(?:of\s+)?(?:experience|d['e ]+exp[ée]rience)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g]
            if len(groups) == 2:
                return f"{groups[0]}-{groups[1]} ans"
            return f"{groups[0]} ans"
    return None


def get_offer_details(offer_url):
    details = {
        "description": "",
        "experience_level": None,
        "contract_type": None,
        "function": None,
        "sector": None,
        "job_id": None,
    }

    job_id = extract_job_id(offer_url)
    if not job_id:
        return details
    details["job_id"] = job_id

    try:
        r = requests.get(DETAIL_URL.format(job_id=job_id), headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return details
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")

        desc = soup.find("div", class_="show-more-less-html__markup")
        if desc:
            details["description"] = clean_text(desc.get_text(separator=" "))

        criteria_list = soup.find("ul", class_="description__job-criteria-list")
        if criteria_list:
            for item in criteria_list.find_all("li", class_="description__job-criteria-item"):
                header = item.find("h3", class_="description__job-criteria-subheader")
                value = item.find("span", class_="description__job-criteria-text")
                if not header or not value:
                    continue
                h_text = header.get_text(strip=True).lower()
                v_text = clean_text(value.get_text())

                if "niveau" in h_text or "seniority" in h_text:
                    details["experience_level"] = v_text
                elif "type" in h_text or "employment" in h_text:
                    details["contract_type"] = v_text
                elif "fonction" in h_text or "function" in h_text:
                    details["function"] = v_text
                elif "secteur" in h_text or "industries" in h_text or "industrie" in h_text:
                    details["sector"] = v_text
    except Exception as e:
        print(f"      ⚠️  Erreur détails : {e}")

    return details


def scrape_keyword_page(keyword, start):
    url = LIST_URL.format(kw=keyword.replace(" ", "%20"), loc=LOCATION, start=start)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"   ⚠️  HTTP {r.status_code}")
            return []
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        return soup.find_all("div", class_="base-card")
    except Exception as e:
        print(f"   ⚠️  Erreur : {e}")
        return []


def parse_card(card, keyword):
    try:
        title_tag = card.find("h3", class_="base-search-card__title")
        title = clean_text(title_tag.get_text()) if title_tag else None

        company_tag = card.find("h4", class_="base-search-card__subtitle")
        company = clean_text(company_tag.get_text()) if company_tag else None

        loc_tag = card.find("span", class_="job-search-card__location")
        location = clean_text(loc_tag.get_text()) if loc_tag else None

        link_tag = card.find("a", class_="base-card__full-link")
        offer_url = link_tag["href"].split("?")[0] if link_tag and link_tag.has_attr("href") else None

        time_tag = (card.find("time", class_="job-search-card__listdate")
                    or card.find("time", class_="job-search-card__listdate--new"))
        posted_date = time_tag.get("datetime") if time_tag else None

        return {
            "title": title, "company": company, "location": location,
            "url": offer_url, "posted_date": posted_date, "keyword": keyword,
        }
    except Exception:
        return None


def scrape_keyword(keyword):
    print(f"\n🔍 Recherche : '{keyword}'")
    all_cards = []
    for page in range(NB_PAGES):
        start = page * 25
        cards = scrape_keyword_page(keyword, start)
        if not cards:
            break
        all_cards.extend(cards)
        time.sleep(2)
    print(f"   ✅ {len(all_cards)} offres trouvées")
    return all_cards


def main():
    print("=" * 60)
    print("🚀 SCRAPER LINKEDIN - Endpoint guest")
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

    print(f"\n📊 Total uniques : {len(all_offers)}")
    if not all_offers:
        print("\n❌ Aucune offre récupérée.")
        return

    print(f"\n⬇️  Enrichissement des {len(all_offers)} offres...")
    final_data = []
    for i, offer in enumerate(all_offers, 1):
        title_short = (offer["title"] or "?")[:50]
        details = get_offer_details(offer["url"])

        education = extract_education(details["description"])
        experience_fallback = extract_experience_years(details["description"])

        tags = []
        if details["function"]: tags.append(f"F:{details['function'][:18]}")
        if details["contract_type"]: tags.append(f"C:{details['contract_type'][:12]}")
        if details["sector"]: tags.append(f"S:{details['sector'][:18]}")
        tag_str = " | ".join(tags) if tags else "⚪"
        print(f"   [{i}/{len(all_offers)}] {title_short} → {tag_str}")

        final_data.append({
            "job_title": offer["title"],
            "company": offer["company"],
            "location": offer["location"],
            "summary": None,
            "description": details["description"][:5000] if details["description"] else "",
            "sector": details["sector"],
            "function": details["function"],
            "experience": details["experience_level"] or experience_fallback,
            "education": education,
            "contract_type": details["contract_type"],
            "posted_date": offer["posted_date"],
            "url": offer["url"],
            "job_id": details["job_id"],
            "source": "linkedin",
            "search_keyword": offer["keyword"],
            "scraped_at": datetime.now()
        })
        time.sleep(0.5)

    df = pd.DataFrame(final_data)
    print(f"\n📊 RÉCAPITULATIF")
    print(f"   • Total              : {len(df)}")
    print(f"   • Avec entreprise    : {df['company'].notna().sum()}")
    print(f"   • Avec localisation  : {df['location'].notna().sum()}")
    print(f"   • Avec secteur       : {df['sector'].notna().sum()}")
    print(f"   • Avec fonction      : {df['function'].notna().sum()}")
    print(f"   • Avec expérience    : {df['experience'].notna().sum()}")
    print(f"   • Avec niveau étude  : {df['education'].notna().sum()}")
    print(f"   • Avec contrat       : {df['contract_type'].notna().sum()}")

    df.to_sql(
        "linkedin_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"\n✅ {len(df)} offres insérées dans bronze.linkedin_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()