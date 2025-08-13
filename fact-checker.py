"""
Fact Checker Hybrid - CrewAI Agent + MCP Server
Auteur: Joop Snijder
Versie: 2.0

Deze implementatie werkt zowel als:
1. CrewAI multi-agent systeem voor complexe fact-checking
2. MCP server voor directe integratie met Claude Desktop en andere MCP clients
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

# Try to import CrewAI tools, with fallbacks for compatibility
try:
    from crewai_tools import SerperDevTool, WebsiteSearchTool, ScrapeWebsiteTool
except ImportError:
    # Fallback for older crewai_tools versions
    SerperDevTool = None
    WebsiteSearchTool = None
    ScrapeWebsiteTool = None

# MCP Server imports
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool

# Pydantic voor data modellen
from pydantic import BaseModel, Field


# ============================================
# CONFIGURATIE
# ============================================

# API Keys (gebruik environment variables)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Initialize FastMCP server
mcp = FastMCP(
    name="fact-checker",
    instructions="Fact Checker service that verifies claims and statistics in texts",
)

# Initialize LLM voor CrewAI
llm = ChatOpenAI(model="gpt-4", temperature=0.1, api_key=OPENAI_API_KEY)

# Initialize Smart Search Tool met automatische fallback
from smart_search_tool import SmartSearchTool, create_smart_search_tool

# Gebruik Smart Search Tool in plaats van SerperDevTool
smart_search = SmartSearchTool(
    serper_api_key=SERPER_API_KEY, brave_api_key=os.getenv("BRAVE_API_KEY", "")
)
search_tool = create_smart_search_tool()

# Initialize other tools with fallback handling
if ScrapeWebsiteTool:
    web_scraper = ScrapeWebsiteTool()
else:
    web_scraper = None

if WebsiteSearchTool:
    website_search = WebsiteSearchTool()
else:
    website_search = None


# ============================================
# DATA MODELLEN (Gedeeld tussen CrewAI en MCP)
# ============================================


class ClaimVerification(BaseModel):
    """Model voor individuele claim verificatie"""

    original_claim: str = Field(description="De originele claim uit de tekst")
    claim_type: str = Field(description="Type: statistiek, feit, quote, datum, etc.")
    verification_status: str = Field(
        description="Status: Geverifieerd, Onwaar, Deels waar, Onverifieerbaar"
    )
    confidence_score: float = Field(description="Betrouwbaarheidsscore 0-1")
    correct_information: Optional[str] = Field(
        description="De juiste informatie indien beschikbaar"
    )
    sources: List[str] = Field(description="Bronnen gebruikt voor verificatie")
    explanation: str = Field(description="Uitleg van de verificatie")


class FactCheckReport(BaseModel):
    """Complete fact check rapport"""

    original_text: str = Field(description="De originele ingevoerde tekst")
    total_claims: int = Field(description="Totaal aantal geïdentificeerde claims")
    verified_claims: int = Field(description="Aantal geverifieerde claims")
    false_claims: int = Field(description="Aantal onjuiste claims")
    unverifiable_claims: int = Field(description="Aantal niet-verifieerbare claims")
    overall_reliability: str = Field(
        description="Algemene betrouwbaarheid: Hoog, Gemiddeld, Laag"
    )
    verifications: List[ClaimVerification] = Field(
        description="Lijst van alle verificaties"
    )
    summary: str = Field(description="Samenvatting van bevindingen")
    timestamp: str = Field(description="Tijdstip van verificatie")


# ============================================
# CREWAI AGENTS
# ============================================


def create_agents():
    """Creëer en return alle agents"""

    claim_extractor = Agent(
        role="Claim Extractor",
        goal="Identificeer alle verifieerbare claims, statistieken en feitelijke uitspraken in de tekst",
        backstory="""Je bent een expert in het analyseren van teksten en het identificeren 
        van claims die geverifieerd kunnen worden. Je hebt jarenlange ervaring met het 
        onderscheiden van meningen van feiten.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )

    research_specialist = Agent(
        role="Research Specialist",
        goal="Zoek betrouwbare bronnen om claims te verifiëren",
        backstory="""Je bent een onderzoeksexpert met toegang tot het internet. 
        Je specialiteit is het vinden van autoritatieve bronnen.""",
        verbose=True,
        allow_delegation=False,
        tools=[
            tool
            for tool in [search_tool, web_scraper, website_search]
            if tool is not None
        ],
        llm=llm,
        max_iter=5,
    )

    verification_analyst = Agent(
        role="Fact Verification Analyst",
        goal="Vergelijk claims met gevonden bronnen en bepaal waarheidsgehalte",
        backstory="""Je bent een analyticus gespecialiseerd in fact-checking. 
        Je maakt genuanceerde oordelen over de waarheid van claims.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )

    report_compiler = Agent(
        role="Report Compiler",
        goal="Stel een helder en actionable fact-check rapport samen",
        backstory="""Je bent een expert in het schrijven van heldere fact-check 
        rapporten in normale, directe taal.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=2,
    )

    return claim_extractor, research_specialist, verification_analyst, report_compiler


