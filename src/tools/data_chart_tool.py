"""Data chart tool — generate charts from data using matplotlib (free, no API key)."""

import os
import json
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class DataChartTool(BaseTool):
    """Generate charts (bar, line, pie, scatter) from structured data.

    Uses matplotlib (free, no API key). Saves chart as PNG file.
    Works in Streamlit/Chainlit prod via st.image() / cl.Image().
    """

    def get_name(self) -> str:
        return "data_chart"

    def get_description(self) -> str:
        return (
            "Generate a chart (bar, line, pie, or scatter) from structured data and save as PNG. "
            "Free (matplotlib, no API key). "
            "Input: chart_type, title, labels (x-axis categories), values (y-axis numbers), "
            "optional series for multi-series charts. Returns file path to the PNG."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie", "scatter"],
                    "description": "Type of chart to generate",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "X-axis labels / categories",
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Y-axis values (must match labels length for single series)",
                },
                "series": {
                    "type": "object",
                    "description": "Multi-series: {series_name: [values...]}. Optional, overrides 'values'.",
                },
                "x_label": {"type": "string", "description": "X-axis label (optional)"},
                "y_label": {"type": "string", "description": "Y-axis label (optional)"},
                "output_dir": {
                    "type": "string",
                    "description": "Directory to save PNG (default: ./output/charts)",
                    "default": "./output/charts",
                },
            },
            "required": ["chart_type", "title", "labels"],
        }

    def execute(
        self,
        chart_type: str,
        title: str,
        labels: List[str],
        values: Optional[List[float]] = None,
        series: Optional[Dict[str, List[float]]] = None,
        x_label: str = "",
        y_label: str = "",
        output_dir: str = "./output/charts",
        **kwargs,
    ) -> ToolResult:
        """Generate and save a chart."""
        try:
            import matplotlib
            matplotlib.use("Agg")  # Non-interactive backend for prod
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError as e:
            return ToolResult(success=False, error=f"matplotlib not installed: {e}")

        try:
            os.makedirs(output_dir, exist_ok=True)

            fig, ax = plt.subplots(figsize=(10, 6))

            if series:
                # Multi-series chart
                x = np.arange(len(labels))
                width = 0.8 / len(series)
                for i, (name, vals) in enumerate(series.items()):
                    offset = (i - len(series) / 2 + 0.5) * width
                    if chart_type == "bar":
                        ax.bar(x + offset, vals, width, label=name)
                    elif chart_type == "line":
                        ax.plot(x, vals, marker="o", label=name)
                    elif chart_type == "scatter":
                        ax.scatter(x, vals, label=name)
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=30, ha="right")
                ax.legend()
            else:
                if not values:
                    return ToolResult(success=False, error="'values' required when 'series' not provided")
                if len(values) != len(labels):
                    return ToolResult(
                        success=False,
                        error=f"labels ({len(labels)}) and values ({len(values)}) length mismatch",
                    )

                if chart_type == "bar":
                    ax.bar(labels, values)
                elif chart_type == "line":
                    ax.plot(labels, values, marker="o", linewidth=2)
                elif chart_type == "pie":
                    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
                    ax.axis("equal")
                elif chart_type == "scatter":
                    ax.scatter(range(len(labels)), values)
                    ax.set_xticks(range(len(labels)))
                    ax.set_xticklabels(labels, rotation=30, ha="right")
                else:
                    return ToolResult(success=False, error=f"Unknown chart_type: {chart_type}")

            ax.set_title(title, fontsize=14, fontweight="bold")
            if x_label and chart_type != "pie":
                ax.set_xlabel(x_label)
            if y_label and chart_type != "pie":
                ax.set_ylabel(y_label)

            plt.tight_layout()

            # Sanitize filename
            safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:50]
            filename = f"{safe_title}_{chart_type}.png"
            filepath = os.path.join(output_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            plt.close(fig)

            file_size = os.path.getsize(filepath)
            logger.info("chart_generated", chart_type=chart_type, filepath=filepath, size=file_size)

            return ToolResult(
                success=True,
                result={
                    "file_path": os.path.abspath(filepath),
                    "filename": filename,
                    "chart_type": chart_type,
                    "title": title,
                    "size_bytes": file_size,
                },
                metadata={"chart_type": chart_type, "series_count": len(series) if series else 1},
            )
        except Exception as e:
            logger.error("chart_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
