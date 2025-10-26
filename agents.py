"""
Fact Checking Agents
Four specialized agents for the fact-checking pipeline
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agent_loop import BaseAgent, ExecutionContext, Task
from portkey_client import create_metadata, get_anthropic_client
from search_wrapper import create_search_tool

# Initialize Anthropic client with Portkey
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
anthropic_client = get_anthropic_client(ANTHROPIC_API_KEY)

# Initialize search tool
search_tool = create_search_tool()


# ============================================
# DATA MODELS
# ============================================


class ClaimVerification(BaseModel):
    """Model voor individuele claim verificatie"""

    original_claim: str = Field(description="De originele claim uit de tekst")
    claim_type: str = Field(description="Type: statistiek, feit, quote, datum, etc.")
    verification_status: str = Field(
        description="Status: Geverifieerd en correct, Geverifieerd en onjuist, Niet geverifieerd, Niet onderzocht"
    )
    confidence_score: float = Field(description="Betrouwbaarheidsscore 0-1")
    correct_information: str | None = Field(
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
# AGENT 1: CLAIM EXTRACTOR
# ============================================


class ClaimExtractorAgent(BaseAgent):
    """
    Extract verifiable claims from text.

    This agent identifies all factual claims that can be verified,
    including statistics, historical facts, quotes, and scientific claims.
    """

    def __init__(self):
        super().__init__(
            name="claim_extractor",
            role="Claim Extractor",
            goal="Identificeer alle verifieerbare claims, statistieken en feitelijke uitspraken in de tekst",
            backstory="""Je bent een expert in het analyseren van teksten en het identificeren
            van claims die geverifieerd kunnen worden. Je hebt jarenlange ervaring met het
            onderscheiden van meningen van feiten.""",
        )
        self.client = anthropic_client

    async def execute(
        self, task: Task, context: ExecutionContext
    ) -> List[Dict[str, str]]:
        """
        Extract claims from the text.

        Returns:
            List of dicts with claim information
        """
        self.log("Extracting claims from text...")

        # Get text from task description or context
        text = context.original_text or task.description

        system_prompt = """Je bent een expert claim extractor. Analyseer de gegeven tekst en identificeer ALLE verifieerbare claims.

Identificeer specifiek:
1. Statistieken en getallen
2. Historische feiten en datums
3. Quotes toegeschreven aan personen
4. Wetenschappelijke claims
5. Bedrijfsinformatie
6. Geografische of demografische feiten

Focus alleen op verifieerbare feiten, geen meningen.

Return je antwoord als een JSON array van objecten, elk met:
- original_claim: de letterlijke claim uit de tekst
- claim_type: het type claim (statistiek, historisch_feit, quote, etc.)

