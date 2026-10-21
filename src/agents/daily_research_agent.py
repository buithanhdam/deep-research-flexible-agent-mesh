"""Daily Research Agent - orchestrated daily IT/AI/ML research pipeline.

Replicates the n8n daily research flow:
  1. Gather data from multiple sources (news, arxiv, github, huggingface).
  2. Synthesize a structured Markdown report via LLM.
  3. Upload report file to Google Drive.
  4. Return the report link (notification handled elsewhere / UI).

Can be run standalone (CLI) or triggered from the Chainlit UI.
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.constants import AGENT_RESEARCH
from src.tools.base_tool import BaseTool
from src.tools.news_search_tool import NewsSearchTool
from src.tools.arxiv_papers_tool import ArxivSearchTool
from src.tools.github_trending_tool import GitHubRepoTool
from src.tools.hf_tool import HuggingFaceTool
from src.tools.google_drive_upload_tool import GoogleDriveUploadTool
from src.logger import get_logger

logger = get_logger(__name__)

REPORT_PROMPT = """You are a senior technology research analyst. Synthesize the collected data below into a comprehensive, well-structured Markdown daily research report in English.

The report MUST follow this exact structure:
# 📚 Daily Technology Research Report
## 📅 Report Information
- Report Date: {report_date}
- Status: ✅ Completed

## 🤖 AI & LLM Technologies
(Summarize trending models, new releases, LLM advances from HF + news + arxiv)

## ⚙️ Automation & AI Agents
(Summarize agent frameworks, MCP, automation tools from GitHub + news)

## 💻 Software Engineering & Development Tools
(Summarize dev tooling, platforms, engineering trends from news + GitHub)

## 📑 Research Papers & Technical Articles
(List key arxiv papers with title, link, one-line summary)

## 🚀 Open Source Projects & Industry Trends
(List trending GitHub repos with link, stars, why it matters)
(Highlight industry trends from news)

## 📈 HuggingFace Trending Models
(Top models with downloads/likes and links)

