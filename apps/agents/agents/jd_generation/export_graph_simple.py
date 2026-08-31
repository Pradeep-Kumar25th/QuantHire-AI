"""
Simple graph export - generates Mermaid diagram
"""
import sys
from pathlib import Path

# Add apps directory to path
apps_dir = Path(__file__).parent.parent.parent
if str(apps_dir) not in sys.path:
    sys.path.insert(0, str(apps_dir))

print("Exporting workflow graph...")

from agents.jd_generation.state_machine import JDGenerationWorkflow

# Create workflow
workflow = JDGenerationWorkflow()

# Get graph
graph_obj = workflow.compiled_graph.get_graph()

# Export as Mermaid
mermaid_code = graph_obj.draw_mermaid()

# Save to file
output_file = Path(__file__).parent / "workflow_graph.mmd"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(mermaid_code)

print(f"✅ Exported to: {output_file}")
print()
print("To view/download as image:")
print("1. Open: https://mermaid.live")
print("2. Paste the content from workflow_graph.mmd")
print("3. Click 'Download PNG' or 'Download SVG'")