Voorbeeld output:
[
    {"original_claim": "Tesla heeft 50.000 werknemers", "claim_type": "statistiek"},
    {"original_claim": "Einstein zei 'Verbeelding is belangrijker dan kennis'", "claim_type": "quote"}
]"""

        # Create metadata for Portkey tracking
        metadata = create_metadata(
            agent="claim_extractor",
            phase="extract",
            text_length=len(text),
            iteration=context.metadata.get("iteration", 1),
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8192,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Analyseer deze tekst en extraheer alle verifieerbare claims:\n\n{text}",
                    }
                ],
                metadata=metadata,
            )

            # Extract text from response
            response_text = response.content[0].text

            # Parse JSON response
            try:
                # Try to find JSON in the response
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()

                claims = json.loads(response_text)

                if not isinstance(claims, list):
                    claims = [claims]

                self.log(f"Extracted {len(claims)} claims")
                return claims

            except json.JSONDecodeError as e:
                self.log(f"Failed to parse JSON response: {e}", level="warning")
                # Fallback: return raw response wrapped in a claim
                return [
                    {
                        "original_claim": "Failed to parse claims",
                        "claim_type": "error",
                        "error": str(e),
                        "raw_response": response_text[:500],
                    }
                ]

        except Exception as e:
            self.log(f"Error during claim extraction: {e}", level="error")
            raise


# ============================================
# AGENT 2: RESEARCH SPECIALIST
# ============================================


class ResearchSpecialistAgent(BaseAgent):
    """
    Research claims using web search.

    Uses multi-search-api to find authoritative sources for each claim.
    """

    def __init__(self):
        super().__init__(
            name="research_specialist",
            role="Research Specialist",
            goal="Zoek betrouwbare bronnen om claims te verifiëren",
            backstory="""Je bent een onderzoeksexpert met toegang tot het internet.
            Je specialiteit is het vinden van autoritatieve bronnen.""",
        )
        self.client = anthropic_client
        self.search_tool = search_tool

    async def execute(
        self, task: Task, context: ExecutionContext
    ) -> List[Dict[str, Any]]:
        """
        Research each claim using web search.

        Returns:
            List of dicts with research results for each claim
        """
        self.log("Researching claims...")

        # Get claims from context
        claims = context.get("extract", [])

        if not claims:
            self.log("No claims found in context", level="warning")
            return []

        research_results = []

        for claim in claims:
            claim_text = claim.get("original_claim", "")
            claim_type = claim.get("claim_type", "unknown")

            self.log(f"Researching claim: {claim_text[:50]}...")

            # Perform web search
            search_query = f"fact check verify {claim_text}"
            search_results = self.search_tool.run(search_query)

            # Store research result
            research_results.append(
                {
                    "claim": claim_text,
                    "claim_type": claim_type,
                    "search_query": search_query,
                    "search_results": search_results,
                }
            )

        self.log(f"Completed research for {len(research_results)} claims")
        return research_results


# ============================================
# AGENT 3: VERIFICATION ANALYST
# ============================================


class VerificationAnalystAgent(BaseAgent):
    """
    Verify claims against research findings.

    Analyzes search results and determines the veracity of each claim.
    """

    def __init__(self):
        super().__init__(
            name="verification_analyst",
            role="Fact Verification Analyst",
            goal="Vergelijk claims met gevonden bronnen en bepaal waarheidsgehalte",
            backstory="""Je bent een analyticus gespecialiseerd in fact-checking.
            Je maakt genuanceerde oordelen over de waarheid van claims.

            BELANGRIJKE REGELS VOOR VERIFICATION_STATUS:
            - Gebruik "Geverifieerd en correct" als de claim klopt met de bronnen
            - Gebruik "Geverifieerd en onjuist" als de claim NIET klopt met de bronnen EN je hebt correcte informatie gevonden
            - Gebruik "Niet geverifieerd" alleen als je geen betrouwbare bronnen kon vinden
            - Gebruik "Niet onderzocht" als de claim niet relevant is voor fact-checking

            Als je correcte informatie vindt die de originele claim tegenspreekt, moet je:
            1. verification_status instellen op "Geverifieerd en onjuist"
            2. confidence_score instellen op 1.0
            3. correct_information vullen met de juiste informatie

            BELANGRIJK: Je neemt altijd de exacte URLs van bronnen over uit het onderzoek.""",
        )
        self.client = anthropic_client

    async def execute(
        self, task: Task, context: ExecutionContext
    ) -> List[ClaimVerification]:
        """
        Verify each claim based on research.

        Returns:
            List of ClaimVerification objects
        """
        self.log("Verifying claims...")

        # Get claims and research from context
        claims = context.get("extract", [])
        research = context.get("research", [])

        if not claims or not research:
            self.log("Missing claims or research data", level="warning")
            return []

        verifications = []

        for claim_data, research_data in zip(claims, research, strict=False):
            claim_text = claim_data.get("original_claim", "")
            claim_type = claim_data.get("claim_type", "unknown")
            search_results = research_data.get("search_results", "")

            self.log(f"Verifying claim: {claim_text[:50]}...")

            system_prompt = """Je bent een fact-checking expert. Analyseer de claim en de gevonden informatie.

VERIFICATIE REGELS:
- "Geverifieerd en correct": Claim klopt met bronnen
- "Geverifieerd en onjuist": Claim klopt NIET, je hebt correcte informatie
- "Niet geverifieerd": Geen betrouwbare bronnen gevonden
- "Niet onderzocht": Claim niet relevant voor fact-checking

