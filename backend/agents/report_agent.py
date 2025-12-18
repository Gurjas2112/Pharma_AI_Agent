"""
Report Generator Agent
Formats synthesized response into polished PDF report with analytics & visualizations
Returns: Professional PDF reports with charts, graphs, heat maps, and app logo
Stores reports in Supabase for historical tracking
"""
from typing import Dict, Any
import os
from datetime import datetime
import json

# Import with better error handling for WeasyPrint's GTK dependencies
HTML = None
CSS = None
Template = None
markdown = None
ReportLab_available = False

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    # Try ReportLab as alternative for Windows
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors as rl_colors
        ReportLab_available = True
        print("✓ Using ReportLab for PDF generation (WeasyPrint not available)")
    except ImportError:
        print(f"⚠️  PDF generation disabled: WeasyPrint unavailable ({e}), ReportLab not installed")

try:
    from jinja2 import Template
except ImportError:
    print("Warning: jinja2 not installed. Template rendering disabled.")

try:
    import markdown
except ImportError:
    print("Warning: markdown not installed. Markdown conversion disabled.")

# Import Supabase service
from services.supabase_client import supabase_service

# Import visualization service
try:
    from agents.visualization_service import VisualizationService
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("Warning: Visualization service not available. Install matplotlib for charts.")


