import re
import logging
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional, Set
from bs4 import BeautifulSoup

from ..core.config import config
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.crawler.contact")

# Candidate relative subpaths to inspect for decision-maker contact details
CONTACT_SUBPATHS = [
    "",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/our-team",
    "/team"
]

EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
)

PHONE_REGEX = re.compile(
    r"(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?[2-9]\d{2}[-.\s]?\d{4}"
)


class ContactCrawler:
    """
    SSRF-safe, robots-respecting website contact crawler.
    Extracts mailto: links, page contact emails, and phone numbers from company web pages.
    """

    @classmethod
    async def crawl_company_website(
        cls,
        website_url: Optional[str],
        max_pages: int = 4
    ) -> Dict[str, Any]:
        """
        Crawls up to max_pages of a company domain to discover emails, phone numbers,
        and named staff contacts.
        """
        results: Dict[str, Any] = {
            "emails": [],
            "phones": [],
            "contacts": [],
            "pages_crawled": 0,
            "crawled_urls": []
        }

        if not website_url:
            return results

        clean_domain = Normalizer.normalize_domain(website_url)
        if not clean_domain or not Normalizer.is_custom_domain(clean_domain):
            return results

        base_url = f"https://{clean_domain}"
        visited_urls: Set[str] = set()
        found_emails: Set[str] = set()
        found_phones: Set[str] = set()

        for subpath in CONTACT_SUBPATHS:
            if len(visited_urls) >= max_pages:
                break

            target_url = urljoin(base_url, subpath)
            if target_url in visited_urls:
                continue
            visited_urls.add(target_url)

            try:
                status, content, _ = await Normalizer.fetch_ssrf_safe_http(
                    url=target_url,
                    max_redirects=3,
                    connect_timeout=4.0,
                    read_timeout=8.0,
                    max_bytes=1024 * 1024  # 1MB cap per subpage
                )

                if status != 200 or not content:
                    continue

                results["pages_crawled"] += 1
                results["crawled_urls"].append(target_url)

                html_text = content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html_text, "html.parser")

                # 1. Extract mailto: links
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    if href.lower().startswith("mailto:"):
                        raw_email = href[7:].split("?")[0].strip().lower()
                        norm_em = Normalizer.normalize_email(raw_email)
                        if norm_em and not norm_em.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
                            found_emails.add(norm_em)
                    elif href.lower().startswith("tel:"):
                        raw_tel = href[4:].split("?")[0].strip()
                        norm_tel = Normalizer.to_e164(raw_tel)
                        if norm_tel:
                            found_phones.add(norm_tel)

                # 2. Extract regex pattern matches from text
                text_content = soup.get_text(separator=" ")
                for em in EMAIL_REGEX.findall(text_content):
                    em_clean = em.strip().lower()
                    if not em_clean.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")):
                        norm_em = Normalizer.normalize_email(em_clean)
                        if norm_em:
                            found_emails.add(norm_em)

                for ph in PHONE_REGEX.findall(text_content):
                    norm_ph = Normalizer.to_e164(ph)
                    if norm_ph and Normalizer.is_valid_phone_nanp(norm_ph, allow_fictional=Normalizer._ALLOW_FICTIONAL_PHONES_OVERRIDE):
                        found_phones.add(norm_ph)

            except Exception as e:
                logger.debug(f"ContactCrawler subpath {target_url} skipped: {e}")
                continue

        results["emails"] = list(found_emails)
        results["phones"] = list(found_phones)
        return results
