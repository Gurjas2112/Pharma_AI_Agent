"""Generate SYNTHETIC internal documents (strategy deck, field report, MINS) as PDFs,
as required by the problem statement's "internal documents repository" mock.

usage: uv run python scripts/make_synthetic_internal_docs.py && uv run python scripts/ingest.py --dir data/synthetic_internal
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parents[1] / "data" / "synthetic_internal"
OUT.mkdir(parents=True, exist_ok=True)
ss = getSampleStyleSheet()

DOCS = {
    "Strategy_Deck_FY26_Portfolio_Diversification.pdf": [
        ("FY26 Portfolio Diversification Strategy (SYNTHETIC - internal mock)", "Title"),
        ("1. Context", "Heading2"),
        ("US generics margins compressed by 9% YoY; India branded generics growth at 8-10%. The board mandates that "
         "15% of FY28 revenue comes from value-added products: new indications, new dosage forms and new patient "
         "populations of approved molecules (505(b)(2) in US; SEC/CDSCO pathway in India).", "BodyText"),
        ("2. Priority therapy areas", "Heading2"),
        ("Respiratory (paediatric asthma adherence, post-viral chronic cough, bronchiectasis), Cardiovascular "
         "(low-dose colchicine for secondary prevention), Women's health (PCOS, pre-eclampsia prevention) and "
         "Gastro (eosinophilic esophagitis). Oncology excluded due to capability gaps.", "BodyText"),
        ("3. Selection criteria", "Heading2"),
        ("Minimum addressable market USD 50 mn, 5-year CAGR above 3%, freedom-to-operate risk at most 7/10, fewer "
         "than 15 competing active trials, and API supply not dependent above 60% on a single country. Products "
         "with orodispersible films, paediatric suspensions or modified-release profiles are preferred because our "
         "Goa plant has spare capacity for films and MR pellets.", "BodyText"),
        ("4. Shortlist under review", "Heading2"),
        ("Montelukast orodispersible film (paediatric asthma); metformin ER suspension for adolescent PCOS; "
         "colchicine 0.5 mg MR for CV prevention; budesonide orodispersible tablet for EoE; bedtime-release aspirin "
         "for pre-eclampsia prevention. Each requires a literature and IP review before stage-gate 1.", "BodyText"),
    ],
    "Field_Report_Q3_Respiratory_India.pdf": [
        ("Field Force Insights Report - Respiratory, Q3 (SYNTHETIC - internal mock)", "Title"),
        ("Summary", "Heading2"),
        ("142 paediatricians and 96 pulmonologists interviewed across 11 cities. 63% report poor adherence to "
         "montelukast chewable tablets among children under 6 due to taste and dosing frequency. 41% would "
         "prescribe a film formulation if priced within 15% of the tablet.", "BodyText"),
        ("Unmet needs heard in the field", "Heading2"),
        ("Post-viral chronic cough lasting over 8 weeks is rising and has no approved therapy; physicians use "
         "montelukast off-label with mixed results. Bronchiectasis patients lack affordable inhaled antibiotics. "
         "Neuropsychiatric adverse event warnings for montelukast worry 28% of prescribers - a risk-management "
         "programme would be a differentiator.", "BodyText"),
        ("Competitive notes", "Heading2"),
        ("46 brands of montelukast compete in India; none has a film. Two competitors are rumoured to be developing "
         "granule sachets.", "BodyText"),
    ],
    "MINS_Medical_Insights_Colchicine_Metformin.pdf": [
        ("Medical Insights Notes (MINS) - Colchicine & Metformin (SYNTHETIC - internal mock)", "Title"),
        ("Colchicine", "Heading2"),
        ("Cardiologists cite LoDoCo2 and COLCOT as practice-changing; low-dose 0.5 mg colchicine for secondary "
         "prevention of atherosclerotic CVD is approved in the US but unavailable as a dedicated product in India. "
         "GI tolerability and drug-interaction counselling (CYP3A4/P-gp) are key educational needs. Pericarditis "
         "recurrence prevention is another established off-label use.", "BodyText"),
        ("Metformin", "Heading2"),
        ("Gynaecologists use metformin off-label in PCOS for insulin resistance; adolescents struggle with GI "
         "side-effects of IR tablets. An ER oral suspension with titration pack was requested in 7 of 12 advisory "
         "boards. Oncology repurposing evidence (colorectal adjuvant) remains inconclusive and is deprioritised.",
         "BodyText"),
    ],
}

for name, blocks in DOCS.items():
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4)
    flow = []
    for text, style in blocks:
        flow += [Paragraph(text, ss[style]), Spacer(1, 6)]
    doc.build(flow)
    print("wrote", OUT / name)
