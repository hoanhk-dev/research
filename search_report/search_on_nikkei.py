import csv
import time
import yfinance as yf

def get_name_company(stock_code):
    ticker = yf.Ticker(f"{stock_code}")
    info = ticker.info
    return info.get("longName", stock_code)

def nikkei_governance_search(
    searcher,
    validator,
    stock_code
):
    name = get_name_company(stock_code)
    print("\n" + "=" * 100)
    print("Company:", name)
    print("=" * 100)

    query = f"""
    site:www.nikkei.com/markets/ir/irftp/data/tdnr/tdnetg3 CORPORATE GOVERNANCE 最終更新日 {name} filetype:pdf
    """

    print("Query:", query.strip())

    try:
        search_results = searcher.search(query)

        best = validator.best_report(query, search_results)

        if not best:
            print("⚠ No valid best result detected")
            return None

        print("Best:", best)
        return best

    except Exception as e:
        print(f"❌ Error processing {name}: {e}")
        return None
    
def nikkei_governance_search_save_evaluate(
    searcher,
    validator,
    stock_list,
    output_file="nikkei_governance_best_results.csv",
    delay=10
):
    """
    Search Nikkei governance PDF for a list of stock codes
    and save best validated result to CSV.
    """

    # ========================
    # CREATE CSV HEADER
    # ========================
    with open(output_file, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "company_name",
            "title",
            "url",
            "category",
            "detected_date",
            "why_best"
        ])

    # ========================
    # MAIN LOOP
    # ========================
    for stock_code in stock_list:
        name = get_name_company(stock_code)
        print("\n" + "=" * 100)
        print("Company:", name)
        print("=" * 100)

        query = f"""
        site:www.nikkei.com/markets/ir/irftp/data/tdnr/tdnetg3 CORPORATE GOVERNANCE 最終更新日 {name} filetype:pdf
        """

        print("Query:", query.strip())

        try:
            search_results = searcher.search(query)

            best = validator.best_report(query, search_results)

            if not best:
                print("⚠ No valid best result detected")
                continue

            print("Best:", best)

            with open(output_file, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    name,
                    best.get("title"),
                    best.get("url"),
                    best.get("category"),
                    best.get("detected_date"),
                    best.get("why_best")
                ])

            print("✅ Saved best report:", best.get("title"))

        except Exception as e:
            print(f"❌ Error processing {name}: {e}")

        time.sleep(delay)

    print("\nDONE. File saved:", output_file)