"""
Scraper Indeed.ma - Version multi-keywords + extraction enrichie
- Scrape 1 page par mot-clé
- Extraction par regex de function/education/experience/sector
  depuis la description (FR + EN)
- Insère dans bronze.indeed_raw
"""

import re
import time
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from config import engine

KEYWORDS = [
    "data engineer",
    "data scientist",
    "data analyst",
    "business intelligence",
    "machine learning",
    "big data",
    "power bi",
]

# ==== Patterns FR + EN ====
CONTRATS = {
    "CDI": r"\bCDI\b|\bpermanent\b|\bfull[- ]time\b",
    "CDD": r"\bCDD\b|\bfixed[- ]term\b",
    "Stage": r"\bstage(?:s)?\b|\binternship\b|\bintern\b",
    "Freelance": r"\bfreelance\b|\bcontractor\b",
    "Alternance": r"\balternance\b|\bapprenticeship\b",
    "Intérim": r"\bint[ée]rim\b|\btemporary\b",
    "PFE": r"\bPFE\b",
}

NIVEAUX_ETUDES = [
    ("Doctorat",  r"\bDoctorat\b|\bPhD\b|\bDoctorate\b"),
    ("Bac+5",     r"\bBac\s*\+\s*5\b|\bMaster['s]?\b|\bing[ée]nieur\b|\bengineering\s+degree\b|\bMSc\b"),
    ("Bac+4",     r"\bBac\s*\+\s*4\b"),
    ("Bac+3",     r"\bBac\s*\+\s*3\b|\bLicence\b|\bBachelor['s]?\b|\bBSc\b"),
    ("Bac+2",     r"\bBac\s*\+\s*2\b|\bBTS\b|\bDUT\b|\bAssociate\s+degree\b"),
]

METIERS = [
    "Data Scientist", "Data Engineer", "Data Analyst", "Data Manager",
    "Machine Learning Engineer", "ML Engineer", "BI Developer",
    "Business Intelligence", "Big Data Engineer", "DevOps", "MLOps",
    "Data Architect", "Architecte Data", "Chef de projet Data",
    "Power BI Developer", "ETL Developer",
]

SECTEURS = {
    "Banque/Finance": r"\bbanqu(?:e|aire)\b|\bbank(?:ing)?\b|\bfinanc(?:e|i[èe]re?|ial)\b|\binsurance\b|\bassurance\b",
    "Telecom": r"\bt[ée]l[ée]com(?:munications?)?\b|\btelecom\b",
    "Industrie/Manufacturing": r"\bindustri(?:e|el|al)\b|\bmanufactur(?:e|ing)\b|\baeronaut\w*\b|\bautomobile\b",
    "Conseil/Consulting": r"\bconsulting\b|\bconseil\b|\bcabinet\b",
    "Tech/IT": r"\bSaaS\b|\bcloud\b|\bsoftware\b|\bIT\s+services\b|\bdigital\b",
    "Santé": r"\bsant[ée]\b|\bhealthcare\b|\bm[ée]dical\b|\bpharmaceutical\b",
    "E-commerce/Retail": r"\be[- ]commerce\b|\bretail\b|\bgrande\s+distribution\b",
    "Énergie": r"\b[ée]nergie\b|\benergy\b|\boil\s+and\s+gas\b|\bp[ée]trole\b",
    "Public/Gouvernement": r"\bsecteur\s+public\b|\bgovernment\b|\bpublic\s+sector\b",
    "Éducation": r"\b[ée]ducation\b|\benseignement\b|\buniversit[ée]\b|\bschool\b",
}


def clean_text(s):
    return re.sub(r"\s+", " ", s).strip() if s else None


def extract_contract_type(text):
    if not text:
        return None
    found = []
    for label, pattern in CONTRATS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(label)
    return " - ".join(found) if found else None


