"""
Clinical Trials Agent
Fetches trial pipeline data from ClinicalTrials.gov using pytrials library
Returns: Tables of active trials, sponsor profiles, trial phase distributions
"""
from typing import Dict, Any, List
import random
import os

try:
    from pytrials.client import ClinicalTrials as CTGovAPI
except ImportError:
    CTGovAPI = None
    print("Warning: pytrials not installed. Using mock clinical trials data.")


class ClinicalTrialsAgent:
    """
    Worker Agent: Clinical Trials Intelligence
    
    Production mode: Queries ClinicalTrials.gov via pytrials library
    Fallback mode: Returns mocked clinical trial data
    """
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        self.llm_config = llm_config
        
        # Initialize ClinicalTrials.gov API client
        if CTGovAPI:
            self.ct_api = CTGovAPI()
        else:
            self.ct_api = None
            print("Warning: pytrials not installed. Install with: pip install pytrials")
    
    def _fetch_clinicaltrials_data(self, molecule: str, disease: str = None) -> Dict[str, Any]:
        """
        Fetch real clinical trials data from ClinicalTrials.gov
        
        Args:
            molecule: Drug molecule name
            disease: Target disease/indication (optional)
            
        Returns:
            Clinical trials data with active trials, phase distribution, sponsors
        """
        if not self.ct_api:
            print("pytrials library not available or in mock mode")
            return None
        
        try:
            # Search for trials using pytrials
            # Search by intervention (drug name)
            search_params = {
                'search_expr': molecule,
                'max_rnk': 100  # Maximum number of results
            }
            
            # Add disease/condition filter if provided
            if disease:
                search_params['cond'] = disease
            
            # Execute search with valid field names for ClinicalTrials.gov API
            # Common valid fields: NCTId, BriefTitle, LeadSponsorName, Phase, OverallStatus, etc.
            trials = self.ct_api.get_study_fields(
                search_expr=molecule,
                fields=['NCTId', 'BriefTitle', 'LeadSponsorName', 'Phase', 
                        'OverallStatus', 'StartDate', 'Condition'],
                max_rnk=100
            )
            
            if not trials or len(trials.get('StudyFieldsResponse', {}).get('StudyFields', [])) == 0:
                print(f"No trials found for {molecule}")
                return None
            
            # Parse results
            active_trials = []
            phase_distribution = {"Phase 1": 0, "Phase 2": 0, "Phase 3": 0, "Phase 4": 0}
            indications = set()
            
            for trial in trials['StudyFieldsResponse']['StudyFields']:
                # Extract trial data (EnrollmentCount removed as it may not be available)
                trial_data = {
                    "nct_id": trial.get('NCTId', [''])[0],
                    "title": trial.get('BriefTitle', [''])[0],
                    "sponsor": trial.get('LeadSponsorName', [''])[0],
                    "phase": trial.get('Phase', ['Not Applicable'])[0],
                    "status": trial.get('OverallStatus', ['Unknown'])[0],
                    "enrollment": "N/A",  # EnrollmentCount field may not be available
                    "start_date": trial.get('StartDate', [''])[0],
                    "indication": ', '.join(trial.get('Condition', []))
                }
                
                # Count by phase
                phase = trial_data['phase']
                if 'Phase 1' in phase:
                    phase_distribution['Phase 1'] += 1
                elif 'Phase 2' in phase:
                    phase_distribution['Phase 2'] += 1
                elif 'Phase 3' in phase:
                    phase_distribution['Phase 3'] += 1
                elif 'Phase 4' in phase:
                    phase_distribution['Phase 4'] += 1
                
                # Collect indications
                for condition in trial.get('Condition', []):
                    indications.add(condition)
                
                active_trials.append(trial_data)
            
            return {
                "total_active_trials": len(active_trials),
                "trials": active_trials[:10],  # Return top 10
                "phase_distribution": phase_distribution,
                "indication_diversity": list(indications)
            }
            
        except Exception as e:
            print(f"Error fetching ClinicalTrials.gov data: {str(e)}")
            return None
    

    
    async def execute(self, molecule: str = None, disease: str = None, context: Dict = None) -> Dict[str, Any]:
        """
        Execute clinical trials analysis
        
        Args:
            molecule: Drug molecule name
            disease: Target disease (filters trials by indication)
            context: Previous agent findings
            
        Returns:
            Clinical trial data including active trials, phases, sponsors
        """
        
        if not molecule:
            return {"error": "No molecule specified for clinical trials analysis"}
        
        # Fetch real ClinicalTrials.gov data
        data = self._fetch_clinicaltrials_data(molecule, disease)
        
        if data is None:
            return {
                "error": "Failed to fetch clinical trials data",
                "message": "Unable to query ClinicalTrials.gov. Check pytrials installation and API availability.",
                "molecule": molecule
            }
        
        # Filter by disease if specified
        filtered_trials = data["trials"]
        if disease:
            filtered_trials = [
                t for t in data["trials"] 
                if disease.lower() in t["indication"].lower()
            ]
        
        # Analyze saturation
        saturation_analysis = self._analyze_clinical_saturation(data)
        
        # Identify repurposing opportunities
        repurposing_opportunities = self._identify_repurposing_signals(data, disease)
        
        return {
            "data_source": "ClinicalTrials.gov (pytrials)",
            "molecule": molecule,
            "total_active_trials": data["total_active_trials"],
            "trials_sample": filtered_trials[:5],  # Return top 5 for brevity
            "phase_distribution": data["phase_distribution"],
            "indication_diversity": data["indication_diversity"],
            "saturation_analysis": saturation_analysis,
            "repurposing_opportunities": repurposing_opportunities,
            "top_sponsors": self._extract_top_sponsors(data),
            "summary": self._generate_summary(molecule, data, saturation_analysis)
        }
    
    def _generate_synthetic_data(self, molecule: str, disease: str = None) -> Dict[str, Any]:
        """Generate plausible mock clinical trial data"""
        total_trials = random.randint(2, 25)
        
        phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4"]
        statuses = ["Recruiting", "Active", "Completed"]
        sponsors = [
            "NIH", "Johns Hopkins", "Mayo Clinic", "Stanford University",
            "Pfizer", "Novartis", "University of California"
        ]
        indications = [
            disease or "General", "Cancer", "Cardiovascular", "Neurological", "Inflammatory"
        ]
        
        trials = []
        for i in range(min(total_trials, 5)):  # Generate up to 5 sample trials
            trials.append({
                "nct_id": f"NCT{random.randint(10000000, 99999999)}",
                "title": f"{molecule} for {random.choice(indications)}",
                "sponsor": random.choice(sponsors),
                "phase": random.choice(phases),
                "status": random.choice(statuses),
                "enrollment": random.randint(50, 500),
                "start_date": f"202{random.randint(2, 4)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                "indication": random.choice(indications)
            })
        
        phase_dist = {phase: random.randint(0, 8) for phase in phases}
        
        return {
            "total_active_trials": total_trials,
            "trials": trials,
            "phase_distribution": phase_dist,
            "indication_diversity": random.sample(indications, k=min(len(indications), 4))
        }
    
    def _analyze_clinical_saturation(self, data: Dict) -> Dict[str, Any]:
        """
        Analyze if clinical space is saturated
        
        High saturation = many trials = competitive space
        Low saturation = few trials = opportunity
        """
        total_trials = data["total_active_trials"]
        
        if total_trials > 20:
            saturation_level = "High"
            interpretation = "Highly competitive clinical space with many ongoing trials"
            opportunity_score = 3  # Low opportunity
        elif total_trials > 10:
            saturation_level = "Medium"
            interpretation = "Moderate clinical activity; room for differentiation"
            opportunity_score = 6
        else:
            saturation_level = "Low"
            interpretation = "Low clinical activity; potential white space opportunity"
            opportunity_score = 9  # High opportunity
        
        return {
            "saturation_level": saturation_level,
            "interpretation": interpretation,
            "opportunity_score": opportunity_score,
            "total_active_trials": total_trials
        }
    
    def _identify_repurposing_signals(self, data: Dict, target_disease: str = None) -> List[Dict[str, str]]:
        """
        Identify potential repurposing opportunities based on trial diversity
        
        If molecule is being tested in multiple indications → repurposing potential
        """
        indications = data["indication_diversity"]
        
        opportunities = []
        for indication in indications:
            if target_disease and indication.lower() == target_disease.lower():
                continue  # Skip original indication
            
            opportunities.append({
                "new_indication": indication,
                "rationale": f"Active clinical trials exploring {indication}",
                "confidence": "Medium" if len(data["trials"]) > 5 else "Low"
            })
        
        return opportunities[:3]  # Return top 3
    
    def _extract_top_sponsors(self, data: Dict) -> List[Dict[str, Any]]:
        """Extract top sponsors by trial count"""
        sponsor_counts = {}
        for trial in data["trials"]:
            sponsor = trial["sponsor"]
            sponsor_counts[sponsor] = sponsor_counts.get(sponsor, 0) + 1
        
        top_sponsors = sorted(
            sponsor_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        return [
            {"sponsor": sponsor, "trial_count": count}
            for sponsor, count in top_sponsors
        ]
    
    def _generate_summary(self, molecule: str, data: Dict, saturation: Dict) -> str:
        """Generate human-readable summary"""
        total_trials = data["total_active_trials"]
        saturation_level = saturation["saturation_level"]
        indication_count = len(data["indication_diversity"])
        
        return (
            f"Clinical Trials Analysis for {molecule}: "
            f"{total_trials} active trials identified. "
            f"Saturation level: {saturation_level}. "
            f"Trials span {indication_count} different indications, suggesting repurposing potential."
        )