Return je antwoord als JSON met:
{
    "verification_status": "...",
    "confidence_score": 0.0-1.0,
    "correct_information": "... (als claim onjuist is)",
    "sources": ["url1", "url2"],
    "explanation": "..."
}"""

            metadata = create_metadata(
                agent="verification_analyst",
                phase="verify",
                claim_type=claim_type,
                iteration=context.metadata.get("iteration", 1),
            )

            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Claim: {claim_text}\n\nClaim type: {claim_type}\n\nZoekresultaten:\n{search_results}\n\nVerifieer deze claim.",
                        }
                    ],
                    metadata=metadata,
                )

                response_text = response.content[0].text

                # Parse JSON response
                try:
                    if "```json" in response_text:
                        json_start = response_text.find("```json") + 7
                        json_end = response_text.find("```", json_start)
                        response_text = response_text[json_start:json_end].strip()
                    elif "```" in response_text:
                        json_start = response_text.find("```") + 3
                        json_end = response_text.find("```", json_start)
                        response_text = response_text[json_start:json_end].strip()

                    verification_data = json.loads(response_text)

                    # Create ClaimVerification object
                    verification = ClaimVerification(
                        original_claim=claim_text,
                        claim_type=claim_type,
                        verification_status=verification_data.get(
                            "verification_status", "Niet geverifieerd"
                        ),
                        confidence_score=float(
                            verification_data.get("confidence_score", 0.0)
                        ),
                        correct_information=verification_data.get(
                            "correct_information"
                        ),
                        sources=verification_data.get("sources", []),
                        explanation=verification_data.get(
                            "explanation", "Geen uitleg beschikbaar"
                        ),
                    )

                    verifications.append(verification)

                except json.JSONDecodeError as e:
                    self.log(f"Failed to parse verification JSON: {e}", level="warning")
                    # Create a fallback verification
                    verifications.append(
                        ClaimVerification(
                            original_claim=claim_text,
                            claim_type=claim_type,
                            verification_status="Niet geverifieerd",
                            confidence_score=0.0,
                            correct_information=None,
                            sources=[],
                            explanation=f"Parse error: {str(e)}",
                        )
                    )

            except Exception as e:
                self.log(f"Error verifying claim: {e}", level="error")
                # Create error verification
                verifications.append(
                    ClaimVerification(
                        original_claim=claim_text,
                        claim_type=claim_type,
                        verification_status="Niet geverifieerd",
                        confidence_score=0.0,
                        correct_information=None,
                        sources=[],
                        explanation=f"Error: {str(e)}",
                    )
                )

        self.log(f"Completed verification of {len(verifications)} claims")
        return verifications


# ============================================
# AGENT 4: REPORT COMPILER
# ============================================


class ReportCompilerAgent(BaseAgent):
    """
    Compile the final fact-check report.

    Creates a comprehensive report with statistics and summary.
    """

    def __init__(self):
        super().__init__(
            name="report_compiler",
            role="Report Compiler",
            goal="Stel een helder en actionable fact-check rapport samen",
            backstory="""Je bent een expert in het schrijven van heldere fact-check
            rapporten in normale, directe taal.

            TELLING REGELS VOOR STATISTIEKEN:
            - verified_claims = aantal claims met status "Geverifieerd en correct"
            - false_claims = aantal claims met status "Geverifieerd en onjuist"
            - unverifiable_claims = aantal claims met status "Niet geverifieerd" of "Niet onderzocht"
            - total_claims = som van alle bovenstaande

            BELANGRIJK: Je zorgt ervoor dat alle bronnen (URLs) uit voorgaande taken
            correct worden opgenomen in het finale rapport en dat de tellingen kloppen.""",
        )
        self.client = anthropic_client

    async def execute(self, task: Task, context: ExecutionContext) -> FactCheckReport:
        """
        Compile the final fact-check report.

        Returns:
            FactCheckReport object
        """
        self.log("Compiling final report...")

        # Get verifications from context
        verifications: List[ClaimVerification] = context.get("verify", [])
        original_text = context.original_text

        if not verifications:
            self.log("No verifications found", level="warning")
            return FactCheckReport(
                original_text=original_text,
                total_claims=0,
                verified_claims=0,
                false_claims=0,
                unverifiable_claims=0,
                overall_reliability="Onbekend",
                verifications=[],
                summary="Geen claims gevonden om te verifiëren.",
                timestamp=datetime.now().isoformat(),
            )

        # Calculate statistics
        verified_count = sum(
            1
            for v in verifications
            if "correct" in v.verification_status.lower()
            and "onjuist" not in v.verification_status.lower()
        )
        false_count = sum(
            1 for v in verifications if "onjuist" in v.verification_status.lower()
        )
        unverifiable_count = sum(
            1
            for v in verifications
            if "niet" in v.verification_status.lower()
            or "onderzocht" in v.verification_status.lower()
        )
        total_count = len(verifications)

        # Determine overall reliability
        if total_count == 0:
            reliability = "Onbekend"
        elif false_count == 0:
            reliability = "Hoog"
        elif false_count / total_count < 0.3:
            reliability = "Gemiddeld"
        else:
            reliability = "Laag"

        # Generate summary using LLM
        system_prompt = """Je bent een expert in het schrijven van fact-check samenvattingen.
        Schrijf een heldere, directe samenvatting (2-3 zinnen) van de bevindingen.
        Vermijd clichés en schrijf in normale taal."""

        verification_summary = "\n".join(
            [
                f"- {v.original_claim}: {v.verification_status}"
                for v in verifications[:5]
            ]
        )

        metadata = create_metadata(
            agent="report_compiler",
            phase="compile",
            total_claims=total_count,
            false_claims=false_count,
            iteration=context.metadata.get("iteration", 1),
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Schrijf een samenvatting voor dit fact-check rapport:\n\nTotaal claims: {total_count}\nGeverifieerd correct: {verified_count}\nOnjuist: {false_count}\nNiet geverifieerd: {unverifiable_count}\n\nBevindingen:\n{verification_summary}",
                    }
                ],
                metadata=metadata,
            )

            summary = response.content[0].text.strip()

        except Exception as e:
            self.log(f"Error generating summary: {e}", level="warning")
            summary = f"Van de {total_count} gecontroleerde claims zijn er {verified_count} correct geverifieerd, {false_count} onjuist, en {unverifiable_count} niet verifieerbaar."

        # Create final report
        report = FactCheckReport(
            original_text=original_text,
            total_claims=total_count,
            verified_claims=verified_count,
            false_claims=false_count,
            unverifiable_claims=unverifiable_count,
            overall_reliability=reliability,
            verifications=verifications,
            summary=summary,
            timestamp=datetime.now().isoformat(),
        )

        self.log("Report compilation complete")
        return report
