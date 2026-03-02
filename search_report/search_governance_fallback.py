"""
Fallback Search Governance Report

Strategy:
1. Try JPX search first
2. If JPX fails or doesn't return PDF -> fallback to Company Site search
3. If Company Site fails or doesn't return PDF -> fallback to Nikkei search
4. If all three fail or don't return PDF -> return None
"""

import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import yfinance as yf

logger = logging.getLogger(__name__)


def is_pdf_url(url: Optional[str]) -> bool:
    """Check if URL is a PDF file."""
    if not url:
        return False
    
    url_lower = url.lower()
    # Check if URL ends with .pdf or has .pdf in the path
    if url_lower.endswith('.pdf'):
        return True
    if '.pdf?' in url_lower:  # For URLs with query parameters
        return True
    
    return False


def get_company_info_from_yfinance(stock_code: str) -> Dict[str, Optional[str]]:
    """
    Get company name and website from yfinance.
    
    Args:
        stock_code: Stock code (e.g., "6920.T")
    
    Returns:
        Dict with 'name' and 'site' keys
    """
    try:
        ticker = yf.Ticker(stock_code)
        info = ticker.info
        
        company_name = info.get('longName') or info.get('shortName') or None
        company_site = info.get('website') or None
        
        return {
            'name': company_name,
            'site': company_site
        }
    except Exception as e:
        logger.warning(f"Could not fetch company info for {stock_code} from yfinance: {str(e)}")
        return {
            'name': None,
            'site': None
        }


async def search_governance_fallback(
    searcher,
    validator,
    stock_code: str,
    company_name: Optional[str] = None,
    company_site: Optional[str] = None,
    max_retries: int = 1,
    headless: bool = True
) -> Dict[str, Any]:
    """
    Fallback search for governance reports with multiple sources.
    
    Args:
        searcher: SearXNGSearch instance
        validator: SearchReportValidator instance
        stock_code: Stock code (e.g., "6920.T")
        company_name: Company name for search
        company_site: Company website URL
        max_retries: Number of retry attempts per source
        headless: Run browser in headless mode (default: True)
    
    Returns:
        Dict with keys: 'url', 'source', 'success', 'error_message'
        Example: {
            'url': 'https://...',
            'source': 'jpx',  # or 'company_site' or 'nikkei'
            'success': True,
            'error_message': None
        }
        If all sources fail: {'url': None, 'source': None, 'success': False, 'error_message': 'All sources failed'}
    """
    from search_on_jpx import JPXGovernanceScraper
    
    result = {
        'url': None,
        'source': None,
        'success': False,
        'error_message': None,
        'date': None
    }
    
    # Step 1: Try JPX search
    logger.info(f"[Fallback] Attempting JPX search for {stock_code}")
    async with JPXGovernanceScraper(headless=headless) as jpx_scraper:
        jpx_result = await _search_jpx(jpx_scraper, stock_code)
        
        if jpx_result['success'] and is_pdf_url(jpx_result['url']):
            logger.info(f"[Fallback] JPX search successful: {jpx_result['url']}")
            return {
                'url': jpx_result['url'],
                'source': 'jpx',
                'success': True,
                'error_message': None,
                'date': jpx_result.get('date')
            }
        
        if not jpx_result['success']:
            logger.warning(f"[Fallback] JPX search failed: {jpx_result.get('error_message')}")
        else:
            logger.warning(f"[Fallback] JPX result is not a PDF: {jpx_result['url']}")
    
    if jpx_result['success'] and is_pdf_url(jpx_result['url']):
        logger.info(f"[Fallback] JPX search successful: {jpx_result['url']}")
        return {
            'url': jpx_result['url'],
            'source': 'jpx',
            'success': True,
            'error_message': None
        }
    
    if not jpx_result['success']:
        logger.warning(f"[Fallback] JPX search failed: {jpx_result.get('error_message')}")
    else:
        logger.warning(f"[Fallback] JPX result is not a PDF: {jpx_result['url']}")
    
    # Step 2: Fallback to Company Site search
    logger.info(f"[Fallback] Attempting Company Site search for {stock_code}")
    company_result = await _search_company_site(
        searcher, 
        validator, 
        stock_code, 
        company_site
    )
    
    if company_result['success'] and is_pdf_url(company_result['url']):
        logger.info(f"[Fallback] Company Site search successful: {company_result['url']}")
        return {
            'url': company_result['url'],
            'source': 'company_site',
            'success': True,
            'error_message': None,
            'date': company_result.get('date')
        }
    
    if not company_result['success']:
        logger.warning(f"[Fallback] Company Site search failed: {company_result.get('error_message')}")
    else:
        logger.warning(f"[Fallback] Company Site result is not a PDF: {company_result['url']}")
    
    # Step 3: Fallback to Nikkei search
    logger.info(f"[Fallback] Attempting Nikkei search for {stock_code}")
    nikkei_result = await _search_nikkei(searcher, validator, stock_code)
    
    if nikkei_result['success'] and is_pdf_url(nikkei_result['url']):
        logger.info(f"[Fallback] Nikkei search successful: {nikkei_result['url']}")
        return {
            'url': nikkei_result['url'],
            'source': 'nikkei',
            'success': True,
            'error_message': None,
            'date': nikkei_result.get('date')
        }
    
    if not nikkei_result['success']:
        logger.warning(f"[Fallback] Nikkei search failed: {nikkei_result.get('error_message')}")
    else:
        logger.warning(f"[Fallback] Nikkei result is not a PDF: {nikkei_result['url']}")
    
    # All sources failed or didn't return PDF
    logger.error(f"[Fallback] All search sources exhausted for {stock_code}")
    return {
        'url': None,
        'source': None,
        'success': False,
        'error_message': 'All sources failed or did not return PDF',
        'date': None
    }