# ============================================
# CREWAI FACT CHECKING LOGICA
# ============================================


def run_fact_check_crew(text: str) -> FactCheckReport:
    """
    Run de complete CrewAI fact checking crew
    """
    claim_extractor, research_specialist, verification_analyst, report_compiler = (
        create_agents()
    )

    # Task 1: Extract Claims
    extract_claims_task = Task(
        description=f"""
        Analyseer de volgende tekst en identificeer ALLE verifieerbare claims:
        
        {text}
        
        Identificeer specifiek:
        1. Statistieken en getallen
        2. Historische feiten en datums  
        3. Quotes toegeschreven aan personen
        4. Wetenschappelijke claims
        5. Bedrijfsinformatie
        6. Geografische of demografische feiten
        
        Focus alleen op verifieerbare feiten, geen meningen.
        """,
        agent=claim_extractor,
        expected_output="Een gestructureerde lijst van alle verifieerbare claims",
    )

    # Task 2: Research Claims
    research_claims_task = Task(
        description="""
        Onderzoek elke geïdentificeerde claim.
        Zoek naar betrouwbare bronnen en documenteer je bevindingen.
        """,
        agent=research_specialist,
        expected_output="Onderzoeksresultaten voor elke claim met bronvermelding",
        context=[extract_claims_task],
    )

    # Task 3: Verify Claims
    verify_claims_task = Task(
        description="""
        Verifieer elke claim op basis van het onderzoek.
        Bepaal de verificatiestatus en betrouwbaarheidsscore.
        """,
        agent=verification_analyst,
        expected_output="Verificatiestatus en analyse voor elke claim",
        context=[extract_claims_task, research_claims_task],
    )

    # Task 4: Compile Report
    compile_report_task = Task(
        description="""
        Stel een professioneel fact-check rapport samen.
        Schrijf helder en direct, vermijd clichés.
        """,
        agent=report_compiler,
        expected_output="Een compleet fact-check rapport",
        context=[extract_claims_task, research_claims_task, verify_claims_task],
        output_pydantic=FactCheckReport,
    )

    # Creëer en run crew
    crew = Crew(
        agents=[
            claim_extractor,
            research_specialist,
            verification_analyst,
            report_compiler,
        ],
        tasks=[
            extract_claims_task,
            research_claims_task,
            verify_claims_task,
            compile_report_task,
        ],
        process=Process.sequential,
        verbose=True,
        memory=True,
        cache=True,
    )

    result = crew.kickoff()
    return result


# ============================================
# SIMPLIFIED FACT CHECKING (voor snelle MCP calls)
# ============================================