def extract_education(text):
    if not text:
        return None
    for label, pattern in NIVEAUX_ETUDES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def extract_experience(text):
    if not text:
        return None
    patterns = [
        r"(\d+)\s*(?:to|à|-|–)\s*(\d+)\s*(?:years?|ans?)\s*(?:of\s+)?(?:experience|d['e ]+exp[ée]rience)",
        r"(?:minimum\s+|at\s+least\s+)?(\d+)\+?\s*(?:years?|ans?)\s*(?:of\s+)?(?:experience|d['e ]+exp[ée]rience)",
        r"(?:experience|exp[ée]rience)\s*(?:de|of|:)?\s*(\d+)\+?\s*(?:years?|ans?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g]
            if len(groups) == 2:
                return f"{groups[0]}-{groups[1]} ans"
            return f"{groups[0]} ans"
    if re.search(r"\bd[ée]butant\b|\bjunior\b|\bsans\s+exp[ée]rience\b|\bentry[- ]level\b", text, flags=re.IGNORECASE):
        return "Débutant / Junior"
    if re.search(r"\bsenior\b|\bconfirm[ée]\b|\blead\b|\bexperienced\b", text, flags=re.IGNORECASE):
        return "Senior / Confirmé"
    return None


def extract_function(title, text):
    sources = " ".join([t for t in [title, text] if t])
    found = []
    for m in METIERS:
        if re.search(rf"\b{re.escape(m)}\b", sources, flags=re.IGNORECASE):
            found.append(m)
    return " - ".join(found[:3]) if found else None


def extract_sector(text):
    if not text:
        return None
    found = []
    for label, pattern in SECTEURS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(label)
    return " - ".join(found[:2]) if found else None


# ============================================================
#                    SCRAPING SELENIUM
# ============================================================

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
            title = clean_text(title_span.get_text()) if title_span else None
            offer_url = f"https://ma.indeed.com/viewjob?jk={data_jk}"

            company_tag = card.find("span", attrs={"data-testid": "company-name"})
            company = clean_text(company_tag.get_text()) if company_tag else None

            location_tag = card.find("div", attrs={"data-testid": "text-location"})
            location = clean_text(location_tag.get_text()) if location_tag else None

            contract_card = None
            meta = card.find("div", class_="jobMetaDataGroup")
            if meta:
                contract_card = clean_text(meta.get_text(separator=" | "))

            print(f"   [{i}/{len(cards)}] {title[:60] if title else 'sans titre'}...")
            description = get_offer_description(driver, offer_url)

            # === EXTRACTION ENRICHIE depuis description ===
            contract_type = extract_contract_type(description) or contract_card
            education = extract_education(description)
            experience = extract_experience(description)
            function = extract_function(title, description)
            sector = extract_sector(description)

            results.append({
                "job_title": title,
                "company": company,
                "location": location,
                "summary": None,
                "description": description[:5000] if description else "",
                "sector": sector,
                "function": function,
                "experience": experience,
                "education": education,
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
    print("🚀 SCRAPER INDEED.MA - Multi-keywords + enrichi")
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
    print(f"\n📊 Total scrapé (avec doublons) : {len(df)}")

    df_unique = df.drop_duplicates(subset=["url"], keep="first")
    print(f"📊 Total unique (par URL) : {len(df_unique)}")

    print(f"\n📊 RÉCAPITULATIF")
    print(f"   • Avec entreprise   : {df_unique['company'].notna().sum()}")
    print(f"   • Avec localisation : {df_unique['location'].notna().sum()}")
    print(f"   • Avec fonction     : {df_unique['function'].notna().sum()}")
    print(f"   • Avec contrat      : {df_unique['contract_type'].notna().sum()}")
    print(f"   • Avec niveau étude : {df_unique['education'].notna().sum()}")
    print(f"   • Avec expérience   : {df_unique['experience'].notna().sum()}")
    print(f"   • Avec secteur      : {df_unique['sector'].notna().sum()}")

    df_unique.to_sql(
        "indeed_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )
    print(f"\n✅ {len(df_unique)} offres insérées dans bronze.indeed_raw")
    print("=" * 60)


if __name__ == "__main__":
    main()