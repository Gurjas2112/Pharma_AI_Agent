"""
Visualization Service for PharmaAI Reports
Generates charts, graphs, heat maps for professional analytics reports
"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any
import os
from datetime import datetime


class VisualizationService:
    """
    Service for generating professional data visualizations
    Supports: Bar charts, Pie charts, Histograms, Heat maps
    """
    
    def __init__(self, output_dir: str = "backend/reports/charts"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Professional color scheme
        self.colors = {
            'primary': '#2E86AB',
            'secondary': '#A23B72',
            'success': '#27AE60',
            'warning': '#F39C12',
            'danger': '#E74C3C',
            'info': '#3498DB',
            'palette': ['#2E86AB', '#F18F01', '#C73E1D', '#6A994E', '#A23B72']
        }
    
    def generate_market_size_chart(self, market_data: Dict, report_id: str) -> str:
        """
        Generate bar chart showing market size by therapy area
        
        Args:
            market_data: Dictionary with therapy area market sizes
            report_id: Report identifier for filename
            
        Returns:
            Path to generated chart image
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Sample data structure
        therapy_areas = ['Respiratory', 'CNS', 'Oncology', 'Cardiology']
        market_sizes = [1.2, 0.9, 2.1, 1.5]  # USD Billion
        
        # Extract from market_data if available
        if isinstance(market_data, dict) and 'therapy_breakdown' in market_data:
            therapy_areas = list(market_data['therapy_breakdown'].keys())
            market_sizes = list(market_data['therapy_breakdown'].values())
        
        bars = ax.bar(therapy_areas, market_sizes, color=self.colors['primary'], alpha=0.8)
        
        ax.set_ylabel('Market Size (USD Billion)', fontsize=12, fontweight='bold')
        ax.set_xlabel('Therapy Area', fontsize=12, fontweight='bold')
        ax.set_title('Market Size by Therapy Area (USD Billion)', fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'${height:.2f}B',
                   ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{report_id}_market_bar.png")
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def generate_patent_expiry_histogram(self, patent_data: Dict, report_id: str) -> str:
        """
        Generate histogram showing patent expiry year distribution
        
        Args:
            patent_data: Dictionary with patent expiry information
            report_id: Report identifier
            
        Returns:
            Path to histogram image
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Sample data
        years = [2025, 2026, 2026, 2027, 2027, 2028, 2028, 2029, 2030]
        
        # Extract from patent_data if available
        if isinstance(patent_data, dict) and 'expiry_years' in patent_data:
            years = patent_data['expiry_years']
        
        bins = range(min(years), max(years) + 2)
        ax.hist(years, bins=bins, color=self.colors['info'], alpha=0.7, edgecolor='black')
        
        ax.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax.set_ylabel('Number of Patents', fontsize=12, fontweight='bold')
        ax.set_title('Patent Expiry Year Distribution', fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{report_id}_patent_histogram.png")
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def generate_clinical_phase_pie(self, clinical_data: Dict, report_id: str) -> str:
        """
        Generate pie chart showing clinical trial phase distribution
        
        Args:
            clinical_data: Dictionary with phase distribution
            report_id: Report identifier
            
        Returns:
            Path to pie chart image
        """
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Sample data
        phases = ['Phase I', 'Phase II', 'Phase III', 'Phase IV']
        counts = [5, 9, 3, 1]
        
        # Extract from clinical_data if available
        if isinstance(clinical_data, dict) and 'phase_distribution' in clinical_data:
            phase_dist = clinical_data['phase_distribution']
            phases = list(phase_dist.keys())
            counts = list(phase_dist.values())
        
        # Filter out zero counts
        filtered_data = [(p, c) for p, c in zip(phases, counts) if c > 0]
        if filtered_data:
            phases, counts = zip(*filtered_data)
        
        colors = self.colors['palette'][:len(phases)]
        
        wedges, texts, autotexts = ax.pie(
            counts, 
            labels=phases, 
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'fontsize': 11, 'fontweight': 'bold'}
        )
        
        ax.set_title('Clinical Trial Phase Distribution', fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{report_id}_clinical_pie.png")
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def generate_import_dependency_heatmap(self, exim_data: Dict, report_id: str) -> str:
        """
        Generate heat map showing API import dependency by country
        
        Args:
            exim_data: Dictionary with import dependency data
            report_id: Report identifier
            
        Returns:
            Path to heat map image
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Sample data
        countries = ['China', 'Germany', 'India', 'USA']
        dependency_levels = [85, 45, 25, 15]  # Percentage
        
        # Extract from exim_data if available
        if isinstance(exim_data, dict) and 'import_dependency' in exim_data:
            countries = list(exim_data['import_dependency'].keys())
            dependency_levels = list(exim_data['import_dependency'].values())
        
        # Create color map
        colors_map = []
        for dep in dependency_levels:
            if dep >= 70:
                colors_map.append('#E74C3C')  # Red - Very High
            elif dep >= 50:
                colors_map.append('#F39C12')  # Orange - High
            elif dep >= 30:
                colors_map.append('#F1C40F')  # Yellow - Moderate
            else:
                colors_map.append('#27AE60')  # Green - Low
        
        bars = ax.barh(countries, dependency_levels, color=colors_map, alpha=0.8)
        
        ax.set_xlabel('Import Dependency (%)', fontsize=12, fontweight='bold')
        ax.set_title('API Import Dependency Heat Map', fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        
        # Add value labels
        for i, (bar, dep) in enumerate(zip(bars, dependency_levels)):
            width = bar.get_width()
            label = "Very High" if dep >= 70 else "High" if dep >= 50 else "Moderate" if dep >= 30 else "Low"
            ax.text(width + 2, bar.get_y() + bar.get_height()/2.,
                   f'{dep}% ({label})',
                   ha='left', va='center', fontweight='bold')
        
        ax.set_xlim(0, 100)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{report_id}_exim_heatmap.png")
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def generate_all_charts(self, findings: Dict, report_id: str) -> Dict[str, str]:
        """
        Generate all charts for a report
        
        Args:
            findings: Raw findings from all agents
            report_id: Report identifier
            
        Returns:
            Dictionary mapping chart type to file path
        """
        charts = {}
        
        try:
            # Market size bar chart
            if 'iqvia' in findings and not findings['iqvia'].get('error'):
                charts['market_bar'] = self.generate_market_size_chart(
                    findings['iqvia'], report_id
                )
        except Exception as e:
            print(f"Error generating market chart: {e}")
        
        try:
            # Patent expiry histogram
            if 'patent' in findings and not findings['patent'].get('error'):
                charts['patent_histogram'] = self.generate_patent_expiry_histogram(
                    findings['patent'], report_id
                )
        except Exception as e:
            print(f"Error generating patent chart: {e}")
        
        try:
            # Clinical trials pie chart
            if 'clinical_trials' in findings and not findings['clinical_trials'].get('error'):
                charts['clinical_pie'] = self.generate_clinical_phase_pie(
                    findings['clinical_trials'], report_id
                )
        except Exception as e:
            print(f"Error generating clinical chart: {e}")
        
        try:
            # EXIM heat map
            if 'exim' in findings and not findings['exim'].get('error'):
                charts['exim_heatmap'] = self.generate_import_dependency_heatmap(
                    findings['exim'], report_id
                )
        except Exception as e:
            print(f"Error generating EXIM chart: {e}")
        
        return charts
