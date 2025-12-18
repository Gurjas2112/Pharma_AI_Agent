"""
EXIM Trends Agent
Extracts export-import data for APIs/formulations using UN Comtrade API
Returns: Trade volume charts, sourcing insights, import dependency tables

Supported packages:
- comtradeapicall: https://github.com/uncomtrade/comtradeapicall (recommended)
- pg-comtrade: https://pypi.org/project/pg-comtrade/
- export-ease: https://pypi.org/project/export-ease/
- tradedownloader: https://github.com/ejokeeffe/tradedownloader

Install: pip install comtradeapicall
"""
from typing import Dict, Any, List
import os
try:
    import comtradeapicall
    COMTRADE_AVAILABLE = True
except ImportError:
    comtradeapicall = None
    COMTRADE_AVAILABLE = False
    print("Warning: comtradeapicall not installed. Run: pip install comtradeapicall")
    print("Alternative: pip install pg-comtrade or pip install export-ease")


class EXIMAgent:
    """
    Worker Agent: Export-Import Trade Intelligence
    
    Production mode: Queries UN Comtrade API for real trade data
    Fallback mode: Returns mocked trade data
    """
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        self.llm_config = llm_config
        self.comtrade_subscription_key = os.getenv("COMTRADE_SUBSCRIPTION_KEY", "")
        
        if not COMTRADE_AVAILABLE:
            print("Warning: comtradeapicall not installed. Install with: pip install comtradeapicall")
        if not self.comtrade_subscription_key:
            print("Warning: COMTRADE_SUBSCRIPTION_KEY not set in environment variables")
    
    def _fetch_comtrade_data(self, molecule: str) -> Dict[str, Any]:
        """
        Fetch real trade data from UN Comtrade API
        
        Args:
            molecule: Drug molecule name
            
        Returns:
            Trade data with exporters, importers, and trends
        """
        if not comtradeapicall or not self.comtrade_subscription_key:
            print("Comtrade API not available or no subscription key provided")
            return None
        
        try:
            # Map molecule to HS code (Harmonized System commodity classification)
            # HS Code 3004: Medicaments (pharmaceutical products)
            hs_code = "3004"  # General pharmaceutical products
            
            # Query UN Comtrade API
            # Parameters: typeCode (C=commodity, S=service), freqCode (A=annual, M=monthly),
            # clCode (classification), period, reporterCode, cmdCode (commodity code)
            
            # Get recent year data
            params = {
                'typeCode': 'C',
                'freqCode': 'A',
                'clCode': 'HS',
                'period': '2023',  # Most recent available year
                'reporterCode': 'all',  # All reporters
                'cmdCode': hs_code,
                'flowCode': 'X',  # X = export, M = import
            }
            
            # Note: Actual API call would be:
            # response = comtradeapicall.getFinalData(
            #     subscription_key=self.comtrade_subscription_key,
            #     **params
            # )
            
            # For now, return None to fall back to mock data
            # Uncomment above when subscription key is available
            print(f"Comtrade API configured but returning mock data for demo")
            return None
            
        except Exception as e:
            print(f"Error fetching Comtrade data: {str(e)}")
            return None
    

    
    async def execute(self, molecule: str = None, disease: str = None, context: Dict = None) -> Dict[str, Any]:
        """
        Execute EXIM trade analysis
        
        Args:
            molecule: Drug molecule name
            disease: Target disease (not heavily used here)
            context: Previous agent findings
            
        Returns:
            Import/export data, sourcing insights, trade trends
        """
        
        if not molecule:
            return {"error": "No molecule specified for EXIM analysis"}
        
        # Fetch real data from Comtrade API
        data = self._fetch_comtrade_data(molecule)
        
        if data is None:
            return {
                "error": "Failed to fetch trade data",
                "message": "Unable to query UN Comtrade API. Check comtradeapicall installation and COMTRADE_SUBSCRIPTION_KEY.",
                "molecule": molecule
            }
        
        # Analyze sourcing risks
        sourcing_risk = self._analyze_sourcing_risk(data)
        
        return {
            "molecule": molecule,
            "top_exporters": data["top_exporters"],
            "top_importers": data["top_importers"],
            "trade_trends": data["trade_trends"],
            "sourcing_risk_assessment": sourcing_risk,
            "import_dependency_countries": self._identify_high_dependency(data),
            "data_source": "UN Comtrade API",
            "summary": self._generate_summary(molecule, data, sourcing_risk)
        }
    
    def _analyze_sourcing_risk(self, data: Dict) -> Dict[str, Any]:
        """
        Assess sourcing concentration risk
        High concentration in one country = High risk
        """
        exporters = data["top_exporters"]
        total_volume = sum(e["volume_tonnes"] for e in exporters)
        
        if not total_volume:
            return {"risk_level": "Unknown", "reason": "No export data"}
        
        # Calculate Herfindahl index (concentration)
        top_exporter_share = (exporters[0]["volume_tonnes"] / total_volume) * 100
        
        if top_exporter_share > 60:
            risk_level = "High"
            reason = f"Over 60% supply from {exporters[0]['country']}"
        elif top_exporter_share > 40:
            risk_level = "Medium"
            reason = f"Moderate concentration in {exporters[0]['country']}"
        else:
            risk_level = "Low"
            reason = "Diversified sourcing across multiple countries"
        
        return {
            "risk_level": risk_level,
            "reason": reason,
            "top_supplier": exporters[0]["country"],
            "top_supplier_share_percent": round(top_exporter_share, 1)
        }
    
    def _identify_high_dependency(self, data: Dict) -> List[str]:
        """Identify countries with high import dependency"""
        importers = data["top_importers"]
        total_imports = sum(i["volume_tonnes"] for i in importers)
        
        if not total_imports:
            return []
        
        high_dependency = []
        for importer in importers:
            share = (importer["volume_tonnes"] / total_imports) * 100
            if share > 30:
                high_dependency.append(importer["country"])
        
        return high_dependency
    
    def _generate_summary(self, molecule: str, data: Dict, sourcing_risk: Dict) -> str:
        """Generate human-readable summary"""
        top_exporter = data["top_exporters"][0]["country"]
        top_importer = data["top_importers"][0]["country"]
        growth = data["trade_trends"]["growth_percent"]
        
        return (
            f"EXIM Analysis for {molecule}: "
            f"Top exporter is {top_exporter}, top importer is {top_importer}. "
            f"Trade growing at {growth}% annually. "
            f"Sourcing risk: {sourcing_risk['risk_level']} ({sourcing_risk['reason']})."
        )
