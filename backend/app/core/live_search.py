import re
import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, parse_qs, unquote, quote_plus, urljoin
import httpx
from bs4 import BeautifulSoup
from .config import settings

logger = logging.getLogger("trucklead.live_search")

EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_REGEX = r"(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}"

DM_PATTERNS = [
    (r"(?:Owner|Founder|Co-Founder)\s*[:\-–]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "Owner"),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[,-–]\s*(?:Owner|Founder|Co-Founder)", "Owner"),
    (r"(?:President|CEO)\s*[:\-–]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "President"),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[,-–]\s*(?:President|CEO)", "President"),
    (r"(?:Fleet Manager|Fleet Director)\s*[:\-–]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "Fleet Manager"),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[,-–]\s*(?:Fleet Manager|Fleet Director)", "Fleet Manager"),
    (r"(?:Operations Manager|Director of Operations)\s*[:\-–]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "Operations Manager"),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[,-–]\s*(?:Operations Manager|Director of Operations)", "Operations Manager"),
    (r"(?:Dispatch Manager|Lead Dispatcher)\s*[:\-–]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "Dispatch Manager"),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[,-–]\s*(?:Dispatch Manager|Lead Dispatcher)", "Dispatch Manager"),
    (r"(?:Safety Director|Safety Manager)\s*[:\-–]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "Safety Director"),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[,-–]\s*(?:Safety Director|Safety Manager)", "Safety Director"),
]

NON_PERSON_WORDS = {
    "trucking", "transport", "freight", "logistics", "express", "carrier", "company",
    "services", "solutions", "dispatch", "customer", "support", "contact", "about",
    "careers", "driver", "recruiting", "home", "privacy", "policy", "terms", "admin"
}


