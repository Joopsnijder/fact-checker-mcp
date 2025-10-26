"""
Fact Checker - Custom Agent Loop Implementation
Auteur: Joop Snijder
Versie: 3.0

Deze implementatie gebruikt een custom agent loop voor volledige controle
over parallel execution en observability met Portkey.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from agent_loop import AgentOrchestrator, ExecutionContext, create_task
from agents import (
    ClaimExtractorAgent,
    FactCheckReport,
    ReportCompilerAgent,
    ResearchSpecialistAgent,
    VerificationAnalystAgent,
)
from dotenv import load_dotenv
from pydantic import BaseModel, Field  # noqa: F401

# Load environment variables from .env file
load_dotenv()

# ============================================
# CONFIGURATIE
# ============================================

# API Keys (gebruik environment variables)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# Portkey configuration (optional - will fallback to standard Anthropic)
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY", "")
PORTKEY_PROVIDER_SLUG = os.getenv("PORTKEY_PROVIDER_SLUG", "@aitoday-anthropic")
PORTKEY_MODEL_NAME = os.getenv("PORTKEY_MODEL_NAME", "claude-sonnet-4-5-20250929")

# Note: LLM client is now initialized in agents.py via portkey_client
# Search tool is now initialized in agents.py via search_wrapper


# ============================================
# DATA MODELLEN
# ============================================
# Note: ClaimVerification and FactCheckReport are now imported from agents.py
# They are re-exported here for backward compatibility


# ============================================
# CUSTOM AGENT LOOP FACT CHECKING
# ============================================


async def run_custom_agent_loop(text: str) -> FactCheckReport:
    """
    Run de custom agent loop voor fact checking.

    Dit gebruikt onze eigen orchestration zonder CrewAI dependency.
    Agents kunnen parallel uitvoeren waar mogelijk.

    Args:
        text: De te controleren tekst

    Returns:
        FactCheckReport object met alle verificaties
    """
    # Initialize agents
    claim_extractor = ClaimExtractorAgent()
    research_specialist = ResearchSpecialistAgent()
    verification_analyst = VerificationAnalystAgent()
    report_compiler = ReportCompilerAgent()

    # Create execution context
    context = ExecutionContext(original_text=text)
    context.metadata["iteration"] = 1

    # Define tasks with dependencies
    tasks = [
        create_task(
            task_id="extract",
            description=f"Extract all verifiable claims from text:\n\n{text}",
            agent=claim_extractor,
            expected_output="List of identified claims with types",
        ),
        create_task(
            task_id="research",
            description="Research each claim using web search",
            agent=research_specialist,
            depends_on=["extract"],
            async_execution=False,  # Sequential for now to avoid rate limits
            expected_output="Research results with sources for each claim",
        ),
        create_task(
            task_id="verify",
            description="Verify each claim against research findings",
            agent=verification_analyst,
            depends_on=["extract", "research"],
            async_execution=False,
            expected_output="Verification status and analysis for each claim",
        ),
        create_task(
            task_id="compile",
            description="Compile final fact-check report",
            agent=report_compiler,
            depends_on=["verify"],
            expected_output="Complete FactCheckReport",
        ),
    ]

    # Run orchestrator
    orchestrator = AgentOrchestrator(verbose=True)
    result = await orchestrator.run(tasks, context)

    if not result.success:
        raise RuntimeError(f"Fact checking failed: {result.error}")

    # Get report from result
    report = result.report

    # Ensure timestamp is current
    if hasattr(report, "timestamp"):
        report.timestamp = datetime.now().isoformat()

    return report


def run_fact_check_crew(text: str) -> FactCheckReport:
    """
    Backward compatible wrapper for async implementation.

    This function name is kept for compatibility with existing code.

    Args:
        text: De te controleren tekst

    Returns:
        FactCheckReport object
    """
    return asyncio.run(run_custom_agent_loop(text))


# ============================================
# SIMPLIFIED FACT CHECKING (voor snelle MCP calls)
# ============================================


async def quick_fact_check(text: str) -> Dict[str, Any]:
    """
    Snelle fact check zonder full agent loop.
    Gebruikt alleen web search voor directe verificatie.

    Args:
        text: Te controleren tekst (max 500 karakters)

    Returns:
        Dict met quick check resultaten
    """
    from search_wrapper import create_search_tool

    try:
        # Initialize search tool
        search = create_search_tool()

        # Perform quick search
        search_results = search.run(f"fact check verify {text[:100]}")

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
    from search_wrapper import create_search_tool

    if len(text) > 500:
        return {
            "error": "Text te lang voor quick verify. Gebruik deep_fact_check voor langere teksten."
        }

    # Simplified version without async
    try:
        # Initialize search tool
        search = create_search_tool()

        # Perform quick search
        search_results = search.run(f"fact check verify {text[:100]}")

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
        # Use timestamp in European format (day-month-year_hour-minute-second)
        output_file = Path(f"fc_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.md")

    # Create markdown content
    markdown_content = f"""# Fact Check Report

