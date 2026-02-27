try:
    from PIL import Image
    import io
except ImportError:
    pass
from playwright.async_api import async_playwright
import re


def save_graph_as_png(compiled_graph, filename: str = "graph.png"):
    """
    Save a LangGraph graph as a PNG image.

    Args:
        compiled_graph: Compiled LangGraph application
        filename: Output file name (default: graph.png)
    """
    try:
        image_data = compiled_graph.get_graph().draw_mermaid_png()
        
        with open(filename, "wb") as f:
            f.write(image_data)
        
        print(f"✓ Graph saved successfully: {filename}")
        return True
    except Exception as e:
        print(f"✗ Error while saving graph: {e}")
        print("Alternative: Install graphviz: brew install graphviz")
        return False


class PlaywrightCrawler:

    def __init__(self, headless=False, scroll_times=5):
        self.headless = headless
        self.scroll_times = scroll_times

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[\n\t]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _scroll_page(self, page):
        for _ in range(self.scroll_times):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

    async def extract_links(self, url: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded")
            # Skip networkidle - it causes timeout on pages with continuous network activity
            await page.wait_for_timeout(2000)  # Wait 2 seconds for dynamic content to load

            await self._scroll_page(page)

            try:
                await page.wait_for_selector("a[href$='.pdf']", timeout=1000)
            except:
                print("⚠ Không thấy PDF selector (có thể trang không có)")

            elements = await page.eval_on_selector_all(
                "a[href]",
                """
                els => els.map(e => ({
                    text: e.innerText ? e.innerText.trim() : '',
                    href: e.href,
                }))
                """
            )

            await browser.close()

        cleaned = []
        for el in elements:
            cleaned.append({
                "text": self.clean_text(el["text"]),
                "href": el["href"],
            })

        return cleaned
