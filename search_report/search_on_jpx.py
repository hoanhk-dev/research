import csv
import os
from playwright.async_api import async_playwright
import yfinance as yf


class JPXGovernanceScraper:
    BASE_URL = "https://www2.jpx.co.jp"
    SEARCH_URL = "https://www2.jpx.co.jp/tseHpFront/JJK020030Action.do"

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.playwright = None
        self.browser = None
        self.page = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless
        )
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ==========================================
    # Core Public Method
    # ==========================================

    async def get_latest_governance(self, stock_code: str):
        """
        Returns:
            {
                "date": str | None,
                "pdf_url": str | None,
            }
        """
        stock_code = stock_code.replace(".T", "")
        try:
            await self._search_stock(stock_code)
            await self._open_basic_information()
            await self._open_governance_tab()

            table = await self._get_japanese_governance_table()

            return await self._extract_latest_row(table)

        except Exception as e:
            print(f"[ERROR] {stock_code}: {e}")
            return {
                "date": None,
                "pdf_url": None,
            }

    # ==========================================
    # Internal Steps
    # ==========================================

    async def _search_stock(self, stock_code: str):
        await self.page.goto(self.SEARCH_URL, wait_until="domcontentloaded")
        await self.page.fill('input[name="eqMgrCd"]', stock_code)
        await self.page.get_by_role("button", name="Search").click()
        await self.page.wait_for_timeout(1000)

    async def _open_basic_information(self):
        await self.page.locator(
            'input[name="detail_button"][value="Basic information"]'
        ).click()
        await self.page.wait_for_timeout(1500)

    async def _open_governance_tab(self):
        await self.page.get_by_role(
            "link",
            name="Corporate governance"
        ).first.click()

    async def _get_japanese_governance_table(self):
        locator = self.page.locator(
            "//h4[contains(text(),'Corporate governance information (Japanese)')]"
            "/following-sibling::table[1]"
        )
        await locator.wait_for()
        return locator

    async def _extract_latest_row(self, table):
        rows = table.locator("tr")
        row_count = await rows.count()

        if row_count <= 3:
            return {
                "date": None,
                "pdf_url": None,
            }

        # Skip header rows
        first_data_row = rows.nth(3)
        cols = first_data_row.locator("td")

        date_text = (await cols.nth(7).inner_text()).strip()

        file_col = cols.nth(8)
        links = file_col.locator("a")
        link_count = await links.count()

        pdf_link = None

        for i in range(link_count):
            href = await links.nth(i).get_attribute("href")
            if not href:
                continue

            full_url = self.BASE_URL + href

            if href.endswith(".pdf"):
                pdf_link = full_url

        return {
            "date": date_text,
            "pdf_url": pdf_link,
        }

# ==========================================
# Legacy Helper Function
# ==========================================

async def jpx_governance_search_save_evaluate(
    stock_list,
    output_file: str = "jpx_governance_latest.csv",
    headless: bool = False
):
    # Write header if file doesn't exist
    file_exists = os.path.exists(output_file)
    
    async with JPXGovernanceScraper(headless=headless) as scraper:
        with open(output_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Company", "Date", "PDF",])

            for stock_code in stock_list:
                ticker = yf.Ticker(stock_code)
                info = ticker.info
                name = info.get("longName") 
                print(f"Processing {name} ({stock_code})")

                try:
                    result = await scraper.get_latest_governance(stock_code)

                    writer.writerow([
                        name,
                        result['date'],
                        result['pdf_url'],
                    ])
                    f.flush()  # Ensure data is written immediately

                except Exception as e:
                    print(f"❌ Error {name}: {e}")

                    writer.writerow([
                        name,
                        None,
                        None,
                    ])
                    f.flush()  # Ensure data is written immediately

    print("\nDone. Saved to:", os.path.abspath(output_file))