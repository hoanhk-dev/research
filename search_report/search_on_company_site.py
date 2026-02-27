from urllib.parse import urlparse
import json
import time
import csv
import os
import yfinance as yf

def normalize_domain(url: str) -> str:
    """
    Convert:
        https://www.lasertec.co.jp/ -> lasertec.co.jp
        https://laserTec.co.jp/en/ -> lasertec.co.jp
        http://www.mhi.com -> mhi.com
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain

def on_company_site_search(
    searcher,
    validator,
    stock_code: str,
    search_keyword: str,
    result_label: str,
):
    ticker = yf.Ticker(f"{stock_code}")
    info = ticker.info
    website = info.get("website")
    domain = normalize_domain(website)

    query = f"site:{domain} filetype:pdf {search_keyword}"
    results = searcher.search(query)

    best_url = "Not Found"

    if results:
        best = validator.best_report(query, results)
        best_url = best.get("url", "") if best else ""
    
    return best_url


def on_company_site_search_save_evaluate(
    searcher,
    validator,
    stock_list: list,
    output_file: str,
    search_keyword: str,
    result_label: str,
    delay: int = 5
):
    """
    Generic search function.

    search_keyword: ví dụ
        "integrated report"
        "corporate governance report"
        "sustainability report"

    result_label: tên cột CSV
        "Integrated"
        "Governance"
    """

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        writer.writerow([
            "Company",
            f"{result_label} Results",
            f"{result_label} Best URL"
        ])

        for stock_code in stock_list:
            ticker = yf.Ticker(f"{stock_code}")
            info = ticker.info
            website = info.get("website")
            domain = normalize_domain(website)

            print("\n==============================")
            print(f"Processing domain: {domain}")
            print("==============================")

            best_url = ""
            results = []

            try:
                query = f"site:{domain} filetype:pdf {search_keyword}"
                results = searcher.search(query)

                if results:
                    best = validator.best_report(query, results)
                    best_url = best.get("url", "") if best else ""

            except Exception as e:
                print(f"Search failed: {domain}")
                print(e)

            results_json = json.dumps(results, ensure_ascii=False)

            writer.writerow([
                domain,
                results_json,
                best_url
            ])

            f.flush()
            time.sleep(delay)
            print(f"Saved: {domain}")

    print("\nDone. Saved to:", os.path.abspath(output_file))
