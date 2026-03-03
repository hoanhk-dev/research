from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
import json
from utils import PlaywrightCrawler, save_graph_as_png

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
import yfinance as yf

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    current_url: str
    links: list
    explored: Annotated[list, operator.add]

class AutomationSearchReportDFS:
    def __init__(self, max_deep=10, max_urls=2, headless=True, save_png=False):
        self.crawler = PlaywrightCrawler(headless=headless)
        self.llm = ChatOpenAI(model="gemini-3-flash-preview")
        self.tree = {}
        self.deep = 0
        self.max_deep = max_deep
        self.max_urls = max_urls
        self.max_deep_mask = max_deep
        self.max_urls_mask = max_urls
        self.stack_url = []
        self.save_png = save_png
        self.app = self.build_graph()
    # -------------------------
    # CRAWL NODE
    # -------------------------
    async def crawl_node(self, state: AgentState):
        # print("TREE:")
        # print(json.dumps(self.tree, indent=2))
        # print("="*100)
        
        url = state["current_url"]
        links = await self.crawler.extract_links(url)
        return {
            "links": links
        }

    async def llm_node(self, state: AgentState):

        prompt_text = f"""
        You are a web navigation expert.

        Below are the navigation links extracted from the current webpage.
        These links have been filtered to exclude already-explored links.

        Extracted Links:
        {state['links']}

        Your task:

        GOAL:
        Find the FULL Integrated Report PDF as efficiently as possible.

        STEP 1 — Direct PDF Check:
        - First, check whether a FULL Integrated Report PDF already exists in the provided links.
        - A full report PDF:
            - Ends with ".pdf"
            - Contains keywords such as:
            "integrated", "report", "annual", "ir_all"
            - Is NOT a partial PDF (e.g., ir_p1-10.pdf, section-based files).
        - If multiple full PDFs exist, prefer the latest year.

        If found, return:

        {{
            "next_step": "END",
            "url": [
                {{
                    "link": "<full_pdf_url>",
                    "score": 1.0
                }}
            ]
        }}

        STEP 2 — If NOT found:
        Select up to 1 URLs that have the highest probability of containing the Integrated Report PDF.

        Prioritize links containing keywords such as:
        - integrated
        - investor
        - ir
        - annual
        - report
        - sustainability
        - library
        - financial
        - disclosure

        Rules:
        - Return AT MOST {self.max_urls} URLs
        - Rank by likelihood (most relevant first)
        - Ignore irrelevant pages (careers, news unrelated to reports, products, etc.)
        - Do NOT return more than {self.max_urls} URLs

        Return:

        {{
            "next_step": "continue",
            "url": [
                {{"link": "url1", "score": 0.92}},
                {{"link": "url2", "score": 0.85}},
                {{"link": "url3", "score": 0.78}}
            ]
        }}

        IMPORTANT:
        - Return ONLY one JSON object.
        - Do NOT include explanations.
        - Do NOT include markdown.
        - Do NOT include text outside JSON.
        """

        response = await self.llm.ainvoke(prompt_text)

        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()
        content_json = json.loads(content)

        return {
            "messages": [AIMessage(content=json.dumps(content_json))],
        }
    
    def route_next_url(self, state: AgentState):
        current_link = state["current_url"]
        
        if current_link:
            return "crawl"
        else:
            return "END"
        

    def route(self, state: AgentState):
        last = state["messages"][-1].content

        try:
            response_json = json.loads(last) if isinstance(last, str) else last
            next_step = response_json.get("next_step", "END")
            
            if next_step == "continue":
                return "continue"
            else:
                return "output_processing"
                
        except json.JSONDecodeError:
            return "output_processing"
    
    def output_processing(self, state: AgentState):
        last = state["messages"][-1].content
        last_json = json.loads(last)
        
        return {
            "current_url": last_json['url'][0]['link']
        }
    
    def get_next_url_from_stack(self, state: AgentState):
        """
        Traverse the tree with DFS strategy:
        1. If current depth < max_deep: add new URLs to tree and go deeper
        2. If current depth == max_deep: pop from current level
        3. If current level is empty: backtrack to previous level
        4. If all levels exhausted: return None
        """
        data = json.loads(state["messages"][-1].content)

        # Validate input
        if not data.get("url"):
            return None

        urls = data.get("url", [])

        # Case 1: Current depth is still less than max_deep
        if self.deep < self.max_deep:
            # Add new level to tree
            stack = sorted(urls, key=lambda x: x["score"], reverse=False)  
            self.deep += 1
            self.tree[self.deep] = stack
            if stack:
                top_url = stack.pop()
                self.tree[self.deep] = stack 
                return {
                        "current_url": top_url["link"]
                    }
        
        # Case 2: At max_deep, pop from current level
        if self.deep == self.max_deep and self.deep in self.tree:
            stack = self.tree[self.deep]
            if stack:
                top_url = stack.pop()
                self.tree[self.deep] = stack
                return {
                    "current_url": top_url["link"]
                }
        
        # Case 3: Current level exhausted, backtrack
        while self.deep > 0:
            self.deep -= 1
            if self.deep in self.tree and self.tree[self.deep]:
                stack = self.tree[self.deep]
                top_url = stack.pop()
                self.tree[self.deep] = stack
                return {
                    "current_url": top_url["link"]
                }
        
        # Case 4: No more URLs to explore
        return  {
            "current_url": None
            }

    def build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("crawl", self.crawl_node)
        graph.add_node("llm", self.llm_node)
        graph.add_node("get_next_url", self.get_next_url_from_stack)
        graph.add_node("output_processing", self.output_processing)
        
        graph.set_entry_point("crawl")
        graph.add_edge("crawl", "llm")
        graph.add_conditional_edges(
            "llm",
            self.route,
            {
                "continue": "get_next_url",
                "output_processing": "output_processing",
            }
        )
        graph.add_edge("output_processing", END)
        graph.add_conditional_edges(
            "get_next_url",
            self.route_next_url,
            {
                "crawl": "crawl",
                "END": END,
            }
        )

        app = graph.compile()

        if self.save_png:
            try:
                save_graph_as_png(app, "bot_access_link_graph.png")
            except Exception as e:
                print(f"Failed to save graph visualization: {e}")
        return app
    
    async def run(self, stock_code: str):
        ticker = yf.Ticker(stock_code)
        info = ticker.info
        website = info.get("website")

        # init 
        self.tree = {}
        self.deep = 0
        self.max_deep = self.max_deep_mask
        self.max_urls = self.max_urls_mask
        self.stack_url = []

        
        initial_state = {
            "messages": [],
            "current_url": website,
            "links": [],
        }
    
        # Increase recursion limit for graph traversal
        config = {"recursion_limit": 100}
        final_state = await self.app.ainvoke(initial_state, config=config)

        return final_state
    