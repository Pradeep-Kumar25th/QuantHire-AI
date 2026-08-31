"""
Export LangGraph workflow visualization to image file
"""
import sys
from pathlib import Path

# Add apps directory to path
apps_dir = Path(__file__).parent.parent.parent
if str(apps_dir) not in sys.path:
    sys.path.insert(0, str(apps_dir))

print("=" * 60)
print("Exporting JD Generation Workflow Graph")
print("=" * 60)
print()

try:
    from agents.jd_generation.state_machine import graph
    
    print("✅ Graph loaded successfully")
    print()
    
    # Get the graph structure
    graph_structure = graph.get_graph()
    
    print(f"Graph has {len(graph_structure.nodes)} nodes")
    print()
    
    # Try to draw the graph
    try:
        from IPython.display import Image, display
        
        # Generate PNG
        png_data = graph_structure.draw_mermaid_png()
        
        # Save to file
        output_file = Path(__file__).parent / "workflow_graph.png"
        with open(output_file, "wb") as f:
            f.write(png_data)
        
        print(f"✅ Graph exported to: {output_file}")
        print()
        
    except ImportError:
        print("⚠️  IPython not available, trying alternative method...")
        
        # Alternative: Export as Mermaid diagram
        try:
            mermaid_code = graph_structure.draw_mermaid()
            
            output_file = Path(__file__).parent / "workflow_graph.mmd"
            with open(output_file, "w") as f:
                f.write(mermaid_code)
            
            print(f"✅ Graph exported as Mermaid diagram to: {output_file}")
            print()
            print("To convert to image:")
            print("1. Visit: https://mermaid.live")
            print("2. Paste the content of workflow_graph.mmd")
            print("3. Download as PNG/SVG")
            print()
            
        except Exception as e:
            print(f"❌ Failed to export as Mermaid: {e}")
    
    # Also print ASCII representation
    print("=" * 60)
    print("Graph Structure (Text)")
    print("=" * 60)
    print()
    
    # List all nodes
    print("Nodes:")
    for i, node in enumerate(graph_structure.nodes, 1):
        node_id = node.id if hasattr(node, 'id') else str(node)
        print(f"  {i}. {node_id}")
    
    print()
    print("Edges:")
    for i, edge in enumerate(graph_structure.edges, 1):
        print(f"  {i}. {edge}")
    
    print()
    print("=" * 60)
    print("✅ Export complete!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