async def quick_fact_check(text: str) -> Dict[str, Any]:
    """
    Snelle fact check zonder full CrewAI crew
    Gebruikt alleen web search voor directe verificatie
    """
    try:
        # Gebruik search tool direct voor snelle checks
        search_results = search_tool.run(f"fact check verify {text[:100]}")

        # Basis analyse
        return {
            "status": "quick_check",
            "text": text,
            "initial_search": search_results,
            "timestamp": datetime.now().isoformat(),
            "note": "Voor volledige verificatie, gebruik deep_fact_check",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# ============================================
# MCP SERVER RESOURCES
# ============================================

# Store voor fact check geschiedenis
fact_check_history: List[FactCheckReport] = []


@mcp.resource("history://list")
async def get_fact_check_history() -> Resource:
    """Krijg de geschiedenis van alle fact checks"""
    return Resource(
        uri="history://list",
        name="Fact Check History",
        description="Lijst van alle uitgevoerde fact checks",
        mimeType="application/json",
        text=json.dumps(
            [
                {
                    "id": i,
                    "timestamp": report.timestamp,
                    "overall_reliability": report.overall_reliability,
                    "total_claims": report.total_claims,
                    "false_claims": report.false_claims,
                }
                for i, report in enumerate(fact_check_history)
            ],
            indent=2,
        ),
    )


@mcp.resource("history://report/{report_id}")
async def get_specific_report(report_id: str) -> Resource:
    """Krijg een specifiek fact check rapport"""
    try:
        idx = int(report_id)
        if 0 <= idx < len(fact_check_history):
            report = fact_check_history[idx]
            return Resource(
                uri=f"history://report/{report_id}",
                name=f"Fact Check Report #{report_id}",
                description=f"Rapport van {report.timestamp}",
                mimeType="application/json",
                text=report.model_dump_json(indent=2),
            )
    except (ValueError, IndexError):
        pass

    return Resource(
        uri=f"history://report/{report_id}",
        name="Report Not Found",
        description="Dit rapport bestaat niet",
        mimeType="text/plain",
        text="Report niet gevonden",
    )


# ============================================
# MCP SERVER TOOLS
# ============================================


@mcp.tool()
async def quick_verify(text: str) -> str:
    """
    Snelle verificatie van een korte claim of statistiek.

    Args:
        text: De te verifiëren claim (max 500 karakters)

    Returns:
        Quick verification result
    """
    if len(text) > 500:
        return json.dumps(
            {
                "error": "Text te lang voor quick verify. Gebruik deep_fact_check voor langere teksten."
            }
        )

    result = await quick_fact_check(text)
    return json.dumps(result, indent=2)


@mcp.tool()
async def deep_fact_check(text: str) -> str:
    """
    Uitgebreide fact check met multi-agent verificatie.
    Gebruikt CrewAI voor grondige verificatie van alle claims.

    Args:
        text: De te controleren tekst

    Returns:
        Uitgebreid fact check rapport
    """
    try:
        # Run de CrewAI crew (dit kan even duren)
        report = await asyncio.to_thread(run_fact_check_crew, text)

        # Voeg toe aan geschiedenis
        fact_check_history.append(report)

        # Return als JSON
        return report.model_dump_json(indent=2)

    except Exception as e:
        return json.dumps(
            {
                "error": f"Fact check mislukt: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
        )


@mcp.tool()
async def check_specific_statistic(
    statistic: str, context: str = "", year: Optional[int] = None
) -> str:
    """
    Verifieer een specifieke statistiek met optionele context.

    Args:
        statistic: De statistiek om te verifiëren (bijv. "GPT-4 heeft 175 miljard parameters")
        context: Optionele context voor betere verificatie
        year: Optioneel jaar voor tijdsgevoelige statistieken

    Returns:
        Verificatie resultaat met bronnen
    """
    search_query = statistic
    if context:
        search_query += f" {context}"
    if year:
        search_query += f" {year}"

    try:
        # Gebruik search tool
        search_results = search_tool.run(search_query)

        # Basis verificatie
        return json.dumps(
            {
                "statistic": statistic,
                "context": context,
                "year": year,
                "search_results": search_results,
                "timestamp": datetime.now().isoformat(),
                "note": "Voor volledige verificatie met bronanalyse, gebruik deep_fact_check",
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": str(e), "timestamp": datetime.now().isoformat()})


@mcp.tool()
async def get_history_summary() -> str:
    """
    Krijg een samenvatting van alle fact checks.

    Returns:
        Samenvatting van fact check geschiedenis
    """
    if not fact_check_history:
        return json.dumps({"message": "Nog geen fact checks uitgevoerd", "total": 0})

    total_claims = sum(r.total_claims for r in fact_check_history)
    total_false = sum(r.false_claims for r in fact_check_history)

    summary = {
        "total_reports": len(fact_check_history),
        "total_claims_checked": total_claims,
        "total_false_claims": total_false,
        "accuracy_rate": f"{((total_claims - total_false) / total_claims * 100):.1f}%"
        if total_claims > 0
        else "N/A",
        "recent_checks": [
            {
                "timestamp": r.timestamp,
                "reliability": r.overall_reliability,
                "claims": r.total_claims,
            }
            for r in fact_check_history[-5:]  # Laatste 5
        ],
    }

    return json.dumps(summary, indent=2)


# ============================================
# MAIN ENTRY POINTS
# ============================================


def run_standalone_check(text: str):
    """Run als standalone CrewAI applicatie"""
    print("\n" + "=" * 50)
    print("FACT CHECKER - STANDALONE MODE")
    print("=" * 50 + "\n")

    crew_result = run_fact_check_crew(text)

    # Extract the actual report from CrewOutput
    if hasattr(crew_result, "raw"):
        report_data = crew_result.raw
    else:
        # Fallback: try to parse JSON from crew_result string representation
        try:
            import json

            report_data = json.loads(str(crew_result))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Could not parse crew result: {e}")
            return crew_result

    # Print rapport
    print("\n### FACT CHECK RAPPORT ###\n")
    print(
        f"Algemene betrouwbaarheid: {report_data.get('overall_reliability', 'Unknown')}"
    )
    print(f"Totaal claims: {report_data.get('total_claims', 0)}")
    print(f"Geverifieerd: {report_data.get('verified_claims', 0)}")
    print(f"Onwaar: {report_data.get('false_claims', 0)}")
    print(f"\nSamenvatting: {report_data.get('summary', 'No summary available')}")

    # Save rapport
    output_file = f"fact_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"\nRapport opgeslagen als: {output_file}")

    return crew_result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--mcp":
            # Start als MCP server
            mcp.run()
        elif sys.argv[1] == "--check":
            # Run standalone check met tekst uit bestand of stdin
            if len(sys.argv) > 2:
                # Lees uit bestand
                with open(sys.argv[2], "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                # Lees van stdin
                print("Voer tekst in om te checken (Ctrl+D om te eindigen):")
                text = sys.stdin.read()

            run_standalone_check(text)
        elif sys.argv[1] == "--help":
            print("""
        Fact Checker - Hybrid CrewAI + MCP Implementation
        
        Gebruik:
        -------
        Als MCP Server:
            python fact_checker.py --mcp
            mcp dev fact_checker.py
            
        Als Standalone:
            python fact_checker.py --check [bestand.txt]
            echo "tekst om te checken" | python fact_checker.py --check
            
        In Python code:
            from fact_checker import run_fact_check_crew
            report = run_fact_check_crew("je tekst hier")
        """)
    else:
        # Default to MCP server mode when run without arguments (voor mcp dev)
        mcp.run()