class ReportGeneratorAgent:
    """
    Worker Agent: Report Generation
    
    Converts Master Agent's synthesis into a downloadable PDF report
    Uses Markdown → HTML → PDF conversion via WeasyPrint or ReportLab
    Stores reports in Supabase for historical tracking
    """
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        self.llm_config = llm_config
        self.output_directory = "backend/reports"
        self.logo_path = "App_logo.png"
        self._ensure_output_directory()
        
        # Initialize visualization service
        if VISUALIZATION_AVAILABLE:
            self.viz_service = VisualizationService()
        else:
            self.viz_service = None
    
    def _ensure_output_directory(self):
        """Create reports directory if it doesn't exist"""
        os.makedirs(self.output_directory, exist_ok=True)
    
    async def execute(self, synthesis: Dict = None, raw_findings: Dict = None, **kwargs) -> Dict[str, Any]:
        """
        Execute report generation
        
        Args:
            synthesis: Master Agent's synthesized decision and summary
            raw_findings: Raw data from all Worker Agents
            
        Returns:
            Report metadata including PDF URL and Supabase storage info
        """
        
        if not synthesis:
            return {"error": "No synthesis data provided for report generation"}
        
        # Generate report ID
        report_id = self._generate_report_id()
        
        # Generate visualizations if available
        charts = {}
        if self.viz_service:
            try:
                charts = self.viz_service.generate_all_charts(raw_findings, report_id)
                print(f"✓ Generated {len(charts)} visualization charts")
            except Exception as e:
                print(f"⚠️  Error generating charts: {e}")
        
        # Build Markdown report
        markdown_content = self._build_markdown_report(synthesis, raw_findings)
        
        # Save Markdown file
        markdown_path = os.path.join(self.output_directory, f"{report_id}.md")
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # Convert to PDF with charts
        pdf_path = self._convert_to_pdf(markdown_path, report_id, charts, synthesis, raw_findings)
        
        # Save metadata
        metadata_path = os.path.join(self.output_directory, f"{report_id}_metadata.json")
        metadata = {
            "report_id": report_id,
            "generated_at": datetime.now().isoformat(),
            "decision": synthesis.get("decision"),
            "confidence": synthesis.get("confidence"),
            "molecule": raw_findings.get("iqvia", {}).get("molecule", "Unknown"),
            "disease": raw_findings.get("iqvia", {}).get("therapy_area", "Unknown")
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # Store in Supabase
        supabase_result = await self._store_in_supabase(
            report_id=report_id,
            molecule=metadata["molecule"],
            disease=metadata["disease"],
            decision=metadata["decision"],
            confidence=metadata["confidence"],
            findings=raw_findings,
            pdf_path=pdf_path
        )
        
        return {
            "report_id": report_id,
            "markdown_url": f"/reports/{report_id}.md",
            "pdf_url": f"/reports/{report_id}.pdf",
            "generated_at": metadata["generated_at"],
            "supabase_stored": supabase_result is not None,
            "summary": f"Report generated and stored for {metadata['molecule']}"
        }
    
    async def _store_in_supabase(self, report_id: str, molecule: str, disease: str,
                                 decision: str, confidence: int, findings: dict,
                                 pdf_path: str) -> dict:
        """
        Store report in Supabase reports table
        
        Args:
            report_id: Unique report identifier
            molecule: Drug molecule name
            disease: Disease/indication
            decision: GO/NO-GO/PARTIAL_GO
            confidence: Confidence score (0-100)
            findings: Raw findings from all agents
            pdf_path: Path to generated PDF
            
        Returns:
            Supabase insert result or None
        """
        try:
            # Read PDF binary data
            with open(pdf_path, "rb") as f:
                pdf_binary = f.read()
            
            # Insert into Supabase
            result = await supabase_service.insert_report(
                report_id=report_id,
                molecule=molecule,
                disease=disease,
                decision=decision,
                confidence=confidence,
                findings=findings,
                file_path=pdf_path,
                pdf_binary=pdf_binary
            )
            
            if result:
                print(f"✓ Report {report_id} stored in Supabase")
            else:
                print(f"⚠️  Failed to store report {report_id} in Supabase")
            
            return result
            
        except Exception as e:
            print(f"✗ Error storing report in Supabase: {e}")
            return None
    
    def _generate_report_id(self) -> str:
        """Generate unique report ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"pharma_ai_report_{timestamp}"
    
    def _build_markdown_report(self, synthesis: Dict, raw_findings: Dict) -> str:
        """
        Build comprehensive Markdown report
        
        Structure:
        1. Executive Summary
        2. Decision & Reasoning
        3. Detailed Findings (by Agent)
        4. Recommendations
        5. Appendices
        """
        
        molecule = raw_findings.get("iqvia", {}).get("molecule", "Unknown Molecule")
        decision = synthesis.get("decision", "PENDING")
        reasoning = synthesis.get("reasoning", "No reasoning provided")
        confidence = synthesis.get("confidence", 0)
        
        # Build report
        report = f"""# PharmaAI Research Report
## {molecule} - Innovation Opportunity Assessment

**Report Generated:** {datetime.now().strftime("%B %d, %Y at %H:%M")}

---

## Executive Summary

**Decision:** {decision}  
**Confidence Score:** {confidence}/100  
**Recommendation:** {reasoning}

---

## 1. Market Intelligence (IQVIA)

"""
        
        # Add IQVIA findings
        if "iqvia" in raw_findings:
            iqvia = raw_findings["iqvia"]
            report += f"""
**Market Size:** ${iqvia.get('market_size_usd_million', 'N/A')}M USD  
**Growth Rate (CAGR):** {iqvia.get('cagr_percent', 'N/A')}%  
**Therapy Area:** {iqvia.get('therapy_area', 'N/A')}  
**Competition Intensity:** {iqvia.get('competition_intensity', 'N/A')}  
**Attractiveness Score:** {iqvia.get('market_attractiveness_score', 'N/A')}/100

### Top Competitors
"""
            for comp in iqvia.get("top_competitors", []):
                report += f"- {comp.get('name')}: {comp.get('market_share')}% market share\n"
        
        # Add Patent findings
        report += "\n---\n\n## 2. Patent Landscape\n\n"
        if "patent" in raw_findings:
            patent = raw_findings["patent"]
            fto = patent.get("fto_assessment", {})
            report += f"""
**Active Patents:** {patent.get('active_patents_count', 'N/A')}  
**FTO Risk Score:** {patent.get('fto_risk_score', 'N/A')}/10  
**Risk Level:** {fto.get('risk_level', 'N/A')}  
**Recommendation:** {fto.get('recommendation', 'N/A')}

### Key Patents
"""
            for p in patent.get("active_patents", [])[:3]:
                report += f"- **{p.get('patent_number')}**: {p.get('title')} ({p.get('assignee')})\n"
        
        # Add Clinical Trials findings
        report += "\n---\n\n## 3. Clinical Trials Landscape\n\n"
        if "clinical_trials" in raw_findings:
            ct = raw_findings["clinical_trials"]
            saturation = ct.get("saturation_analysis", {})
            report += f"""
**Total Active Trials:** {ct.get('total_active_trials', 'N/A')}  
**Saturation Level:** {saturation.get('saturation_level', 'N/A')}  
**Opportunity Score:** {saturation.get('opportunity_score', 'N/A')}/10

### Indication Diversity
"""
            for indication in ct.get("indication_diversity", []):
                report += f"- {indication}\n"
            
            report += "\n### Repurposing Opportunities\n"
            for opp in ct.get("repurposing_opportunities", []):
                report += f"- **{opp.get('new_indication')}**: {opp.get('rationale')}\n"
        
        # Add EXIM findings
        report += "\n---\n\n## 4. Trade Intelligence (EXIM)\n\n"
        if "exim" in raw_findings:
            exim = raw_findings["exim"]
            sourcing = exim.get("sourcing_risk_assessment", {})
            report += f"""
**Sourcing Risk:** {sourcing.get('risk_level', 'N/A')}  
**Top Supplier:** {sourcing.get('top_supplier', 'N/A')} ({sourcing.get('top_supplier_share_percent', 'N/A')}%)

### Top Exporters
"""
            for exp in exim.get("top_exporters", []):
                report += f"- {exp.get('country')}: {exp.get('volume_tonnes')} tonnes\n"
        
        # Add Internal Knowledge findings
        report += "\n---\n\n## 5. Internal Knowledge Insights\n\n"
        if "internal_knowledge" in raw_findings:
            kb = raw_findings["internal_knowledge"]
            report += f"**Documents Found:** {kb.get('documents_found', 0)}\n\n"
            
            for insight in kb.get("key_insights", []):
                report += f"- {insight}\n"
        
        # Add Web Intelligence findings
        report += "\n---\n\n## 6. Web Intelligence\n\n"
        if "web_intelligence" in raw_findings:
            web = raw_findings["web_intelligence"]
            
            report += "### Recent Scientific Publications\n"
            for pub in web.get("scientific_publications", [])[:2]:
                report += f"- **{pub.get('title')}** ({pub.get('journal')}, {pub.get('publication_date')})\n"
            
            report += "\n### Clinical Guidelines\n"
            for guide in web.get("guidelines", [])[:2]:
                report += f"- {guide.get('title')} - {guide.get('source')}\n"
        
        # Final Recommendations
        report += f"\n---\n\n## Final Recommendations\n\n{synthesis.get('summary', 'No summary available')}\n"
        
        report += "\n---\n\n*Report generated by PharmaAI Agentic System*\n"
        
        return report
    
    def _convert_to_pdf(self, markdown_path: str, report_id: str, charts: Dict = None, 
                       synthesis: Dict = None, raw_findings: Dict = None) -> str:
        """
        Convert Markdown to PDF using WeasyPrint or ReportLab
        
        Process: Markdown → HTML → PDF (WeasyPrint) or Markdown → Professional PDF (ReportLab)
        """
        pdf_path = os.path.join(self.output_directory, f"{report_id}.pdf")
        
        # Try WeasyPrint first (better formatting)
        if WEASYPRINT_AVAILABLE and HTML and markdown:
            return self._convert_with_weasyprint(markdown_path, pdf_path)
        
        # Fallback to ReportLab with enhanced professional formatting
        elif ReportLab_available:
            return self._convert_with_reportlab_professional(
                markdown_path, pdf_path, charts, synthesis, raw_findings
            )
        
        # Final fallback: Create placeholder PDF
        else:
            with open(pdf_path, "w", encoding="utf-8") as f:
                f.write(f"PDF Report Placeholder\n\nSee Markdown version at: {markdown_path}")
            return pdf_path
    
    def _convert_with_weasyprint(self, markdown_path: str, pdf_path: str) -> str:
        """Convert using WeasyPrint (Linux/Mac)"""
        
        try:
            # Read Markdown content
            with open(markdown_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
            
            # Convert Markdown to HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=['tables', 'fenced_code', 'nl2br']
            )
            
            # Create styled HTML document
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 800px;
                        margin: 40px auto;
                        padding: 20px;
                    }}
                    h1 {{
                        color: #2c3e50;
                        border-bottom: 3px solid #3498db;
                        padding-bottom: 10px;
                    }}
                    h2 {{
                        color: #34495e;
                        margin-top: 30px;
                        border-bottom: 2px solid #95a5a6;
                        padding-bottom: 5px;
                    }}
                    h3 {{
                        color: #7f8c8d;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 20px 0;
                    }}
                    th, td {{
                        border: 1px solid #ddd;
                        padding: 12px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #3498db;
                        color: white;
                    }}
                    tr:nth-child(even) {{
                        background-color: #f2f2f2;
                    }}
                    .decision-go {{
                        color: #27ae60;
                        font-weight: bold;
                    }}
                    .decision-no-go {{
                        color: #e74c3c;
                        font-weight: bold;
                    }}
                    .decision-partial {{
                        color: #f39c12;
                        font-weight: bold;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            # Convert HTML to PDF using WeasyPrint
            HTML(string=styled_html).write_pdf(pdf_path)
            
            print(f"✓ PDF generated successfully: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            print(f"Error generating PDF with WeasyPrint: {e}")
            # Fallback to placeholder
            with open(pdf_path, "w", encoding="utf-8") as f:
                f.write(f"PDF generation failed\n\nError: {e}\n\nSee Markdown version at: {markdown_path}")
            return pdf_path
    
    def _convert_with_reportlab(self, markdown_path: str, pdf_path: str) -> str:
        """Convert using ReportLab (Windows-compatible)"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.colors import HexColor
            
            # Read markdown content
            with open(markdown_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
            
            # Create PDF document
            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=HexColor('#2c3e50'),
                spaceAfter=30
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=HexColor('#34495e'),
                spaceAfter=12
            )
            
            # Parse markdown and convert to PDF elements
            lines = markdown_content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 0.2*inch))
                elif line.startswith('# '):
                    story.append(Paragraph(line[2:], title_style))
                elif line.startswith('## '):
                    story.append(Paragraph(line[3:], heading_style))
                elif line.startswith('### '):
                    story.append(Paragraph(line[4:], styles['Heading3']))
                elif line.startswith('**') and line.endswith('**'):
                    story.append(Paragraph(f"<b>{line[2:-2]}</b>", styles['Normal']))
                elif line.startswith('- '):
                    story.append(Paragraph(f"• {line[2:]}", styles['Normal']))
                elif line.startswith('---'):
                    story.append(Spacer(1, 0.3*inch))
                else:
                    if line:
                        story.append(Paragraph(line, styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            print(f"✓ PDF generated successfully with ReportLab: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            print(f"Error generating PDF with ReportLab: {e}")
            # Fallback to placeholder
            with open(pdf_path, "w", encoding="utf-8") as f:
                f.write(f"PDF generation failed\n\nError: {e}\n\nSee Markdown version at: {markdown_path}")
            return pdf_path
            
        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            # Fallback to placeholder
            with open(pdf_path, "w", encoding="utf-8") as f:
                f.write(f"PDF Generation Failed\n\nError: {str(e)}\n\nSee Markdown version at: {markdown_path}")
            return pdf_path
    
    def _convert_with_reportlab_professional(self, markdown_path: str, pdf_path: str,
                                            charts: Dict = None, synthesis: Dict = None, 
                                            raw_findings: Dict = None) -> str:
        """
        Generate professional PDF with logo splash screen and analytics charts
        
        Args:
            markdown_path: Path to markdown source
            pdf_path: Output PDF path
            charts: Dictionary of chart image paths
            synthesis: Synthesized analysis
            raw_findings: Raw agent findings
        """
        try:
            doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=18)
            story = []
            styles = getSampleStyleSheet()
            
            # Custom professional styles
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=28,
                textColor=rl_colors.HexColor('#1a237e'),
                alignment=1,  # Center
                spaceAfter=30,
                fontName='Helvetica-Bold'
            )
            
            heading_style = ParagraphStyle(
                'Heading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=rl_colors.HexColor('#283593'),
                spaceAfter=12,
                spaceBefore=20,
                fontName='Helvetica-Bold'
            )
            
            subheading_style = ParagraphStyle(
                'SubHeading',
                parent=styles['Heading3'],
                fontSize=13,
                textColor=rl_colors.HexColor('#3949ab'),
                spaceAfter=10,
                fontName='Helvetica-Bold'
            )
            
            # === SPLASH SCREEN WITH LOGO ===
            if os.path.exists(self.logo_path):
                try:
                    logo = Image(self.logo_path, width=4*inch, height=4*inch, kind='proportional')
                    story.append(Spacer(1, 1.5*inch))
                    story.append(logo)
                    story.append(Spacer(1, 0.5*inch))
                except Exception as e:
                    print(f"Warning: Could not load logo: {e}")
            
            story.append(Paragraph("PharmaAI Research Report", title_style))
            story.append(Paragraph("Innovation Opportunity Assessment", styles['Heading2']))
            story.append(Spacer(1, 0.3*inch))
            
            # Report metadata
            molecule = "Unknown"
            if raw_findings and isinstance(raw_findings, dict):
                for agent_name in ['iqvia', 'patent', 'clinical_trials']:
                    if agent_name in raw_findings and 'molecule' in raw_findings[agent_name]:
                        molecule = raw_findings[agent_name]['molecule']
                        break
            
            generated = datetime.now().strftime("%B %d, %Y at %H:%M")
            
            metadata_style = ParagraphStyle('Metadata', parent=styles['Normal'], 
                                           alignment=1, fontSize=11, textColor=rl_colors.grey)
            story.append(Paragraph(f"<b>Molecule:</b> {molecule}", metadata_style))
            story.append(Paragraph(f"<b>Generated:</b> {generated}", metadata_style))
            story.append(PageBreak())
            
            # === EXECUTIVE SUMMARY ===
            story.append(Paragraph("Executive Summary", heading_style))
            
            if synthesis:
                decision = synthesis.get('decision', 'PENDING')
                confidence = synthesis.get('confidence', 0)
                reasoning = synthesis.get('reasoning', 'No reasoning provided')
                
                # Decision box with color coding
                decision_color = rl_colors.green if decision == "GO" else \
                               rl_colors.red if decision == "NO_GO" else rl_colors.orange
                
                decision_data = [
                    ['Decision', decision],
                    ['Confidence', f'{confidence}/100'],
                    ['Recommendation', reasoning]
                ]
                
                decision_table = Table(decision_data, colWidths=[2*inch, 4.5*inch])
                decision_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), rl_colors.HexColor('#e3f2fd')),
                    ('BACKGROUND', (1, 0), (1, 0), decision_color),
                    ('TEXTCOLOR', (1, 0), (1, 0), rl_colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 1, rl_colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.lightgrey]),
                    ('PADDING', (0, 0), (-1, -1), 10)
                ]))
                
                story.append(decision_table)
                story.append(Spacer(1, 0.3*inch))
            
            # === ANALYTICS PANELS ===
            if charts:
                story.append(PageBreak())
                story.append(Paragraph("Analytics & Visualization", heading_style))
                
                chart_count = 0
                for chart_type, chart_path in charts.items():
                    if os.path.exists(chart_path):
                        try:
                            chart_img = Image(chart_path, width=6*inch, height=4*inch, kind='proportional')
                            story.append(chart_img)
                            story.append(Spacer(1, 0.2*inch))
                            chart_count += 1
                            
                            # Page break after every 2 charts
                            if chart_count % 2 == 0 and chart_count < len(charts):
                                story.append(PageBreak())
                        except Exception as e:
                            print(f"Warning: Could not embed chart {chart_type}: {e}")
            
            # === DETAILED FINDINGS ===
            story.append(PageBreak())
            story.append(Paragraph("Detailed Findings by Agent", heading_style))
            
            # Market Intelligence
            story.append(Paragraph("1. Market Intelligence (IQVIA)", subheading_style))
            if raw_findings and 'iqvia' in raw_findings:
                iqvia = raw_findings['iqvia']
                if 'error' in iqvia:
                    story.append(Paragraph(f"⚠️ {iqvia.get('message', 'Data unavailable')}", styles['Normal']))
                else:
                    market_summary = f"Market insights available for {iqvia.get('therapy_area', 'N/A')}"
                    story.append(Paragraph(market_summary, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # Patent Landscape
            story.append(Paragraph("2. Patent Landscape", subheading_style))
            if raw_findings and 'patent' in raw_findings:
                patent = raw_findings['patent']
                if 'error' in patent:
                    story.append(Paragraph(f"⚠️ {patent.get('message', 'Data unavailable')}", styles['Normal']))
                else:
                    patent_summary = f"Patent analysis completed"
                    story.append(Paragraph(patent_summary, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # Clinical Trials
            story.append(Paragraph("3. Clinical Trials Landscape", subheading_style))
            if raw_findings and 'clinical_trials' in raw_findings:
                ct = raw_findings['clinical_trials']
                if 'error' in ct:
                    story.append(Paragraph(f"⚠️ {ct.get('message', 'Data unavailable')}", styles['Normal']))
                else:
                    ct_summary = f"Total Active Trials: {ct.get('total_active_trials', 'N/A')}"
                    story.append(Paragraph(ct_summary, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # Web Intelligence
            story.append(Paragraph("4. Web Intelligence", subheading_style))
            if raw_findings and 'web_intelligence' in raw_findings:
                web = raw_findings['web_intelligence']
                if not web.get('error'):
                    web_summary = f"Web research completed with multiple data sources"
                    story.append(Paragraph(web_summary, styles['Normal']))
            
            # Footer
            story.append(PageBreak())
            story.append(Spacer(1, 6*inch))
            footer_style = ParagraphStyle('Footer', parent=styles['Normal'], 
                                         alignment=1, fontSize=9, textColor=rl_colors.grey)
            story.append(Paragraph("Report generated by PharmaAI Agentic System", footer_style))
            story.append(Paragraph(f"© {datetime.now().year} PharmaAI - All Rights Reserved", footer_style))
            
            # Build PDF
            doc.build(story)
            
            print(f"✓ Professional PDF generated with logo and analytics: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            print(f"Error generating professional PDF: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to basic version
            return self._convert_with_reportlab(markdown_path, pdf_path)