Rules:
- Use ONLY the data provided. Do not invent links or facts.
- Every item must include its source URL as a markdown link.
- Be concise but informative: 2-4 bullet points per subsection.
- If a data section is empty or failed, write "No data collected today." under it.
- Output ONLY the raw Markdown content, no code fences.
"""

COLLECT_SOURCES = [
    "news", "arxiv", "github", "huggingface",
]


class DailyResearchAgent(BaseAgent):
    """Orchestrated daily research pipeline: collect -> synthesize -> upload."""

    def __init__(self, tools: Optional[List[BaseTool]] = None):
        default_tools = [
            NewsSearchTool(),
            ArxivSearchTool(),
            GitHubRepoTool(),
            HuggingFaceTool(),
            GoogleDriveUploadTool(),
        ]
        super().__init__(AGENT_RESEARCH, tools=tools or default_tools)

    def get_system_prompt(self) -> str:
        return REPORT_PROMPT

    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Implement BaseAgent abstract method — chạy full daily research pipeline.

        Args:
            task: Mô tả nhiệm vụ (thường là "daily research" — thông tin gợi ý
                  có thể nằm trong context, ví dụ nguồn cần chạy).
            context: Tùy chọn: {"sources": [...], "upload": bool}

        Returns:
            Dict với 'success', 'result' (report markdown), 'report_url',
            'confidence', 'sources_collected'.
        """
        ctx = context or {}
        upload = ctx.get("upload", True)
        sources = ctx.get("sources") or COLLECT_SOURCES

        result = self.run(upload=upload, sources=sources)
        return {
            "success": result.get("success", False),
            "result": result.get("report", ""),
            "report_url": result.get("report_url"),
            "sources_collected": result.get("sources_collected", []),
            "confidence": 0.9 if result.get("success") else 0.1,
            "error": result.get("error"),
        }

    def _tool_by_name(self, name: str) -> Optional[BaseTool]:
        for t in self.tools:
            if t.get_name() == name:
                return t
        return None

    def _collect(self, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run each collection tool, tolerating individual failures."""
        sources = sources or COLLECT_SOURCES
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        raw: Dict[str, Any] = {}

        if "news" in sources:
            tool = self._tool_by_name("news_search")
            if tool:
                res = tool.execute(query="AI OR artificial intelligence OR LLM OR machine learning", max_records=15, timespan="1day")
                raw["news"] = res.result if res.success else {"error": res.error}

        if "arxiv" in sources:
            tool = self._tool_by_name("arxiv_search")
            if tool:
                res = tool.execute(
                    keyword="AI OR LLM OR agent OR machine learning",
                    categories="cs.AI,cs.CL,cs.LG,cs.CV,cs.SE",
                    days=2,
                    limit=10,
                )
                raw["arxiv"] = res.result if res.success else {"error": res.error}

        if "github" in sources:
            tool = self._tool_by_name("github_search")
            if tool:
                res = tool.execute(min_stars=50, days=1, limit=5)
                raw["github"] = res.result if res.success else {"error": res.error}

        if "huggingface" in sources:
            tool = self._tool_by_name("huggingface_search")
            if tool:
                res = tool.execute(resource_type="both", sort="trending", limit=10)
                raw["huggingface"] = res.result if res.success else {"error": res.error}

        logger.info("daily_research_collected", sources=list(raw.keys()), date=yesterday)
        return raw

    def _render_data_for_llm(self, raw: Dict[str, Any]) -> str:
        """Flatten collected tool results into a compact text block for the LLM."""
        lines = ["=== COLLECTED RAW DATA ==="]
        for source, data in raw.items():
            lines.append(f"\n--- SOURCE: {source} ---")
            lines.append(str(data))
        return "\n".join(lines)

    def _synthesize(self, raw_data_text: str, report_date: str) -> str:
        """Call LLM to produce the final Markdown report."""
        system = REPORT_PROMPT.format(report_date=report_date)
        user = f"Today is {report_date}.\n\n{raw_data_text}\n\nGenerate the daily research report now."
        response = self._call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4,
        )
        return response

    def _upload(self, report_md: str, report_date: str) -> Dict[str, Any]:
        """Write report to a temp .md file and upload to Google Drive."""
        upload_tool = self._tool_by_name("google_drive_upload")
        if not upload_tool:
            return {"success": False, "error": "google_drive_upload tool missing"}

        filename = f"daily-research-report-{report_date}.md"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(report_md)
            tmp_path = f.name

        try:
            res = upload_tool.execute(file_path=tmp_path, filename=filename)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if res.success:
            return {"success": True, "file": res.result}
        return {"success": False, "error": res.error}

    def run(self, upload: bool = True, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute the full daily research pipeline.

        Args:
            upload: Upload generated report to Google Drive.
            sources: Subset of sources to collect (default: all).

        Returns:
            Dict with report markdown, drive upload result, and success flag.
        """
        report_date = datetime.utcnow().strftime("%Y-%m-%d")
        result: Dict[str, Any] = {"date": report_date, "success": False}

        try:
            raw = self._collect(sources)
            result["sources_collected"] = list(raw.keys())

            raw_text = self._render_data_for_llm(raw)
            report_md = self._synthesize(raw_text, report_date)
            report_md = report_md.strip()
            if report_md.startswith("```"):
                report_md = report_md.split("\n", 1)[-1].rsplit("```", 1)[0]
            result["report"] = report_md

            if upload:
                upload_res = self._upload(report_md, report_date)
                result["upload"] = upload_res
                if upload_res.get("success"):
                    result["report_url"] = upload_res["file"].get("link") or upload_res["file"].get("url")

            result["success"] = True
        except Exception as e:
            logger.error("daily_research_failed", error=str(e))
            result["error"] = str(e)

        return result
