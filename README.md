# PharmaAI - Agentic AI Drug Repurposing Assistant

![PharmaAI](https://img.shields.io/badge/AI-Powered-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.9+-blue)

**PharmaAI** is an intelligent drug repurposing research assistant powered by **Agentic AI**. Built for Techathon 6.0, it helps pharmaceutical strategists identify innovation opportunities by orchestrating multiple specialized AI agents for comprehensive market, patent, clinical, and trade analysis.

---

## 🎯 Problem Statement

Pharmaceutical companies need to identify drug repurposing opportunities faster. Traditional literature reviews take 2-3 months. PharmaAI reduces this to **minutes** using autonomous AI agents that:

- Analyze market dynamics (IQVIA-style data)
- Assess patent landscapes and FTO risks
- Map clinical trial pipelines
- Review import/export trade trends
- Search internal knowledge bases
- Aggregate web intelligence
- Generate comprehensive PDF reports

---

## 🏗️ Architecture

### Master Agent (Orchestrator)
- Interprets user queries
- Decomposes research into tasks
- Applies **decision logic**:
  - ❌ Stops if market unattractive
  - ⚠️ Flags if patents block FTO
  - ⚠️ Warns if clinical space saturated
- Synthesizes findings into GO/NO-GO recommendations

### Worker Agents (7 Specialized Agents)

| Agent | Data Source | Responsibility | Output |
|-------|-------------|----------------|--------|
| **IQVIA Insights** | ZenRows web scraping | Market size, CAGR, competition | Tables, graphs, attractiveness score |
| **EXIM Trends** | UN Comtrade API | Import/export data by country | Trade volumes, sourcing risk assessment |
| **Patent Landscape** | USPTO/EPO via patent_client | Patent search & FTO analysis | Active patents, FTO score, expiry timelines |
| **Clinical Trials** | ClinicalTrials.gov (pytrials) | Trial pipeline analysis | Active trials, phase distribution, repurposing signals |
| **Internal Knowledge** | Supabase pgvector + PDF processing | RAG over internal documents | Semantic search over internal PDFs |
| **Web Intelligence** | DuckDuckGo Search | Real-time web search | Guidelines, publications, news, forums |
| **Report Generator** | WeasyPrint | Markdown → PDF conversion | Downloadable comprehensive PDF report |

---

## 🚀 Tech Stack

**Core Framework:**
- **Frontend**: Next.js 16 (React 19, TypeScript, Tailwind CSS)
- **Backend**: FastAPI (Python 3.9+)
- **Agent Framework**: CrewAI + MCP (Model Context Protocol)
- **LLM**: Mistral 7B GGUF (local)
- **Vector Store**: Supabase PostgreSQL with `pgvector`
- **MCP Server**: Fast MCP integration for AI assistant access

**Real Data Sources:**
- **IQVIA**: ZenRows API (web scraping)
- **Trade Data**: UN Comtrade API (comtradeapicall)
- **Patents**: USPTO/EPO (patent_client library)
- **Clinical Trials**: ClinicalTrials.gov (pytrials)
- **Web Search**: DuckDuckGo (duckduckgo-search)
- **PDF Processing**: pdfplumber, PyPDF2
- **Report Generation**: WeasyPrint, Jinja2, Markdown

---

## 📦 Quick Start

### 1. Install Backend Dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows (or source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
```

**Note:** Some libraries may require additional system dependencies:
- **WeasyPrint** (PDF generation): Requires GTK+ libraries
  - Windows: Download GTK+ from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
  - Mac: `brew install cairo pango gdk-pixbuf libffi`
  - Linux: `sudo apt-get install python3-dev python3-pip python3-cffi libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info`

### 2. Configure Environment

```bash
cd backend
cp .env.example .env
# Edit .env with your API keys and configuration
```

**Required API Keys** (for real data sources):
- **ZenRows API**: For IQVIA web scraping (already provided in example)
- **UN Comtrade API**: Get free key at https://comtradeplus.un.org/ (optional)
- **Supabase**: For vector database (pgvector)

**Optional APIs** (free, no keys required):
- **USPTO/EPO Patents**: patent_client uses public APIs
- **ClinicalTrials.gov**: pytrials uses free public API
- **DuckDuckGo Search**: No API key needed

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 4. Run Backend

```bash
cd backend
python main.py
```

Backend runs on http://localhost:8000

### 5. Run Frontend

```bash
cd frontend
npm run dev
```

Frontend runs on http://localhost:3000

### 6. Try It Out!

Open http://localhost:3000 and ask:
- "Find repurposing opportunities for Montelukast"
- "Analyze market potential for Metformin"

---

##   MCP Server Integration

PharmaAI exposes all agents as **Model Context Protocol (MCP)** tools, enabling integration with:
- ✅ **Claude Desktop** 
- ✅ **VS Code GitHub Copilot**
- ✅ **Cursor**
- ✅ Any MCP-compatible AI assistant

### Quick MCP Setup

**Server URL:** `http://localhost:8000/mcp`

**Available Tools:**
1. `pharma_research_orchestrator` - Master agent for complete research
2. `iqvia_market_analysis` - Market intelligence  
3. `exim_trade_analysis` - Trade data analysis
4. `patent_landscape_analysis` - Patent & FTO analysis
5. `clinical_trials_analysis` - Clinical pipeline intelligence
6. `internal_knowledge_search` - Semantic search over documents
7. `web_intelligence_search` - Real-time web intelligence
8. `generate_research_report` - PDF report generation

**Configure your AI assistant:**

```json
{
  "mcpServers": {
    "pharmaai": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

📖 **Full MCP Documentation:** See [MCP_SERVER.md](MCP_SERVER.md)

---

##  📊 Decision Logic

The Master Agent applies intelligent decision-making:

**Market Attractiveness**
- ✓ Market size > $50M USD
- ✓ CAGR > 3%
- ✓ Competition not excessive

**Patent Freedom to Operate (FTO)**
- ✓ FTO risk score < 7/10
- ✓ No blocking patents

**Clinical Viability**
- ✓ Active trials < 15 (not saturated)
- ✓ Indication diversity suggests repurposing potential

**Final Decision:**
- **GO**: All checks pass (Confidence: 85%)
- **PARTIAL_GO**: Market + Patents favorable (Confidence: 65%)
- **NO_GO**: Critical failures (Confidence: <40%)

---

## 📁 Project Structure

```
Pharma_AI_Agent/
├── backend/
│   ├── agents/                    # 7 specialized AI agents
│   │   ├── master_agent.py        # Orchestration logic
│   │   ├── iqvia_agent.py         # Market intelligence
│   │   ├── exim_agent.py          # Trade data
│   │   ├── patent_agent.py        # Patent landscape
│   │   ├── clinical_trials_agent.py
│   │   ├── internal_kb_agent.py   # RAG with pgvector
│   │   ├── web_intel_agent.py
│   │   └── report_agent.py
│   ├── services/
│   │   ├── supabase_client.py     # Vector DB
│   │   └── embedding_service.py   # Embeddings
│   ├── main.py                    # FastAPI server
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   └── ChatUI.tsx         # Chat interface
│   │   └── page.tsx
│   └── package.json
└── models/
    └── mistral-7b-instruct.gguf   # Local LLM (optional)
```

---

## 🔥 Key Features

✅ **Multi-Agent Orchestration** - 7 specialized agents work in harmony  
✅ **Real Data Integration** - Production-ready APIs (ZenRows, Comtrade, USPTO, ClinicalTrials.gov, DuckDuckGo)  
✅ **Decision Intelligence** - Automatic GO/NO-GO with reasoning  
✅ **RAG with pgvector** - Semantic search over internal documents  
✅ **Mock Mode** - Runs without external APIs for demos/testing  
✅ **Real-time Chat UI** - Conversational responses with markdown rendering  
✅ **PDF Reports** - Professional PDF generation with WeasyPrint  

---

## 🔧 Configuration Guide

### Mock vs Real Data Mode

PharmaAI supports two operating modes:

**Mock Mode** (Default - for testing/demos):
```env
USE_MOCK_DATA=true
```
- Uses pre-loaded sample data for Montelukast, Metformin, Aspirin
- No API keys required
- Instant responses
- Perfect for demonstrations and development

**Real Data Mode** (Production - for actual research):
```env
USE_MOCK_DATA=false
ZENROWS_API_KEY=your_key_here
COMTRADE_SUBSCRIPTION_KEY=your_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
```
- Fetches live data from real sources
- Requires API keys (see .env.example)
- Longer response times
- Accurate, up-to-date information

### Individual Agent Data Sources

Each agent can independently use real or mock data:

| Agent | Real Data Source | API Key Required? | Free Tier Available? |
|-------|------------------|-------------------|----------------------|
| IQVIA | ZenRows web scraping | ✅ Yes | ✅ Yes (limited) |
| EXIM | UN Comtrade API | ✅ Yes | ✅ Yes (500 requests/hour) |
| Patent | patent_client (USPTO/EPO) | ❌ No | ✅ Yes (unlimited) |
| Clinical Trials | pytrials (ClinicalTrials.gov) | ❌ No | ✅ Yes (unlimited) |
| Web Intelligence | DuckDuckGo Search | ❌ No | ✅ Yes (unlimited) |
| Internal KB | Supabase pgvector | ✅ Yes | ✅ Yes (500MB free) |
| Report Generator | WeasyPrint (local) | ❌ No | ✅ Yes (unlimited) |

---

## 🧪 Example Workflow

**User Query:** "Find repurposing opportunities for Montelukast"

**Agent Orchestration:**
1. **Master Agent** → Extract molecule: "Montelukast"
2. **IQVIA Agent** → Market size: $850M, CAGR: 5.2% ✓
3. **Patent Agent** → FTO risk: 6.5/10 ✓
4. **Clinical Trials Agent** → 8 active trials ✓
5. **EXIM Agent** → Trade analysis
6. **Internal KB Agent** → Search internal docs
7. **Web Intelligence** → Recent publications
8. **Report Generator** → PDF with all findings

**Decision:** **GO** (Confidence: 85%)

---

## ⚙️ Configuration

Create `backend/.env`:

```env
PORT=8000
LLM_MODEL=mistral
MISTRAL_MODEL_PATH=models/mistral-7b-instruct-v0.1.Q4_K_M.gguf
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-key
EMBEDDING_MODEL_TYPE=mistral_local
USE_MOCK_DATA=true
```

---

## 📝 Example Prompts

- "Montelukast repurposing opportunities"
- "Market analysis for Metformin"
- "Patent landscape for Aspirin"
- "Clinical trials for respiratory drugs"

---

## 🚧 Roadmap

- [ ] Real API integrations (IQVIA, USPTO, ClinicalTrials.gov)
- [ ] PDF upload for internal knowledge base
- [ ] Advanced visualizations
- [ ] User authentication
- [ ] Export to Excel/PowerPoint

---

## 📄 License

MIT License

---

## 🙏 Built for Techathon 6.0

Drug repurposing research assistant powered by Agentic AI

**Ready to innovate?** 🚀 Start the app and ask your first question!
