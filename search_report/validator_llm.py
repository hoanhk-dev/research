import os
from langchain_openai import ChatOpenAI
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

os.environ["OPENAI_API_KEY"] = "proxypal-local"
os.environ["OPENAI_API_BASE"] = "http://localhost:8317/v1"

class SearchReportValidator:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0.0)

    def run_chatgpt(self, user_prompt: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("user", "{input}")
        ])
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke({"input": user_prompt})

    def best_report(self, query: str, results: list) -> dict:
        """
        Return ONLY the single best matching + newest report
        from search results.
        """

        user_prompt = f"""
        You are an AI agent that selects the BEST report result.

        Query:
        {query}

        Search results:
        {json.dumps(results, indent=2)}

        Task:
        - Select ONLY ONE result that best matches the query intent
        - Prefer official PDF reports
        - Prefer the newest report (latest year/date in title/content/url)
        - If no true match exists, still return the closest available report

        Output format (STRICT JSON ONLY):

        {{
          "url": "...",
          "title": "...",
          "category": "ir_report / governance_report / other",
          "detected_date": "YYYY-MM-DD or YYYY or null",
          "why_best": "short explanation"
        }}

        Do NOT output anything outside JSON.
        """

        raw = self.run_chatgpt(user_prompt)

        # clean markdown fences
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        raw = raw.strip()

        return json.loads(raw)