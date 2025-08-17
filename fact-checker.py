"""
Fact Checker Hybrid - CrewAI Agent
Auteur: Joop Snijder
Versie: 2.0

Deze implementatie werkt als CrewAI multi-agent systeem voor complexe fact-checking
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# CrewAI imports
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

# Try to import CrewAI tools, with fallbacks for compatibility
try:
    from crewai_tools import ScrapeWebsiteTool, SerperDevTool, WebsiteSearchTool
except ImportError:
    # Fallback for older crewai_tools versions
    SerperDevTool = None
    WebsiteSearchTool = None
    ScrapeWebsiteTool = None

# Pydantic voor data modellen
from pydantic import BaseModel, Field

# ============================================
# CONFIGURATIE
# ============================================

# API Keys (gebruik environment variables)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Configuration removed - no longer using MCP server

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
        Je maakt genuanceerde oordelen over de waarheid van claims.
        BELANGRIJK: Je neemt altijd de exacte URLs van bronnen over uit het onderzoek.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )

    report_compiler = Agent(
        role="Report Compiler",
        goal="Stel een helder en actionable fact-check rapport samen",
        backstory="""Je bent een expert in het schrijven van heldere fact-check
        rapporten in normale, directe taal. 
        BELANGRIJK: Je zorgt ervoor dat alle bronnen (URLs) uit voorgaande taken
        correct worden opgenomen in het finale rapport.""",
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
        
        BELANGRIJK: Bewaar de EXACTE URLs van alle bronnen die je gebruikt.
        Voor elke claim, geef een lijst van alle URLs die je hebt geraadpleegd.
        """,
        agent=research_specialist,
        expected_output="Onderzoeksresultaten voor elke claim met EXACTE URLs van alle bronnen",
        context=[extract_claims_task],
    )

    # Task 3: Verify Claims
    verify_claims_task = Task(
        description="""
        Verifieer elke claim op basis van het onderzoek.
        Bepaal de verificatiestatus en betrouwbaarheidsscore.
        
        BELANGRIJK: Voeg de EXACTE URLs van de bronnen toe die gebruikt zijn voor verificatie.
        Voor elke claim moet je de sources uit de research fase meenemen.
        """,
        agent=verification_analyst,
        expected_output="Verificatiestatus, analyse en bronnen voor elke claim",
        context=[extract_claims_task, research_claims_task],
    )

    # Task 4: Compile Report
    compile_report_task = Task(
        description="""
        Stel een professioneel fact-check rapport samen.
        Schrijf helder en direct, vermijd clichés.
        
        BELANGRIJK: Zorg ervoor dat alle sources/bronnen uit de vorige taken 
        correct worden opgenomen in het finale rapport. Elke claim moet 
        de bijbehorende URLs bevatten.
        """,
        agent=report_compiler,
        expected_output="Een compleet fact-check rapport met alle bronnen",
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
    
    # Ensure the timestamp is always current (override any AI-generated placeholder)
    if hasattr(result, 'timestamp'):
        result.timestamp = datetime.now().isoformat()
    elif hasattr(result, 'raw') and isinstance(result.raw, dict):
        result.raw['timestamp'] = datetime.now().isoformat()
    
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
# PERSISTENT HISTORY MANAGEMENT
# ============================================

HISTORY_FILE = Path("fact_check_history.json")


def load_history() -> List[FactCheckReport]:
    """Laad geschiedenis uit JSON bestand"""
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [FactCheckReport.model_validate(item) for item in data]
    except Exception as e:
        print(f"Warning: Could not load history: {e}")
        return []


def save_history(history: List[FactCheckReport]):
    """Sla geschiedenis op in JSON bestand"""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                [report.model_dump() for report in history],
                f,
                indent=2,
                ensure_ascii=False,
            )
    except Exception as e:
        print(f"Warning: Could not save history: {e}")


def add_to_history(report: FactCheckReport):
    """Voeg rapport toe aan geschiedenis en sla op"""
    fact_check_history.append(report)
    save_history(fact_check_history)


# Store voor fact check geschiedenis - laad bij startup
fact_check_history: List[FactCheckReport] = load_history()


def get_fact_check_history_list():
    """Krijg de geschiedenis van alle fact checks"""
    return [
        {
            "id": i,
            "timestamp": report.timestamp,
            "overall_reliability": report.overall_reliability,
            "total_claims": report.total_claims,
            "false_claims": report.false_claims,
        }
        for i, report in enumerate(fact_check_history)
    ]


def get_specific_report(report_id: int):
    """Krijg een specifiek fact check rapport"""
    if 0 <= report_id < len(fact_check_history):
        return fact_check_history[report_id].model_dump()
    return None


# ============================================
# UTILITY FUNCTIONS
# ============================================


