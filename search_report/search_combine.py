from searcher_searxng import SearXNGSearch
from validator_llm import SearchReportValidator
from search_on_jpx import JPXGovernanceScraper
from datetime import datetime
import csv
import os
import yfinance as yf
from search_on_company_site import normalize_domain

class SearchReportCombine:
    def __init__(self,headless=True):
        self.xng_searcher = SearXNGSearch()
        self.validator = SearchReportValidator()
        self.jpx_scraper = JPXGovernanceScraper(headless=True)

    def parse_date(self, date_str):
        if not date_str:
            return None
        formats = [
            "%Y/%m/%d",
            "%Y-%m-%d",
            "%Y.%m.%d",
            "%Y/%m",
            "%Y"
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def normalize_report(self, source_name, data):
        if not data:
            return None

        if "date" in data:
            date_value = data.get("date")
            url = data.get("pdf_url")
        else:
            date_value = data.get("detected_date")
            url = data.get("url")

        parsed = self.parse_date(date_value)

        if not parsed or not url:
            return None

        return {
            "source": source_name,
            "url": url,
            "date": parsed,
            "raw_date": date_value,
        }
    def select_latest(self, *reports):
        valid_reports = [r for r in reports if r is not None]

        if not valid_reports:
            return None

        return max(valid_reports, key=lambda x: x["date"])

    async def __call__(self, stock_id: str, company_name: str, company_site: str):
        # 1 - Search on company site
        query_on_company_site = f"site:{normalize_domain(company_site)} filetype:pdf corporate governance report"
        results_on_company_site = self.xng_searcher.search(query_on_company_site)
        best_on_company_site = self.validator.best_report(query_on_company_site, results_on_company_site)

        # 2 - Search on nikkei site
        query_on_nikkei_site = f"site:www.nikkei.com/markets/ir/irftp/data/tdnr/tdnetg3 filetype:pdf CORPORATE GOVERNANCE 最終更新日 {company_name}"
        results_on_nikkei_site = self.xng_searcher.search(query_on_nikkei_site)
        best_on_nikkei_site = self.validator.best_report(query_on_nikkei_site, results_on_nikkei_site)

        # 3 - Search on JPX - Listed Company Search
        async with self.jpx_scraper as scraper:
            best_on_jpx = await scraper.get_latest_governance(stock_id)

        normalize_company = self.normalize_report("company_site", best_on_company_site)
        normalize_nikkei = self.normalize_report("nikkei_site", best_on_nikkei_site)
        normalize_jpx = self.normalize_report("jpx_site", best_on_jpx)

        latest = self.select_latest(normalize_company, normalize_nikkei, normalize_jpx)

        return latest

    async def search_single_company(self, stock_code: str):
        """
        Search governance report for a single company.
        Auto-fetch company name and website from yfinance.
        
        Args:
            stock_code: Stock code with .T suffix (e.g., "6920.T")
        
        Returns:
            dict with keys: source, url, date, raw_date
            or None if not found
        """
        # Get company info from yfinance
        ticker = yf.Ticker(stock_code)
        info = ticker.info
        company_name = info.get("longName")
        company_site = info.get("website")
        stock_id = stock_code.replace(".T", "")
        
        if not company_name or not company_site:
            print(f"⚠️ Could not fetch info for {stock_code}")
            return None
        
        print(f"Processing {company_name} ({stock_code})")
        
        try:
            result = await self(
                stock_id=stock_id,
                company_name=company_name,
                company_site=company_site
            )
            
            if result:
                print(f"✅ Found: {result['source']} - {result['raw_date']}")
                return result
            else:
                print(f"❌ No result found")
                return None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
            return None

    async def process_companies(self, stock_list: list, output_file: str = "governance_reports_combined.csv"):
        """
        Process list of stock codes and save results to CSV file.
        Auto-fetch company name and website from yfinance.
        
        Args:
            stock_list: list of stock codes (e.g., ["7203.T", "9983.T"])
            output_file: output CSV file path
        """
        
        # Write header if file doesn't exist
        file_exists = os.path.exists(output_file)
        
        with open(output_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Stock ID", "Company Name", "Source", "URL", "Date", "Raw Date"])
            
            for stock_code in stock_list:
                # Get company info from yfinance
                ticker = yf.Ticker(stock_code)
                info = ticker.info
                company_name = info.get("longName")
                company_site = info.get("website")
                
                if not company_name or not company_site:
                    print(f"⚠️ Could not fetch info for {stock_code}")
                    continue
                
                # Remove .T suffix for stock_id
                stock_id = stock_code.replace(".T", "")
                
                print(f"Processing {company_name} ({stock_code})")
                
                try:
                    result = await self(
                        stock_id=stock_id,
                        company_name=company_name,
                        company_site=company_site
                    )
                    
                    if result:
                        writer.writerow([
                            stock_id,
                            company_name,
                            result['source'],
                            result['url'],
                            result['date'].strftime("%Y-%m-%d"),
                            result['raw_date'],
                        ])
                    else:
                        writer.writerow([
                            stock_id,
                            company_name,
                            None,
                            None,
                            None,
                            None,
                        ])
                    
                    f.flush()  # Ensure data is written immediately
                    
                except Exception as e:
                    print(f"❌ Error processing {company_name} ({stock_code}): {e}")
                    writer.writerow([
                        stock_id,
                        company_name,
                        None,
                        None,
                        None,
                        None,
                    ])
                    f.flush()
        
        print(f"\n✅ Done. Saved to: {os.path.abspath(output_file)}")