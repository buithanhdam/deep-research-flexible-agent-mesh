"""Mindmap generator tool — create concept maps from structured data (graphviz, free)."""

import os
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class MindmapGeneratorTool(BaseTool):
    """Generate a mindmap / concept map from a topic and sub-topics.

    Uses graphviz (free, no API key; requires graphviz binary installed).
    Input: central_topic, branches (list of {label, children: [...]}).
    Saves as PNG.
    """

    def get_name(self) -> str:
        return "mindmap_generator"

    def get_description(self) -> str:
        return (
            "Generate a mindmap / concept map from a central topic and branches. "
            "Free (graphviz, no API key; requires graphviz system binary). "
            "Input: central_topic, branches=[{label, children=[...]}]. "
            "Returns PNG file path."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "central_topic": {"type": "string", "description": "Central node label"},
                "branches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "children": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "description": "Branches radiating from the center",
                },
                "output_dir": {"type": "string", "default": "./output/mindmaps"},
            },
            "required": ["central_topic", "branches"],
        }

    def execute(
        self,
        central_topic: str,
        branches: List[Dict[str, Any]],
        output_dir: str = "./output/mindmaps",
        **kwargs,
    ) -> ToolResult:
        """Generate a mindmap PNG."""
        try:
            from graphviz import Digraph
        except ImportError as e:
            return ToolResult(success=False, error=f"graphviz package not installed: {e}")

        try:
            os.makedirs(output_dir, exist_ok=True)

            dot = Digraph(comment=central_topic, format="png")
            dot.attr(rankdir="LR", bgcolor="white", fontname="Helvetica")
            dot.attr("node", fontname="Helvetica", style="filled", shape="box")

            # Central node
            center_id = "center"
            dot.node(center_id, central_topic, fillcolor="#4A90D9", fontcolor="white", fontsize="16")

            colors = ["#E8F5E9", "#FFF3E0", "#E3F2FD", "#FCE4EC", "#F3E5F5", "#E0F7FA"]

            for i, branch in enumerate(branches):
                label = branch.get("label", f"Branch {i+1}")
                branch_id = f"b{i}"
                color = colors[i % len(colors)]
                dot.node(branch_id, label, fillcolor=color, fontsize="13")
                dot.edge(center_id, branch_id, color="#666666")

                children = branch.get("children", [])
                for j, child in enumerate(children):
                    child_id = f"b{i}_c{j}"
                    dot.node(child_id, str(child), fillcolor="white", fontsize="11")
                    dot.edge(branch_id, child_id, color="#AAAAAA")

            safe_topic = "".join(c if c.isalnum() or c in "-_" else "_" for c in central_topic)[:50]
            filename = f"{safe_topic}_mindmap"
            filepath = os.path.join(output_dir, filename)
            rendered = dot.render(filepath, cleanup=True)
            # graphviz appends .png
            if not rendered.endswith(".png"):
                rendered = rendered + ".png"

            file_size = os.path.getsize(rendered) if os.path.exists(rendered) else 0
            logger.info("mindmap_generated", filepath=rendered, branches=len(branches))

            return ToolResult(
                success=True,
                result={
                    "file_path": os.path.abspath(rendered),
                    "filename": os.path.basename(rendered),
                    "central_topic": central_topic,
                    "branch_count": len(branches),
                    "size_bytes": file_size,
                },
                metadata={"branches": len(branches)},
            )
        except Exception as e:
            logger.error("mindmap_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