def quick_verify_text(text: str):
    """
    Snelle verificatie van een korte claim of statistiek.

    Args:
        text: De te verifiëren claim (max 500 karakters)

    Returns:
        Quick verification result
    """
    if len(text) > 500:
        return {
            "error": "Text te lang voor quick verify. Gebruik deep_fact_check voor langere teksten."
        }

    # Simplified version without async
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


def deep_fact_check_text(text: str):
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
        report = run_fact_check_crew(text)

        # Voeg toe aan geschiedenis
        add_to_history(report)

        # Return als dict
        return report.model_dump()

    except Exception as e:
        return {
            "error": f"Fact check mislukt: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# def export_to_markdown(
#     report_data: Dict[str, Any], original_filename: str = None
# ) -> str:
#     """
#     Krijg een samenvatting van alle fact checks.

#     Returns:
#         Samenvatting van fact check geschiedenis
#     """
#     if not fact_check_history:
#         return json.dumps({"message": "Nog geen fact checks uitgevoerd", "total": 0})

#     total_claims = sum(r.total_claims for r in fact_check_history)
#     total_false = sum(r.false_claims for r in fact_check_history)

#     summary = {
#         "total_reports": len(fact_check_history),
#         "total_claims_checked": total_claims,
#         "total_false_claims": total_false,
#         "accuracy_rate": f"{((total_claims - total_false) / total_claims * 100):.1f}%"
#         if total_claims > 0
#         else "N/A",
#         "recent_checks": [
#             {
#                 "timestamp": r.timestamp,
#                 "reliability": r.overall_reliability,
#                 "claims": r.total_claims,
#             }
#             for r in fact_check_history[-5:]  # Laatste 5
#         ],
#     }

#     return summary


def export_report_to_markdown_by_id(report_id: int, base_filename: str = None):
    """
    Export een fact check rapport naar markdown formaat.

    Args:
        report_id: ID van het rapport in de geschiedenis (0-based)
        base_filename: Optionele basis bestandsnaam voor het markdown bestand

    Returns:
        Status van de export operatie
    """
    try:
        if 0 <= report_id < len(fact_check_history):
            report = fact_check_history[report_id]
            report_data = report.model_dump()

            # Generate markdown file
            markdown_filename = export_to_markdown(report_data, base_filename)

            return {
                "status": "success",
                "message": f"Report successfully exported to {markdown_filename}",
                "filename": markdown_filename,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "message": f"Report ID {report_id} not found. Available IDs: 0-{len(fact_check_history) - 1}",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to export report: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ============================================
# MARKDOWN EXPORT FUNCTIONALITY
# ============================================


def export_to_markdown(
    report_data: Dict[str, Any], original_filename: str = None
) -> str:
    """
    Export fact check report to markdown format

    Args:
        report_data: The fact check report data
        original_filename: Optional original filename to base the markdown filename on

    Returns:
        The full path of the created markdown file
    """
    # Generate filename with fc prefix and place in same directory as input file
    if original_filename:
        # Convert to Path object
        original_path = Path(original_filename)
        # Use same directory and base name as original file with fc prefix
        output_dir = original_path.parent
        base_name = original_path.stem
        output_file = output_dir / f"fc_{base_name}.md"
    else:
        # Use timestamp with fc prefix in current directory
        output_file = Path(f"fc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")

    # Create markdown content
    markdown_content = f"""# Fact Check Report

**Generated on:** {report_data.get("timestamp", datetime.now().isoformat())}

## Summary

- **Overall Reliability:** {report_data.get("overall_reliability", "Unknown")}
- **Total Claims:** {report_data.get("total_claims", 0)}
- **Verified Claims:** {report_data.get("verified_claims", 0)}
- **False Claims:** {report_data.get("false_claims", 0)}
- **Unverifiable Claims:** {report_data.get("unverifiable_claims", 0)}

## Executive Summary

{report_data.get("summary", "No summary available")}

## Detailed Verification Results

"""

    # Add individual verifications if available
    verifications = report_data.get("verifications", [])
    if verifications:
        for i, verification in enumerate(verifications, 1):
            markdown_content += f"""### Claim {i}: {verification.get("claim_type", "General").title()}

**Original Claim:** {verification.get("original_claim", "N/A")}

**Verification Status:** {verification.get("verification_status", "Unknown")}

**Confidence Score:** {verification.get("confidence_score", "N/A")}

**Explanation:** {verification.get("explanation", "No explanation provided")}

"""

            # Add correct information if available
            if verification.get("correct_information"):
                markdown_content += f"**Correct Information:** {verification['correct_information']}\n\n"

            # Add sources
            sources = verification.get("sources", [])
            if sources:
                markdown_content += "**Sources:**\n"
                for source in sources:
                    markdown_content += f"- {source}\n"
                markdown_content += "\n"

            markdown_content += "---\n\n"
    else:
        markdown_content += "No detailed verifications available.\n\n"

    # Add original text section
    if report_data.get("original_text"):
        markdown_content += f"""## Original Text

```
{report_data["original_text"]}
```

"""

    # Add footer
    markdown_content += """## About This Report

This fact check report was generated using the Fact Checker MCP Server, which uses multi-agent verification powered by CrewAI to analyze claims and verify information against reliable sources.

For more information or to run your own fact checks, see the [Fact Checker documentation](https://github.com/your-repo/fact-checker-mcp).
"""

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return str(output_file)


# ============================================
# MAIN ENTRY POINTS
# ============================================


def run_standalone_check(
    text: str, input_filename: str = None, export_markdown: bool = False
):
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

    # Ensure report_data is a dict, not a string
    if isinstance(report_data, str):
        try:
            import json

            report_data = json.loads(report_data)
        except (json.JSONDecodeError, ValueError):
            print(
                f"Error: Could not parse report data as JSON. Got: {type(report_data)}"
            )
            print(
                "Raw data:",
                str(report_data)[:200] + "..."
                if len(str(report_data)) > 200
                else str(report_data),
            )
            return crew_result

    # Always ensure we have the current timestamp (override any AI-generated placeholders)
    report_data['timestamp'] = datetime.now().isoformat()

    # Print rapport
    print("\n### FACT CHECK RAPPORT ###\n")
    print(
        f"Algemene betrouwbaarheid: {report_data.get('overall_reliability', 'Unknown')}"
    )
    print(f"Totaal claims: {report_data.get('total_claims', 0)}")
    print(f"Geverifieerd: {report_data.get('verified_claims', 0)}")
    print(f"Onwaar: {report_data.get('false_claims', 0)}")
    print(f"\nSamenvatting: {report_data.get('summary', 'No summary available')}")

    # Save rapport in JSON (default) - in same directory as input file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if input_filename:
        # Convert to Path object
        input_path = Path(input_filename)
        # Use same directory as input file
        output_dir = input_path.parent
        base_name = input_path.stem
        json_output = output_dir / f"{base_name}_fact_check_{timestamp}.json"
    else:
        json_output = Path(f"fact_check_{timestamp}.json")

    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"\nJSON rapport opgeslagen als: {json_output}")

    # Also save as markdown if requested
    if export_markdown:
        markdown_output = export_to_markdown(report_data, input_filename)
        print(f"Markdown rapport opgeslagen als: {markdown_output}")

    return crew_result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            # Run standalone check met tekst uit bestand of stdin
            input_filename = None
            export_markdown = False

            # Check for --markdown flag
            if "--markdown" in sys.argv:
                export_markdown = True
                # Remove the flag from sys.argv for processing
                sys.argv = [arg for arg in sys.argv if arg != "--markdown"]

            if len(sys.argv) > 2:
                # Lees uit bestand
                input_filename = sys.argv[2]
                with open(input_filename, "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                # Lees van stdin
                print("Voer tekst in om te checken (Ctrl+D om te eindigen):")
                text = sys.stdin.read()

            run_standalone_check(text, input_filename, export_markdown)
        elif sys.argv[1] == "--web":
            # Start web UI
            from web_ui import launch_web_ui

            # Parse optional arguments for web UI
            host = "127.0.0.1"
            port = 7860
            share = False

            # Look for additional arguments
            for _i, arg in enumerate(sys.argv[2:], start=2):
                if arg.startswith("--host="):
                    host = arg.split("=", 1)[1]
                elif arg.startswith("--port="):
                    port = int(arg.split("=", 1)[1])
                elif arg == "--share":
                    share = True

            launch_web_ui(host=host, port=port, share=share)

        elif sys.argv[1] == "--help":
            print("""
        Fact Checker - CrewAI Multi-Agent System
        
        Gebruik:
        -------
        Fact Checking:
            python fact_checker.py --check [bestand.txt] [--markdown]
            echo "tekst om te checken" | python fact_checker.py --check [--markdown]
            
        Voorbeelden:
            python fact_checker.py --check document.txt --markdown
            python fact_checker.py --check document.txt  # Alleen JSON export
            echo "Tesla heeft 50000 werknemers" | python fact_checker.py --check --markdown
            
        Als Web UI:
            python fact_checker.py --web
            python fact_checker.py --web --host=0.0.0.0 --port=8080 --share
            
        Opties:
            --markdown      Export resultaten ook als markdown bestand (fc_*.md)
            
        In Python code:
            from fact_checker import run_fact_check_crew
            report = run_fact_check_crew("je tekst hier")
        """)
    else:
        # Default to help when run without arguments
        print("Gebruik --help voor instructies over hoe de fact checker te gebruiken.")