class LiveSearchClient:
    """Robust live web search & crawling engine for real lead discovery and verification."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @classmethod
    async def search_web(cls, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Executes live web search via DuckDuckGo Lite with fallback support.
        Returns list of dicts: [{'title': str, 'url': str, 'snippet': str}].
        """
        results: List[Dict[str, str]] = []

        # 1. Check Serper API if configured
        if getattr(settings, "serper_api_key", None):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                        json={"q": query, "num": limit}
                    )
                    if r.status_code == 200:
                        data = r.json()
                        for item in data.get("organic", [])[:limit]:
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", "")
                            })
                        if results:
                            return results
            except Exception as e:
                logger.warning(f"Serper API search failed, falling back to DDG: {e}")

        # 2. Live DuckDuckGo Lite search (Fast, reliable, free, no API key required)
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=cls.DEFAULT_HEADERS) as client:
                r = await client.post("https://lite.duckduckgo.com/lite/", data={"q": query})
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    rows = soup.find_all("tr")
                    for tr in rows:
                        link = tr.select_one(".result-link")
                        snip = tr.select_one(".result-snippet")
                        if not link:
                            continue
                        raw_href = link.get("href", "")
                        if "/l/?uddg=" in raw_href:
                            parsed = urlparse(raw_href)
                            qs = parse_qs(parsed.query)
                            actual_url = qs.get("uddg", [raw_href])[0]
                        else:
                            actual_url = raw_href
                        actual_url = unquote(actual_url)

                        if actual_url.startswith("http"):
                            results.append({
                                "title": link.get_text().strip(),
                                "url": actual_url,
                                "snippet": snip.get_text().strip() if snip else ""
                            })
                            if len(results) >= limit:
                                break
        except Exception as e:
            logger.warning(f"DDG search error for query '{query}': {e}")

        return results

    @classmethod
    async def find_company_website(cls, company_name: str, city: str = "", state: str = "") -> Optional[str]:
        """
        Discovers the official corporate website for a trucking company or shipper.
        Filters out aggregators and search engines to identify the actual corporate domain.
        """
        aggregator_domains = {
            "duckduckgo.com", "google.com", "bing.com", "yahoo.com",
            "facebook.com", "instagram.com", "twitter.com", "x.com",
            "yellowpages.com", "yelp.com", "mapquest.com", "bbb.org",
            "wikipedia.org", "chamberofcommerce.com", "dnb.com", "manta.com"
        }

        query = f'"{company_name}" {city} {state} official website'
        items = await cls.search_web(query, limit=5)
        for item in items:
            url = item.get("url", "")
            try:
                parsed = urlparse(url)
                netloc = parsed.netloc.lower()
                if netloc.startswith("www."):
                    netloc = netloc[4:]
                if netloc and not any(agg in netloc for agg in aggregator_domains):
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    return base_url
            except Exception:
                continue

        # Fallback to direct search without quotes
        fallback_query = f"{company_name} {city} {state} trucking website"
        items = await cls.search_web(fallback_query, limit=4)
        for item in items:
            url = item.get("url", "")
            try:
                parsed = urlparse(url)
                netloc = parsed.netloc.lower()
                if netloc.startswith("www."):
                    netloc = netloc[4:]
                if netloc and not any(agg in netloc for agg in aggregator_domains):
                    return f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                continue

        return None

    @classmethod
    async def crawl_website_for_contacts(cls, website_url: str, max_pages: int = 3) -> Dict[str, Any]:
        """
        Asynchronously crawls the company website to extract genuine emails, phone numbers,
        decision-maker names, equipment capabilities, and active intent signals.
        """
        out: Dict[str, Any] = {
            "emails": set(),
            "phones": set(),
            "decision_makers": [],
            "equipment": set(),
            "intent_signals": [],
            "raw_text": ""
        }

        if not website_url or not website_url.startswith("http"):
            return {
                "emails": list(out["emails"]),
                "phones": list(out["phones"]),
                "decision_makers": out["decision_makers"],
                "equipment": list(out["equipment"]),
                "intent_signals": out["intent_signals"],
            }

        visited_urls: Set[str] = set()
        to_visit: List[str] = [website_url]

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=cls.DEFAULT_HEADERS) as client:
            pages_crawled = 0
            while to_visit and pages_crawled < max_pages:
                curr_url = to_visit.pop(0)
                if curr_url in visited_urls:
                    continue
                visited_urls.add(curr_url)

                try:
                    r = await client.get(curr_url)
                    if r.status_code != 200:
                        continue
                    pages_crawled += 1
                    html = r.text
                    soup = BeautifulSoup(html, "html.parser")

                    # Strip script and style
                    for script in soup(["script", "style", "noscript"]):
                        script.decompose()

                    page_text = soup.get_text(separator=" ", strip=True)
                    out["raw_text"] += " " + page_text

                    # 1. Extract Emails
                    found_emails = re.findall(EMAIL_REGEX, html) + re.findall(EMAIL_REGEX, page_text)
                    for em in found_emails:
                        em_clean = em.strip().lower()
                        if not any(ig in em_clean for ig in [".png", ".jpg", ".jpeg", ".svg", "example.com", "domain.com"]):
                            out["emails"].add(em_clean)

                    # 2. Extract Phones
                    found_phones = re.findall(PHONE_REGEX, page_text)
                    for ph in found_phones:
                        digits = re.sub(r"\D", "", ph)
                        if len(digits) == 10 or (len(digits) == 11 and digits.startswith("1")):
                            out["phones"].add(ph.strip())

                    # 3. Detect Equipment
                    text_lower = page_text.lower()
                    if "dry van" in text_lower or "53ft van" in text_lower or "53' van" in text_lower:
                        out["equipment"].add("Dry Van")
                    if "reefer" in text_lower or "refrigerated" in text_lower or "temperature control" in text_lower:
                        out["equipment"].add("Reefer")
                    if "flatbed" in text_lower or "step deck" in text_lower or "stepdeck" in text_lower:
                        out["equipment"].add("Flatbed")
                    if "drayage" in text_lower or "intermodal" in text_lower or "port container" in text_lower:
                        out["equipment"].add("Drayage")
                    if "dedicated" in text_lower or "dedicated fleet" in text_lower:
                        out["equipment"].add("Dedicated")
                    if "heavy haul" in text_lower or "oversized" in text_lower:
                        out["equipment"].add("Heavy Haul")

                    # 4. Extract Decision Makers via patterns
                    for pattern, title in DM_PATTERNS:
                        matches = re.finditer(pattern, page_text, re.IGNORECASE)
                        for m in matches:
                            candidate_name = m.group(1).strip()
                            name_words = candidate_name.split()
                            if 2 <= len(name_words) <= 3:
                                if not any(w.lower() in NON_PERSON_WORDS for w in name_words):
                                    # Ensure unique
                                    if not any(d["full_name"].lower() == candidate_name.lower() for d in out["decision_makers"]):
                                        out["decision_makers"].append({
                                            "full_name": candidate_name,
                                            "title": title,
                                            "confidence": 0.90,
                                            "source_url": curr_url
                                        })

                    # 5. Extract Intent Signals (Hiring / Expansion)
                    if any(k in text_lower for k in ["hiring dispatcher", "hiring dispatchers", "seeking dispatcher"]):
                        out["intent_signals"].append({
                            "signal_type": "HIRING_DISPATCH",
                            "title": "Actively Hiring Freight Dispatchers",
                            "description": "Company careers/contact page specifies active dispatcher hiring.",
                            "confidence": 0.95,
                            "source_url": curr_url
                        })
                    elif any(k in text_lower for k in ["now hiring drivers", "join our fleet", "driver recruiting", "driver application"]):
                        out["intent_signals"].append({
                            "signal_type": "FLEET_EXPANSION",
                            "title": "Active Driver & Fleet Expansion",
                            "description": "Company website indicates ongoing recruitment and fleet capacity growth.",
                            "confidence": 0.85,
                            "source_url": curr_url
                        })

                    # Look for internal contact/about links to crawl next
                    if pages_crawled < max_pages:
                        for a in soup.find_all("a", href=True):
                            href = a["href"].strip()
                            href_lower = href.lower()
                            if any(k in href_lower for k in ["contact", "about", "team", "career", "services", "leadership"]):
                                full_link = urljoin(curr_url, href)
                                parsed_link = urlparse(full_link)
                                parsed_base = urlparse(website_url)
                                if parsed_link.netloc == parsed_base.netloc and full_link not in visited_urls:
                                    to_visit.append(full_link)

                except Exception as e:
                    logger.debug(f"Error crawling {curr_url}: {e}")

        return {
            "emails": list(out["emails"]),
            "phones": list(out["phones"]),
            "decision_makers": out["decision_makers"],
            "equipment": list(out["equipment"]),
            "intent_signals": out["intent_signals"],
        }

    @classmethod
    async def search_decision_makers(cls, company_name: str, state: str = "") -> List[Dict[str, Any]]:
        """
        Executes targeted web and LinkedIn queries to discover real company executives and owners.
        """
        query = f'site:linkedin.com/in "{company_name}" (owner OR president OR "fleet manager" OR CEO OR founder) {state}'
        items = await cls.search_web(query, limit=5)
        contacts: List[Dict[str, Any]] = []

        for item in items:
            title = item.get("title", "")
            # Typical LinkedIn title: "John Doe - Owner - ABC Trucking | LinkedIn"
            parts = [p.strip() for p in title.split(" - ") if p.strip()]
            if not parts:
                parts = [p.strip() for p in title.split(" | ") if p.strip()]

            if len(parts) >= 2:
                name_candidate = parts[0]
                role_candidate = parts[1] if len(parts) > 1 else "Executive"
                name_words = name_candidate.split()
                if 2 <= len(name_words) <= 3 and not any(w.lower() in NON_PERSON_WORDS for w in name_words):
                    contacts.append({
                        "full_name": name_candidate,
                        "title": role_candidate.replace("| LinkedIn", "").strip(),
                        "linkedin_url": item.get("url"),
                        "confidence": 0.90,
                        "is_primary": True,
                        "verification_source": item.get("url")
                    })

        return contacts

    @classmethod
    async def search_hiring_intent(cls, company_name: str) -> List[Dict[str, Any]]:
        """
        Searches the live web for authentic hiring posts and dispatch job openings.
        """
        query = f'"{company_name}" (hiring OR job OR "dispatcher" OR "driver wanted")'
        items = await cls.search_web(query, limit=4)
        signals: List[Dict[str, Any]] = []

        for item in items:
            snip = item.get("snippet", "").lower()
            title = item.get("title", "")
            if any(k in snip or k in title.lower() for k in ["dispatcher", "dispatch", "hiring", "driver", "recruiting"]):
                signals.append({
                    "signal_type": "HIRING_DISPATCH",
                    "title": f"Hiring Signal: {item.get('title', 'Active Recruitment')}",
                    "description": item.get("snippet", ""),
                    "source_url": item.get("url"),
                    "confidence": 0.90
                })
                break

        return signals

    @classmethod
    async def search_news_and_awards(cls, company_name: str) -> List[Dict[str, Any]]:
        """
        Searches the live web for genuine contract awards, news mentions, or freight milestones.
        """
        query = f'"{company_name}" (freight OR contract OR award OR expansion OR trucking)'
        items = await cls.search_web(query, limit=4)
        signals: List[Dict[str, Any]] = []

        for item in items:
            snip = item.get("snippet", "").lower()
            if any(k in snip for k in ["contract", "expand", "acquisition", "facility", "awarded", "fleet"]):
                signals.append({
                    "signal_type": "BUSINESS_EXPANSION",
                    "title": f"Expansion News: {item.get('title')}",
                    "description": item.get("snippet"),
                    "source_url": item.get("url"),
                    "confidence": 0.88
                })
                break

        return signals

    _last_nominatim_call: float = 0.0
    _nominatim_lock: Optional[asyncio.Lock] = None
    _nominatim_cache: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    async def search_nominatim(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Queries OpenStreetMap Nominatim for real physical location verification.
        Strictly complies with Nominatim Usage Policy:
        - Max 1 request per second (enforced via asyncio.Lock and timer)
        - Descriptive User-Agent with contact information
        - In-memory response caching
        - No bulk scraping
        """
        query_key = f"{query.strip().lower()}:{limit}"
        if query_key in cls._nominatim_cache:
            return cls._nominatim_cache[query_key]

        if cls._nominatim_lock is None:
            cls._nominatim_lock = asyncio.Lock()

        async with cls._nominatim_lock:
            # Enforce minimum 1.0s interval between requests
            now = asyncio.get_event_loop().time()
            elapsed = now - cls._last_nominatim_call
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

            url = f"https://nominatim.openstreetmap.org/search?q={quote_plus(query)}&format=json&addressdetails=1&limit={limit}"
            headers = {
                "User-Agent": "TruckLead-Autopilot/2.0 (dispatch-support@trucklead.com; carrier-verification)"
            }
            try:
                async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                    r = await client.get(url)
                    cls._last_nominatim_call = asyncio.get_event_loop().time()
                    if r.status_code == 200:
                        data = r.json()
                        cls._nominatim_cache[query_key] = data
                        return data
                    elif r.status_code == 429:
                        logger.warning("Nominatim rate limit reached (HTTP 429).")
            except Exception as e:
                logger.debug(f"Nominatim search error: {e}")
            finally:
                cls._last_nominatim_call = asyncio.get_event_loop().time()

        return []
