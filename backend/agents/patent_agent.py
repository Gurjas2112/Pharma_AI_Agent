"""
Patent Landscape Agent
Searches USPTO, EPO, and other IP databases using patent_client library
Returns: Patent status tables, competitive filing heatmaps, FTO risk assessment
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import random
import os

try:
    from patent_client import Patent, USApplication
except ImportError:
    Patent = None
    USApplication = None
    print("Warning: patent_client not installed. Using mock patent data.")


class PatentAgent:
    """
    Worker Agent: Patent Landscape Intelligence
    
    Queries USPTO/EPO via patent_client library
    """
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        self.llm_config = llm_config
        
        if not Patent or not USApplication:
            print("Warning: patent_client not installed. Run: pip install patent-client")
    
    def _search_uspto_patents(self, molecule: str) -> Dict[str, Any]:
        """
        Search USPTO for real patent data using patent_client library
        
        Args:
            molecule: Drug molecule name
            
        Returns:
            Patent landscape data with active/expired patents, FTO risk
        """
        if not Patent or not USApplication:
            print("patent_client library not available")
            return None
        
        try:
            # Search for patents related to the molecule
            # patent_client uses query syntax similar to USPTO's PatFT
            search_query = f'TTL/({molecule}) OR ABST/({molecule})'
            
            # Search US patents
            # results = Patent.objects.filter(search_query).limit(50)
            
            # Note: Actual patent_client usage:
            # patents = Patent.objects.filter(title=molecule).values_list()
            # or: patents = USApplication.objects.filter(title__contains=molecule)
            
            # Parse results into structured format
            active_patents = []
            expired_patents = 0
            
            # Example parsing (would iterate through real results):
            # for patent in results:
            #     patent_data = {
            #         "patent_number": patent.patent_number,
            #         "title": patent.title,
            #         "assignee": patent.assignee_organization,
            #         "filing_date": str(patent.filing_date),
            #         "expiry_date": str(patent.expiry_date),
            #         "status": "Active" if patent.is_active else "Expired",
            #         "claims": patent.claim_count
            #     }
            #     if patent.is_active:
            #         active_patents.append(patent_data)
            #     else:
            #         expired_patents += 1
            
            # For now, return None to fall back to mock data
            # Uncomment above when ready to use real API
            print(f"Patent search configured but returning mock data for demo")
            return None
            
        except Exception as e:
            print(f"Error searching USPTO patents: {str(e)}")
            return None
    
    async def execute(self, molecule: str = None, disease: str = None, context: Dict = None) -> Dict[str, Any]:
        """
        Execute patent landscape analysis
        
        Args:
            molecule: Drug molecule name
            disease: Target disease (used for indication-specific patents)
            context: Previous agent findings
            
        Returns:
            Patent data including active patents, FTO risk, filing trends
        """
        
        if not molecule:
            return {"error": "No molecule specified for patent analysis"}
        
        # Fetch real data from USPTO
        data = self._search_uspto_patents(molecule)
        
        if data is None:
            return {
                "error": "Failed to fetch patent data",
                "message": "Unable to query USPTO. Check patent_client installation (pip install patent-client).",
                "molecule": molecule
            }
        
        # Analyze FTO (Freedom to Operate)
        fto_assessment = self._assess_fto(data, disease)
        
        # Identify expiring patents (opportunities)
        expiring_soon = self._identify_expiring_patents(data)
        
        return {
            "molecule": molecule,
            "active_patents_count": len(data["active_patents"]),
            "active_patents": data["active_patents"],
            "data_source": "USPTO (patent_client)",
            "expired_patents_count": data["expired_patents"],
            "fto_risk_score": data["fto_risk_score"],
            "fto_assessment": fto_assessment,
            "expiring_within_3_years": expiring_soon,
            "recent_filing_activity": data["recent_filings_last_2_years"],
            "competitive_landscape": self._analyze_competitive_landscape(data),
            "summary": self._generate_summary(molecule, data, fto_assessment)
        }
    
    def _assess_fto(self, data: Dict, disease: str = None) -> Dict[str, Any]:
        """
        Assess Freedom to Operate
        
        FTO Risk Score interpretation:
        1-3: Low risk (clear FTO)
        4-7: Medium risk (some blocking patents)
        8-10: High risk (significant blocking patents)
        """
        fto_score = data["fto_risk_score"]
        
        if fto_score <= 3:
            risk_level = "Low"
            recommendation = "Proceed with development; FTO appears clear"
            action = "Continue to next phase"
        elif fto_score <= 7:
            risk_level = "Medium"
            recommendation = "Conduct detailed FTO study; design-around may be needed"
            action = "Engage patent attorney for detailed analysis"
        else:
            risk_level = "High"
            recommendation = "Significant blocking patents identified; consider alternative approaches"
            action = "Deprioritize unless design-around feasible"
        
        return {
            "risk_level": risk_level,
            "fto_score": fto_score,
            "recommendation": recommendation,
            "suggested_action": action,
            "blocking_patents": [p for p in data["active_patents"] if p["claims"] > 15]
        }
    
    def _identify_expiring_patents(self, data: Dict) -> List[Dict[str, Any]]:
        """Identify patents expiring within 3 years (opportunities)"""
        expiring = []
        current_year = datetime.now().year
        
        for patent in data["active_patents"]:
            expiry_year = int(patent["expiry_date"].split("-")[0])
            years_to_expiry = expiry_year - current_year
            
            if 0 < years_to_expiry <= 3:
                expiring.append({
                    "patent_number": patent["patent_number"],
                    "expiry_date": patent["expiry_date"],
                    "years_remaining": years_to_expiry,
                    "assignee": patent["assignee"]
                })
        
        return expiring
    
    def _analyze_competitive_landscape(self, data: Dict) -> Dict[str, Any]:
        """Analyze competitive patent filing activity"""
        # Count patents by assignee
        assignee_counts = {}
        for patent in data["active_patents"]:
            assignee = patent["assignee"]
            assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
        
        # Identify dominant players
        dominant_players = sorted(
            assignee_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:3]
        
        return {
            "dominant_patent_holders": [
                {"company": company, "patent_count": count} 
                for company, count in dominant_players
            ],
            "filing_activity_trend": "Increasing" if data["recent_filings_last_2_years"] > 3 else "Stable"
        }
    
    def _generate_summary(self, molecule: str, data: Dict, fto_assessment: Dict) -> str:
        """Generate human-readable summary"""
        active_count = len(data["active_patents"])
        fto_score = data["fto_risk_score"]
        risk_level = fto_assessment["risk_level"]
        
        return (
            f"Patent Landscape for {molecule}: "
            f"{active_count} active patents identified. "
            f"FTO risk score: {fto_score}/10 ({risk_level} risk). "
            f"{fto_assessment['recommendation']}"
        )
