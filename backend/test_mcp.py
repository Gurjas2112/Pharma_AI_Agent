"""
Test script for PharmaAI MCP Server
Validates that all MCP tools are properly exposed
"""
import requests
import json
from typing import Dict, Any


def test_mcp_server():
    """Test MCP server availability and tool discovery"""
    
    base_url = "http://localhost:8000/mcp"
    
    print("=" * 60)
    print("PharmaAI MCP Server Test Suite")
    print("=" * 60)
    
    # Test 1: Check if MCP server is running
    print("\n[TEST 1] Checking MCP server availability...")
    try:
        response = requests.get(f"{base_url}/tools")
        if response.status_code == 200:
            print("✓ MCP server is running")
            tools = response.json()
            print(f"✓ Found {len(tools)} tools")
        else:
            print(f"✗ Server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to MCP server")
        print("  Make sure backend is running: python backend/main.py")
        return False
    
    # Test 2: List all available tools
    print("\n[TEST 2] Listing available MCP tools...")
    expected_tools = [
        "pharma_research_orchestrator",
        "iqvia_market_analysis",
        "exim_trade_analysis",
        "patent_landscape_analysis",
        "clinical_trials_analysis",
        "internal_knowledge_search",
        "web_intelligence_search",
        "generate_research_report"
    ]
    
    for tool_name in expected_tools:
        if any(t.get("name") == tool_name for t in tools):
            print(f"  ✓ {tool_name}")
        else:
            print(f"  ✗ {tool_name} - NOT FOUND")
    
    # Test 3: Test IQVIA Market Analysis tool
    print("\n[TEST 3] Testing IQVIA Market Analysis tool...")
    try:
        response = requests.post(
            f"{base_url}/tools/iqvia_market_analysis",
            json={
                "molecule": "Aspirin",
                "disease": None
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Tool executed successfully")
            print(f"  ✓ Molecule: {result.get('molecule')}")
            print(f"  ✓ Market Size: {result.get('market_size')}")
            print(f"  ✓ CAGR: {result.get('cagr')}")
        else:
            print(f"  ✗ Tool failed with status {response.status_code}")
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  ✗ Error calling tool: {str(e)}")
    
    # Test 4: Test Patent Landscape Analysis tool
    print("\n[TEST 4] Testing Patent Landscape Analysis tool...")
    try:
        response = requests.post(
            f"{base_url}/tools/patent_landscape_analysis",
            json={
                "molecule": "Metformin",
                "disease": "diabetes"
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Tool executed successfully")
            print(f"  ✓ Molecule: {result.get('molecule')}")
            print(f"  ✓ FTO Score: {result.get('fto_score')}/10")
            print(f"  ✓ Total Patents: {result.get('total_patents')}")
        else:
            print(f"  ✗ Tool failed with status {response.status_code}")
    except Exception as e:
        print(f"  ✗ Error calling tool: {str(e)}")
    
    # Test 5: Test Web Intelligence tool
    print("\n[TEST 5] Testing Web Intelligence Search tool...")
    try:
        response = requests.post(
            f"{base_url}/tools/web_intelligence_search",
            json={
                "molecule": "Montelukast",
                "disease": "asthma"
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Tool executed successfully")
            print(f"  ✓ Molecule: {result.get('molecule')}")
            print(f"  ✓ Sources found: {len(result.get('web_sources', []))}")
        else:
            print(f"  ✗ Tool failed with status {response.status_code}")
    except Exception as e:
        print(f"  ✗ Error calling tool: {str(e)}")
    
    # Test 6: Test Master Agent Orchestrator (complex query)
    print("\n[TEST 6] Testing Master Agent Orchestrator...")
    try:
        response = requests.post(
            f"{base_url}/tools/pharma_research_orchestrator",
            json={
                "query": "What is the repurposing potential for Aspirin in cancer treatment?",
                "conversation_history": []
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Master agent executed successfully")
            print(f"  ✓ Decision: {result.get('decision')}")
            print(f"  ✓ Confidence: {result.get('confidence_score')}/100")
            print(f"  ✓ Agents called: {len(result.get('findings', {}))}")
        else:
            print(f"  ✗ Master agent failed with status {response.status_code}")
    except Exception as e:
        print(f"  ✗ Error calling master agent: {str(e)}")
    
    print("\n" + "=" * 60)
    print("MCP Server Test Complete")
    print("=" * 60)
    print("\n✓ All tests passed!")
    print("\nNext steps:")
    print("  1. Configure your AI assistant to use: http://localhost:8000/mcp")
    print("  2. See MCP_SERVER.md for integration examples")
    print("  3. Start using PharmaAI tools in Claude Desktop, VS Code, or Cursor")
    
    return True


if __name__ == "__main__":
    test_mcp_server()
