"""Tools module for agent capabilities."""

from src.tools.base_tool import BaseTool, ToolResult
from src.tools.web_search_tool import WebSearchTool
from src.tools.web_scrape_tool import WebScrapeTool
from src.tools.json_processor_tool import JsonProcessorTool
from src.tools.markdown_generator_tool import MarkdownGeneratorTool
from src.tools.pdf_generator_tool import PDFGeneratorTool
from src.tools.docx_generator_tool import DocxGeneratorTool
from src.tools.google_drive_upload_tool import GoogleDriveUploadTool
from src.tools.google_drive_download_tool import GoogleDriveDownloadTool
from src.tools.diagram_generator_tool import DiagramGeneratorTool
from src.tools.lark_send_message_tool import LarkSendMessageTool
from src.tools.lark_file_tool import LarkFileDownloadTool, LarkFileUploadTool
from src.tools.file_extractor_tool import FileExtractorTool
from src.tools.arxiv_papers_tool import ArxivSearchTool
from src.tools.hf_tool import HuggingFaceTool
from src.tools.github_trending_tool import GitHubRepoTool
from src.tools.wikipedia_tool import WikipediaTool
from src.tools.news_search_tool import NewsSearchTool
from src.tools.stackoverflow_tool import StackOverflowTool
from src.tools.youtube_transcript_tool import YouTubeTranscriptTool
from src.tools.code_snippet_tool import CodeSnippetTool
from src.tools.data_chart_tool import DataChartTool
from src.tools.comparison_table_tool import ComparisonTableTool
from src.tools.mindmap_generator_tool import MindmapGeneratorTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "WebSearchTool",
    "WebScrapeTool",
    "JsonProcessorTool",
    "MarkdownGeneratorTool",
    "PDFGeneratorTool",
    "DocxGeneratorTool",
    "GoogleDriveUploadTool",
    "GoogleDriveDownloadTool",
    "DiagramGeneratorTool",
    "LarkSendMessageTool",
    "LarkFileDownloadTool",
    "LarkFileUploadTool",
    "FileExtractorTool",
    # Research tools (free, no API key required)
    "ArxivSearchTool",
    "HuggingFaceTool",
    "GitHubRepoTool",
    "WikipediaTool",
    "NewsSearchTool",
    "StackOverflowTool",
    "YouTubeTranscriptTool",
    "CodeSnippetTool",
    # Visualization & analysis tools (free)
    "DataChartTool",
    "ComparisonTableTool",
    "MindmapGeneratorTool",
]