**Generated on:** {report_data.get("timestamp", datetime.now().isoformat())}\n\n
**Document:** {original_filename}

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Overall Reliability** | {report_data.get("overall_reliability", "Unknown")} |
| **Total Claims Analyzed** | {report_data.get("total_claims", 0)} |
| **✅ Verified Claims** | {report_data.get("verified_claims", 0)} |
| **❌ False Claims** | {report_data.get("false_claims", 0)} |
| **❓ Unverifiable Claims** | {report_data.get("unverifiable_claims", 0)} |


## Detailed Verification Results

"""

    # Add individual verifications if available
    verifications = report_data.get("verifications", [])
    if verifications:
        for i, verification in enumerate(verifications, 1):
            # Add claim header with better formatting
            if "onjuist" in verification.get("verification_status", "").lower():
                icon = "❌"
            elif (
                "niet geverifieerd"
                in verification.get("verification_status", "").lower()
            ):
                icon = "❓"
            else:
                icon = "✅"

            markdown_content += f"### {icon} Claim {i}: {verification.get('claim_type', 'General').title()}\n\n"

            markdown_content += (
                f"**Original Claim**: {verification.get('original_claim', 'N/A')} \n\n"
            )
            markdown_content += f"**Verification Status**: {verification.get('verification_status', 'Unknown')} \n\n"
            markdown_content += f"**Confidence Score**: {verification.get('confidence_score', 'N/A')} \n\n"

            # Add explanation as a separate section with better formatting
            markdown_content += "#### Analysis\n\n"
            markdown_content += (
                f"{verification.get('explanation', 'No explanation provided')}\n\n"
            )

            # Add correct information if available - with appropriate styling based on verification status
            if verification.get("correct_information"):
                verification_status = verification.get("verification_status", "")
                if "onjuist" in verification_status.lower():
                    # For false claims, show what the correct information should be
                    markdown_content += "#### ❌ False Claim\n\n"
                else:
                    # For other cases where we have additional correct information
                    markdown_content += "#### ✅ Additional Information\n\n"
                markdown_content += f"{verification['correct_information']}\n\n"

            # Add sources with better formatting
            sources = verification.get("sources", [])
            if sources:
                markdown_content += "#### 📚 Sources\n\n"
                for source in sources:
                    # Make URLs clickable and add bullet points
                    if source.startswith("http"):
                        # Extract domain for display
                        domain = (
                            source.split("/")[2]
                            if len(source.split("/")) > 2
                            else source
                        )
                        markdown_content += f"- [{domain}]({source})\n"
                    else:
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

This fact check report was generated using the Fact Checker Agent, which uses multi-agent verification powered by CrewAI to analyze claims and verify information against reliable sources.

For more information or to run your own fact checks, see the [Fact Checker documentation](https://github.com/Joopsnijder/fact-checker-mcp).
"""

    # Write to file with error handling for OneDrive/cloud sync issues
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Set proper file permissions to ensure it can be opened
        # Give read/write permissions to owner, group, and others (0o644)
        import stat
        import subprocess

        os.chmod(output_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

        # Remove ALL macOS extended attributes that can cause permission issues
        # This includes quarantine, provenance, and other attributes
        try:
            subprocess.run(
                ["xattr", "-c", str(output_file)],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass  # Ignore if xattr removal fails

        return str(output_file)

    except (PermissionError, OSError) as e:
        # If we can't write to the original location (OneDrive sync issues),
        # try writing to user's Desktop as fallback
        print(
            f"Warning: Could not write to {output_file} ({e}). Trying Desktop fallback..."
        )

        desktop_path = Path.home() / "Desktop"
        if original_filename:
            original_path = Path(original_filename)
            base_name = original_path.stem
            fallback_file = desktop_path / f"fc_{base_name}.md"
        else:
            fallback_file = (
                desktop_path / f"fc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            )

        try:
            with open(fallback_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Set proper file permissions
            import stat
            import subprocess

            os.chmod(
                fallback_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
            )

            # Remove ALL macOS extended attributes
            try:
                subprocess.run(
                    ["xattr", "-c", str(fallback_file)],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass

            print(f"Fact check report saved to Desktop: {fallback_file}")
            return str(fallback_file)

        except Exception as fallback_error:
            print(
                f"Error: Could not write file to either location. Original error: {e}, Fallback error: {fallback_error}"
            )
            raise e from fallback_error


# ============================================
# MAIN ENTRY POINTS
# ============================================


def run_standalone_check(
    text: str, input_filename: str = None, export_markdown: bool = False
):
    """Run als standalone fact check applicatie"""
    print("\n" + "=" * 50)
    print("FACT CHECKER - STANDALONE MODE")
    print("=" * 50 + "\n")

    # Run fact check (returns FactCheckReport Pydantic object)
    report = run_fact_check_crew(text)

    # Convert Pydantic model to dict
    if hasattr(report, "model_dump"):
        report_data = report.model_dump()
    elif hasattr(report, "dict"):
        report_data = report.dict()
    else:
        # Fallback for unexpected types
        print(f"Warning: Unexpected report type: {type(report)}")
        report_data = {"error": "Could not parse report", "raw": str(report)}

    # Always ensure we have the current timestamp (override any AI-generated placeholders)
    report_data["timestamp"] = datetime.now().isoformat()

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

    return report


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