async def _search_jpx(jpx_scraper, stock_code: str) -> Dict[str, Any]:
    """
    Search governance report on JPX.
    
    Returns:
        Dict with 'url', 'date', 'success', 'error_message'
    """
    try:
        result = await jpx_scraper.get_latest_governance(stock_code=stock_code)
        
        # JPX returns dict with 'date' and 'pdf_url' keys
        if result and isinstance(result, dict):
            pdf_url = result.get('pdf_url')
            report_date = result.get('date')
            if pdf_url:
                return {
                    'url': pdf_url,
                    'date': report_date,
                    'success': True,
                    'error_message': None
                }
        
        return {
            'url': None,
            'date': None,
            'success': False,
            'error_message': 'JPX returned empty result or no PDF URL'
        }
    
    except Exception as e:
        logger.error(f"JPX search error for {stock_code}: {str(e)}")
        return {
            'url': None,
            'date': None,
            'success': False,
            'error_message': f"JPX error: {str(e)}"
        }


async def _search_company_site(
    searcher,
    validator,
    stock_code: str,
    company_site: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search governance report on company website.
    
    Returns:
        Dict with 'url', 'date', 'success', 'error_message'
    """
    try:
        from search_on_company_site import on_company_site_search
        
        url = on_company_site_search(
            searcher,
            validator,
            stock_code=stock_code,
            search_keyword="corporate governance report",
            result_label="Governance"
        )
        
        if url:
            return {
                'url': url,
                'date': None,
                'success': True,
                'error_message': None
            }
        else:
            return {
                'url': None,
                'date': None,
                'success': False,
                'error_message': 'Company Site search returned empty result'
            }
    
    except Exception as e:
        logger.error(f"Company Site search error for {stock_code}: {str(e)}")
        return {
            'url': None,
            'date': None,
            'success': False,
            'error_message': f"Company Site error: {str(e)}"
        }


async def _search_nikkei(searcher, validator, stock_code: str) -> Dict[str, Any]:
    """
    Search governance report on Nikkei.
    
    Returns:
        Dict with 'url', 'date', 'success', 'error_message'
    """
    try:
        from search_on_nikkei import nikkei_governance_search
        
        url = nikkei_governance_search(
            searcher,
            validator,
            stock_code=stock_code
        )
        
        if url:
            return {
                'url': url,
                'date': None,
                'success': True,
                'error_message': None
            }
        else:
            return {
                'url': None,
                'date': None,
                'success': False,
                'error_message': 'Nikkei search returned empty result'
            }
    
    except Exception as e:
        logger.error(f"Nikkei search error for {stock_code}: {str(e)}")
        return {
            'url': None,
            'date': None,
            'success': False,
            'error_message': f"Nikkei error: {str(e)}"
        }


async def search_governance_fallback_batch(
    searcher,
    validator,
    stock_list: list,
    output_file: str = "governance_fallback_results.csv",
    headless: bool = True
) -> None:
    """
    Search governance reports for multiple companies with fallback logic.
    Save results to CSV file immediately after each company is processed.
    
    Args:
        searcher: SearXNGSearch instance
        validator: SearchReportValidator instance
        stock_list: List of stock codes (e.g., ["6920.T", "4063.T"])
        output_file: Path to output CSV file
        headless: Run browser in headless mode (default: True)
    """
    import csv
    from datetime import datetime
    import os
    
    fieldnames = ['stock_code', 'company_name', 'url', 'source', 'report_date', 'success', 'error_message']
    file_exists = os.path.exists(output_file)
    
    # Write header if file doesn't exist
    if not file_exists:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        logger.info(f"Created new CSV file: {output_file}")
    
    success_count = 0
    total_count = len(stock_list)
    
    for idx, stock_code in enumerate(stock_list, 1):
        try:
            logger.info(f"[{idx}/{total_count}] Processing {stock_code}")
            
            # Get company info from yfinance
            company_info = get_company_info_from_yfinance(stock_code)
            
            result = await search_governance_fallback(
                searcher=searcher,
                validator=validator,
                stock_code=stock_code,
                company_name=company_info.get('name'),
                company_site=company_info.get('site'),
                headless=headless
            )
            
            row = {
                'stock_code': stock_code,
                'company_name': company_info.get('name') or '',
                'url': result['url'] or '',
                'source': result['source'] or '',
                'report_date': result.get('date') or '',
                'success': result['success'],
                'error_message': result['error_message'] or ''
            }
            
            # Append result to CSV immediately
            with open(output_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerow(row)
            
            if result['success']:
                success_count += 1
            
            logger.info(
                f"[{idx}/{total_count}] {stock_code} -> "
                f"Source: {result['source']}, Success: {result['success']}, Date: {result.get('date')}"
            )
        
        except Exception as e:
            logger.error(f"Error processing {stock_code}: {str(e)}")
            row = {
                'stock_code': stock_code,
                'company_name': '',
                'url': '',
                'source': '',
                'report_date': '',
                'success': False,
                'error_message': f"Batch processing error: {str(e)}"
            }
            
            # Append error row to CSV immediately
            with open(output_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerow(row)
    
    logger.info(f"All processing completed. Results saved to {output_file}")
    logger.info(f"Summary: {success_count}/{total_count} successful")
