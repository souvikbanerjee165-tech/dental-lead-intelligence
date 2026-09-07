import asyncio
import re
import urllib.parse
from typing import List, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

from config import MAPS_BASE_URL, USER_AGENT, HEADLESS_BROWSER
from models import RawLead

class GoogleMapsLeadFinder:
    """Agent 1: Scrapes business listings from Google Maps search results."""

    def __init__(self, headless: bool = HEADLESS_BROWSER):
        self.headless = headless

    async def _handle_consent(self, page: Page):
        """Dismiss Google cookie/consent dialog if present."""
        try:
            consent_btn = await page.query_selector('button[aria-label="Accept all"], button[aria-label="Agree to the use of cookies and other data"], form[action*="consent"] button')
            if consent_btn:
                await consent_btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

    async def search(
        self,
        query: str,
        limit: int = 20,
        on_lead_found: Optional[Any] = None,
        is_existing_fn: Optional[Any] = None,
        on_lead_skipped: Optional[Any] = None
    ) -> List[RawLead]:
        """
        Execute Google Maps search and extract up to `limit` business leads.
        Automatically ignores leads already tracked in database if is_existing_fn is provided.
        """
        results: List[RawLead] = []
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"{MAPS_BASE_URL}/search/{encoded_query}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                ]
            )
            context: BrowserContext = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1440, "height": 900},
                locale="en-US"
            )
            page = await context.new_page()

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await self._handle_consent(page)

                feed_selector = 'div[role="feed"]'
                try:
                    await page.wait_for_selector(feed_selector, timeout=10000)
                except Exception:
                    pass

                feed = await page.query_selector(feed_selector)
                if not feed:
                    # Check if landed directly on a single place
                    single_lead = await self._extract_detail_panel(page)
                    if single_lead:
                        is_dup = is_existing_fn and is_existing_fn(single_lead.name, single_lead.website, single_lead.phone)
                        if not is_dup:
                            results.append(single_lead)
                            if on_lead_found:
                                try:
                                    if asyncio.iscoroutinefunction(on_lead_found):
                                        await on_lead_found(single_lead, 1, 1)
                                    else:
                                        on_lead_found(single_lead, 1, 1)
                                except Exception:
                                    pass
                        elif on_lead_skipped:
                            try:
                                if asyncio.iscoroutinefunction(on_lead_skipped):
                                    await on_lead_skipped(single_lead.name, "Already in database")
                                else:
                                    on_lead_skipped(single_lead.name, "Already in database")
                            except Exception:
                                pass
                    await browser.close()
                    return results

                seen_names = set()
                scroll_attempts = 0
                max_scroll_attempts = max(35, (limit * 3) + 10)

                while len(results) < limit and scroll_attempts < max_scroll_attempts:
                    listing_cards = await page.query_selector_all('div.Nv2PK, div[role="article"]')
                    
                    for card in listing_cards:
                        if len(results) >= limit:
                            break

                        try:
                            # 1. Extract from the card itself
                            card_name_el = await card.query_selector('.qBF1Pd, .fontHeadlineSmall, a.hfpxzc')
                            name = ""
                            if card_name_el:
                                name = (await card_name_el.inner_text()).strip()
                                if not name:
                                    name = (await card_name_el.get_attribute("aria-label") or "").strip()

                            if not name or name in seen_names:
                                continue
                            seen_names.add(name)

                            # Extract website link directly on card if present
                            card_web = None
                            web_btn = await card.query_selector('a[data-value="Website"], a.lcr4fd, a[aria-label*="website" i]')
                            if web_btn:
                                href = await web_btn.get_attribute('href')
                                if href and href.startswith("http"):
                                    card_web = self._clean_url(href)

                            # Early database check: If name or card website matches existing database lead, skip!
                            if is_existing_fn and is_existing_fn(name, card_web, None):
                                if on_lead_skipped:
                                    try:
                                        if asyncio.iscoroutinefunction(on_lead_skipped):
                                            await on_lead_skipped(name, "Already saved in database")
                                        else:
                                            on_lead_skipped(name, "Already saved in database")
                                    except Exception:
                                        pass
                                continue

                            # Extract card rating & reviews
                            card_rating = None
                            card_reviews = 0
                            rating_el = await card.query_selector('span.MW4etd')
                            if rating_el:
                                try:
                                    card_rating = float((await rating_el.inner_text()).strip())
                                except Exception:
                                    pass

                            rev_el = await card.query_selector('span.UY7F9')
                            if rev_el:
                                try:
                                    rev_raw = await rev_el.inner_text()
                                    digits = re.sub(r'[^\d]', '', rev_raw)
                                    if digits:
                                        card_reviews = int(digits)
                                except Exception:
                                    pass

                            # Get direct maps place link from anchor
                            link_el = await card.query_selector('a.hfpxzc')
                            maps_url = await link_el.get_attribute('href') if link_el else page.url

                            # 2. Click to open detail panel for full info (phone, address, high-res website)
                            phone = None
                            address = None
                            category = None

                            if link_el:
                                await link_el.click()
                                try:
                                    await page.wait_for_selector('h1.DUwDvf', timeout=4000)
                                    await page.wait_for_timeout(500)
                                    detail_lead = await self._extract_detail_panel(page, fallback_name=name)
                                    if detail_lead:
                                        category = detail_lead.category
                                        phone = detail_lead.phone
                                        address = detail_lead.address
                                        if detail_lead.website:
                                            card_web = detail_lead.website
                                        if detail_lead.rating:
                                            card_rating = detail_lead.rating
                                        if detail_lead.review_count:
                                            card_reviews = detail_lead.review_count
                                        if detail_lead.maps_url:
                                            maps_url = detail_lead.maps_url
                                except Exception:
                                    await page.wait_for_timeout(1500)

                            # Detail panel database check: Check phone / real website against existing database
                            if is_existing_fn and is_existing_fn(name, card_web, phone):
                                if on_lead_skipped:
                                    try:
                                        if asyncio.iscoroutinefunction(on_lead_skipped):
                                            await on_lead_skipped(name, "Already saved in database (phone/website match)")
                                        else:
                                            on_lead_skipped(name, "Already saved in database (phone/website match)")
                                    except Exception:
                                        pass
                                continue

                            # Extract lat/long coordinates from maps_url or current page url
                            lat, lng = None, None
                            for u in (maps_url, page.url):
                                if u:
                                    m_at = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', u)
                                    if m_at:
                                        try:
                                            lat, lng = float(m_at.group(1)), float(m_at.group(2))
                                            break
                                        except Exception:
                                            pass
                                    m_3d = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', u)
                                    if m_3d:
                                        try:
                                            lat, lng = float(m_3d.group(1)), float(m_3d.group(2))
                                            break
                                        except Exception:
                                            pass

                            lead = RawLead(
                                name=name,
                                category=category or "Dental clinic",
                                rating=card_rating,
                                review_count=card_reviews,
                                phone=phone,
                                address=address,
                                website=card_web,
                                maps_url=maps_url,
                                latitude=lat,
                                longitude=lng
                            )
                            results.append(lead)

                            if on_lead_found:
                                try:
                                    if asyncio.iscoroutinefunction(on_lead_found):
                                        await on_lead_found(lead, len(results), limit)
                                    else:
                                        on_lead_found(lead, len(results), limit)
                                except Exception:
                                    pass

                        except Exception:
                            continue

                    # Scroll down inside feed
                    await page.evaluate(
                        '''(selector) => {
                            const feed = document.querySelector(selector);
                            if (feed) {
                                feed.scrollTop += 1800;
                            }
                        }''',
                        feed_selector
                    )
                    await page.wait_for_timeout(1800)
                    scroll_attempts += 1

                    # Check for end of list
                    end_banner = await page.query_selector('span.HlvSq')
                    if end_banner:
                        break

            finally:
                await browser.close()

        return results

    def _clean_url(self, url: str) -> str:
        """Strip Google redirect wrappers."""
        if "google.com/url?q=" in url:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            if "q" in query_params:
                return query_params["q"][0]
        return url

    async def _extract_detail_panel(self, page: Page, fallback_name: str = "") -> Optional[RawLead]:
        """Extract structured fields from the Google Maps business detail panel."""
        try:
            # Business Name
            name_el = await page.query_selector('h1.DUwDvf')
            name = (await name_el.inner_text()).strip() if name_el else fallback_name

            # Category
            cat_el = await page.query_selector('button.DkEaL, button[jsaction*="category"]')
            category = (await cat_el.inner_text()).strip() if cat_el else None

            # Rating and Reviews
            rating = None
            review_count = 0
            rating_el = await page.query_selector('div.F7nice span[aria-hidden="true"]')
            if rating_el:
                try:
                    rating = float((await rating_el.inner_text()).strip())
                except Exception:
                    pass

            reviews_el = await page.query_selector('div.F7nice span[aria-label*="review" i], div.F7nice span:nth-child(2)')
            if reviews_el:
                try:
                    rev_text = await reviews_el.inner_text()
                    digits = re.sub(r'[^\d]', '', rev_text)
                    if digits:
                        review_count = int(digits)
                except Exception:
                    pass

            # Address
            addr_el = await page.query_selector('button[data-item-id="address"] div.fontBodyMedium, [data-item-id="address"]')
            address = None
            if addr_el:
                raw_addr = (await addr_el.inner_text()).strip()
                address = re.sub(r'^[^\w\d]+', '', raw_addr).strip()
                address = " ".join(address.split())

            # Website
            website = None
            web_el = await page.query_selector('a[data-item-id="authority"], a[aria-label*="website" i], [data-tooltip*="website" i]')
            if web_el:
                href = await web_el.get_attribute('href')
                if href and href.startswith("http"):
                    website = self._clean_url(href)

            # Phone Number
            phone = None
            # 1. Try exact phone:tel: data-item-id
            phone_el = await page.query_selector('button[data-item-id^="phone:tel:"], [data-item-id*="phone:tel:"]')
            if phone_el:
                data_id = (await phone_el.get_attribute("data-item-id") or "").strip()
                if "tel:" in data_id:
                    phone = data_id.split("tel:")[-1].strip()
            
            # 2. Fallback to aria-label or inner text
            if not phone:
                phone_btn = await page.query_selector('button[data-item-id*="phone"], [data-tooltip*="phone" i], [aria-label*="Phone:" i]')
                if phone_btn:
                    aria = (await phone_btn.get_attribute("aria-label") or "").strip()
                    if "Phone:" in aria:
                        phone = aria.replace("Phone:", "").strip()
                    else:
                        raw_phone = (await phone_btn.inner_text() or "").strip()
                        if raw_phone and "send to" not in raw_phone.lower():
                            phone = re.sub(r'^[^\w\d+]+', '', raw_phone).strip()

            if phone:
                phone = " ".join(phone.split())

            return RawLead(
                name=name or fallback_name,
                category=category,
                rating=rating,
                review_count=review_count,
                phone=phone,
                address=address,
                website=website,
                maps_url=page.url
            )
        except Exception:
            return None
