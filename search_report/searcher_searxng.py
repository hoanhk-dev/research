from pyserxng.models import SafeSearchLevel, SearchConfig, TimeRange, SearchCategory
from pyserxng import SearXNGClient
from pyserxng.models import InstanceInfo


class SearXNGSearch:
    def __init__(self, instance_url="http://localhost:8888"):
        self.client = SearXNGClient()
        self.instance = InstanceInfo(url=instance_url)

        self.config = SearchConfig(
            page=1,
            safe_search=SafeSearchLevel.STRICT,
            timeout=30,
            engines=["google"],  # 🔥 only google
            categories=[SearchCategory.GENERAL]
        )

        # self.config.time_range = TimeRange.YEAR

    def search(self, query: str):
        print(f"\nQuery: {query}")

        results = self.client.search(
            query,
            instance=self.instance,
            config=self.config
        )

        print(f"Found {len(results.results)} results\n")

        cleaned_results = []

        if results.results:
            for result in results.results:
                cleaned_results.append({
                    "title": str(result.title),
                    "url": str(result.url),
                    "content": str(result.content) if result.content else ""
                })

        else:
            print("No results\n")

        return cleaned_results