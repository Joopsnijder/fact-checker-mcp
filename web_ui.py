"""
Web UI voor Fact Checker - Gradio Interface
Auteur: Joop Snijder
Versie: 2.0

Gradio-gebaseerde web interface voor de Fact Checker agent
met file upload, progress tracking en resultaten weergave.

Now using custom agent loop instead of CrewAI.
"""

import asyncio

# Direct imports (no longer using importlib workaround)
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Import fact checker functions (renamed to avoid conflict with module name)
import fact_checker as fc_module
import gradio as gr

# Import from refactored fact_checker module

run_fact_check_crew = fc_module.run_fact_check_crew
quick_fact_check = fc_module.quick_fact_check
fact_check_history = fc_module.fact_check_history
add_to_history = fc_module.add_to_history
load_history = fc_module.load_history


class FactCheckerUI:
    """Web UI handler voor de Fact Checker"""

    def __init__(self):
        self.current_progress = ""
        self.is_processing = False

    def update_progress(self, message: str):
        """Update progress message"""
        self.current_progress = message
        return message

    def format_quick_results(self, result_data: Dict[str, Any]) -> str:
        """Format quick check results voor mooie weergave"""
        try:
            formatted = f"""
## 🔍 **Quick Verification Results**

**📝 Analyzed Text:**
> {result_data.get("text", "N/A")[:200]}{"..." if len(result_data.get("text", "")) > 200 else ""}

**⚡ Status:** {result_data.get("status", "Unknown")}

**🔎 Initial Search Results:**
{result_data.get("initial_search", "No search results available")[:500]}{"..." if len(str(result_data.get("initial_search", ""))) > 500 else ""}

**⏰ Completed:** {result_data.get("timestamp", "Unknown")[:19]}

---
💡 *For comprehensive verification with source analysis, use Deep Fact Check*
            """
            return formatted.strip()
        except Exception as e:
            return f"Error formatting results: {str(e)}"

    def format_deep_results(self, report: Any) -> str:
        """Format deep fact check results voor mooie weergave"""
        try:
            # Handle CrewOutput object if needed
            if hasattr(report, "pydantic") and report.pydantic:
                report = report.pydantic
            elif hasattr(report, "raw") and report.raw:
                report = report.raw
            # Calculate reliability emoji
            reliability_emoji = {"Hoog": "✅", "Gemiddeld": "⚠️", "Laag": "❌"}.get(
                report.overall_reliability, "❓"
            )

            formatted = f"""
## 🤖 **Multi-Agent Fact Check Results**

### 📊 **Overall Assessment**
{reliability_emoji} **Reliability:** {report.overall_reliability}

### 📈 **Claims Analysis**
- **Total Claims Found:** {report.total_claims}
- **✅ Verified Claims:** {report.verified_claims}
- **❌ False Claims:** {report.false_claims}
- **❓ Unverifiable Claims:** {report.unverifiable_claims}

### 📝 **Original Text**
> {report.original_text[:300]}{"..." if len(report.original_text) > 300 else ""}

### 🎯 **Executive Summary**
{report.summary}

### 🔍 **Detailed Verifications**
            """

            if report.verifications:
                for i, verification in enumerate(report.verifications, 1):
                    status_emoji = {
                        "Geverifieerd": "✅",
                        "Onwaar": "❌",
                        "Deels waar": "⚠️",
                        "Onverifieerbaar": "❓",
                    }.get(verification.verification_status, "❓")

                    formatted += f"""

**Claim {i}:** {verification.original_claim}
- **Status:** {status_emoji} {verification.verification_status}
- **Confidence:** {verification.confidence_score:.1%}
- **Type:** {verification.claim_type}
                    """

                    if verification.correct_information:
                        formatted += (
                            f"\n- **Correct Info:** {verification.correct_information}"
                        )

                    formatted += f"\n- **Explanation:** {verification.explanation}"

                    if verification.sources:
                        formatted += (
                            f"\n- **Sources:** {len(verification.sources)} source(s)"
                        )
            else:
                formatted += "\n*No detailed verifications available*"

            formatted += f"""

---
**⏰ Analysis completed:** {report.timestamp[:19]}
            """

            return formatted.strip()

        except Exception as e:
            return f"Error formatting deep results: {str(e)}"

    async def process_text_input(
        self, text: str, check_type: str
    ) -> Tuple[str, str, str, str]:
        """
        Verwerk tekst input voor fact checking

        Args:
            text: Input tekst om te controleren
            check_type: 'quick' of 'deep' verificatie

        Returns:
            Tuple van (formatted_results, samenvatting, status, raw_json)
        """
        if not text.strip():
            return "", "⚠️ Geen tekst ingevoerd", "❌ Geen tekst ingevoerd", ""

        self.is_processing = True

        try:
            start_time = datetime.now()

            if check_type == "quick":
                result = await quick_fact_check(text)

                # Parse and format result
                if isinstance(result, str):
                    result_data = json.loads(result)
                else:
                    result_data = result

                formatted_results = self.format_quick_results(result_data)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                summary = (
                    f"✅ **Snelle verificatie voltooid** in {duration:.1f} seconden"
                )
                status = f"✅ Voltooid in {duration:.1f}s"
                raw_json = json.dumps(result_data, indent=2)

                return formatted_results, summary, status, raw_json

            else:  # deep check
                # Run CrewAI fact check
                crew_output = await asyncio.to_thread(run_fact_check_crew, text)

                # Extract actual report from CrewOutput
                if hasattr(crew_output, "pydantic") and crew_output.pydantic:
                    report = crew_output.pydantic
                elif hasattr(crew_output, "raw") and crew_output.raw:
                    report = crew_output.raw
                else:
                    # Fallback: try to get the result directly
                    report = crew_output

                # Voeg toe aan geschiedenis
                add_to_history(report)

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                # Format results using our formatter
                formatted_results = self.format_deep_results(report)

                # Calculate accuracy
                if report.total_claims > 0:
                    accuracy = (
                        (report.total_claims - report.false_claims)
                        / report.total_claims
                        * 100
                    )
                    accuracy_str = f"{accuracy:.1f}%"
                else:
                    accuracy_str = "N/A"

                # Create concise summary
                summary = f"""
✅ **Deep Fact Check Voltooid**

📊 **Quick Stats:**
- **Betrouwbaarheid**: {report.overall_reliability}
- **Claims**: {report.total_claims} total, {report.false_claims} false
- **Accuracy**: {accuracy_str}
- **Duration**: {duration:.1f} seconden

⏱️ **Voltooid**: {datetime.now().strftime("%H:%M:%S")}
                """

                status = (
                    f"✅ Voltooid in {duration:.1f}s ({report.total_claims} claims)"
                )

                # Handle JSON serialization
                try:
                    if hasattr(report, "model_dump_json"):
                        raw_json = report.model_dump_json(indent=2)
                    elif hasattr(report, "model_dump"):
                        raw_json = json.dumps(report.model_dump(), indent=2)
                    else:
                        raw_json = json.dumps(report.__dict__, indent=2, default=str)
                except Exception:
                    raw_json = json.dumps(
                        {
                            "error": "Could not serialize report",
                            "type": str(type(report)),
                        },
                        indent=2,
                    )

                return formatted_results, summary, status, raw_json

        except Exception as e:
            error_msg = f"❌ **Fout opgetreden**: {str(e)}"
            status = f"❌ Fout: {str(e)}"
            return "", error_msg, status, ""
        finally:
            self.is_processing = False
            self.current_progress = ""

    async def process_file_upload(
        self, file, check_type: str
    ) -> Tuple[str, str, str, str]:
        """
        Verwerk geüploade file voor fact checking

        Args:
            file: Gradio file object
            check_type: 'quick' of 'deep' verificatie

        Returns:
            Tuple van (formatted_results, samenvatting, status, raw_json)
        """
        if file is None:
            return "", "⚠️ Geen bestand geüpload", "❌ Geen bestand geüpload", ""

        try:
            # Lees file content
            if isinstance(file, str):
                file_path = file
            else:
                file_path = file.name

            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            # Process de tekst
            return await self.process_text_input(text, check_type)

        except Exception as e:
            error_msg = f"❌ Fout bij lezen bestand: {str(e)}"
            status = f"❌ Fout: {str(e)}"
            return "", error_msg, status, ""

    def get_history_summary(self) -> str:
        """Krijg overzicht van fact check geschiedenis"""
        # Reload history from file to get latest data
        fact_check_history.clear()
        fact_check_history.extend(load_history())

        if not fact_check_history:
            return "📝 Nog geen fact checks uitgevoerd"

        summary_lines = ["📊 **Fact Check Geschiedenis**\n"]

        for i, report in enumerate(fact_check_history[-10:]):  # Laatste 10
            summary_lines.append(
                f"**{i + 1}.** {report.timestamp[:19]} - "
                f"Betrouwbaarheid: {report.overall_reliability} "
                f"({report.total_claims} claims, {report.false_claims} onjuist)"
            )

        total_claims = sum(r.total_claims for r in fact_check_history)
        total_false = sum(r.false_claims for r in fact_check_history)
        accuracy = (
            ((total_claims - total_false) / total_claims * 100)
            if total_claims > 0
            else 0
        )

        summary_lines.extend(
            [
                "\n📈 **Totaal Statistieken:**",
                f"- Rapporten: {len(fact_check_history)}",
                f"- Claims gecontroleerd: {total_claims}",
                f"- Onjuiste claims: {total_false}",
                f"- Nauwkeurigheid: {accuracy:.1f}%",
            ]
        )

        return "\n".join(summary_lines)

    def export_results(self, results_json: str) -> Optional[str]:
        """Exporteer resultaten naar JSON bestand"""
        if not results_json.strip():
            return None

        try:
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fact_check_export_{timestamp}.json"
            filepath = Path(filename)

            # Parse and save JSON
            data = json.loads(results_json)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return str(filepath.absolute())
        except Exception as e:
            return f"Export failed: {str(e)}"


def create_gradio_interface():
    """Creëer de Gradio interface"""

    ui_handler = FactCheckerUI()

    # Custom CSS voor betere styling
    custom_css = """
    .main-header {
        text-align: center;
        color: #2E86AB;
        margin-bottom: 20px;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .progress-info {
        color: #17a2b8;
        font-style: italic;
    }
    .detailed-results {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #2E86AB;
        margin: 10px 0;
    }
    .detailed-results h2 {
        color: #2E86AB;
        margin-top: 0;
    }
    .detailed-results h3 {
        color: #495057;
        margin-bottom: 10px;
    }
    .detailed-results blockquote {
        background-color: #e9ecef;
        border-left: 3px solid #6c757d;
        margin: 10px 0;
        padding: 10px 15px;
        font-style: italic;
    }
    /* Simple status styling */
    .status-running {
        background: linear-gradient(45deg, #17a2b8, #20c997) !important;
        color: white !important;
        padding: 12px 20px !important;
        border-radius: 8px !important;
        margin: 10px 0 !important;
        text-align: center !important;
        font-weight: 600 !important;
    }

    .waiting-message {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef) !important;
        border: 2px dashed #6c757d !important;
        border-radius: 8px !important;
        padding: 20px !important;
        margin: 15px 0 !important;
        text-align: center !important;
        color: #495057 !important;
    }

    /* Better accordion styling */
    .gradio-accordion {
        border: 1px solid #dee2e6 !important;
        border-radius: 8px !important;
        margin: 10px 0 !important;
    }

    .gradio-accordion summary {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef) !important;
        padding: 15px !important;
        border-radius: 8px 8px 0 0 !important;
        font-weight: 600 !important;
        color: #495057 !important;
    }
    """

    with gr.Blocks(css=custom_css, title="Fact Checker Web UI") as interface:
        # Header
        gr.Markdown(
            """
            # 🔍 Fact Checker Web Interface

            Hybrid CrewAI + MCP systeem voor uitgebreide fact-checking met multi-agent verificatie.
            """,
            elem_classes=["main-header"],
        )

        # Main tabs
        with gr.Tabs():
            # Tab 1: Fact Checking
            with gr.TabItem("🔍 Fact Checking"):
                with gr.Row():
                    with gr.Column(scale=2):
                        # Input methods
                        gr.Markdown("### 📝 Input Methode")

                        input_type = gr.Radio(
                            choices=["Tekst invoer", "Bestand upload"],
                            value="Tekst invoer",
                            label="Kies input methode",
                        )

                        # Text input
                        text_input = gr.Textbox(
                            placeholder="Voer hier de tekst in om te fact-checken...",
                            lines=10,
                            label="Tekst om te controleren",
                            visible=True,
                        )

                        # File upload
                        file_input = gr.File(
                            label="Upload tekstbestand (.txt, .md, etc.)",
                            file_types=[".txt", ".md", ".rtf"],
                            visible=False,
                        )

                        # Verification type
                        check_type = gr.Radio(
                            choices=["quick", "deep"],
                            value="deep",
                            label="Verificatie Type",
                            info="Quick = snelle check, Deep = uitgebreide multi-agent analyse",
                        )

                        # Buttons
                        with gr.Row():
                            check_btn = gr.Button(
                                "🚀 Start Fact Check", variant="primary", size="lg"
                            )
                            clear_btn = gr.Button("🗑️ Wissen", variant="secondary")

                    with gr.Column(scale=3):
                        # Simple status indicator
                        status_display = gr.Markdown("ℹ️ Klaar voor fact checking")

                        # Results
                        gr.Markdown("### 📊 Resultaten")

                        summary_output = gr.Markdown(
                            "Hier verschijnen de resultaten..."
                        )

                        # Simple waiting message
                        waiting_message = gr.Markdown(
                            "🔍 **Start een fact check om resultaten te zien**",
                            visible=True,
                        )

                        # Detailed results (collapsible)
                        with gr.Accordion("🔍 Gedetailleerde Resultaten", open=True):
                            detailed_output = gr.Markdown(
                                "Gedetailleerde resultaten verschijnen hier na fact checking...",
                                elem_classes=["detailed-results"],
                                visible=False,
                            )

                        # Raw JSON (collapsible, closed by default)
                        with gr.Accordion(
                            "🔧 Raw JSON Data (voor ontwikkelaars)", open=False
                        ):
                            json_output = gr.Code(
                                language="json",
                                label="Volledige rapport data (JSON)",
                                visible=True,
                            )

                        # Control buttons
                        with gr.Row():
                            export_btn = gr.Button(
                                "💾 Exporteer Resultaten", variant="secondary"
                            )
                            download_link = gr.File(
                                label="Download Export", visible=False
                            )

            # Tab 2: Statistic Checker (MCP Tool)
            with gr.TabItem("📊 Statistic Checker"):
                gr.Markdown("### 🔍 Specifieke Statistiek Verificatie")
                gr.Markdown(
                    "Verifieer individuele statistieken en claims met optionele context."
                )

                with gr.Row():
                    with gr.Column():
                        statistic_input = gr.Textbox(
                            placeholder="Bijv: GPT-4 heeft 175 miljard parameters",
                            label="Statistiek om te verifiëren",
                            lines=3,
                        )

                        context_input = gr.Textbox(
                            placeholder="Optionele context informatie",
                            label="Context (optioneel)",
                            lines=2,
                        )

                        year_input = gr.Number(
                            label="Jaar (optioneel)",
                            placeholder=datetime.now().year,
                            precision=0,
                        )

                        verify_stat_btn = gr.Button(
                            "🔍 Verifieer Statistiek", variant="primary"
                        )

                    with gr.Column():
                        stat_result = gr.Code(
                            language="json", label="Verificatie Resultaat"
                        )

            # Tab 3: Geschiedenis
            with gr.TabItem("📚 Geschiedenis"):
                with gr.Row():
                    refresh_history_btn = gr.Button(
                        "🔄 Ververs Geschiedenis", variant="secondary"
                    )
                    get_mcp_history_btn = gr.Button(
                        "📊 MCP Geschiedenis", variant="secondary"
                    )

                history_display = gr.Markdown("Geen geschiedenis beschikbaar")

        # Event handlers
        def toggle_input_visibility(choice):
            if choice == "Tekst invoer":
                return gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=False), gr.update(visible=True)

        input_type.change(
            fn=toggle_input_visibility,
            inputs=[input_type],
            outputs=[text_input, file_input],
        )

        def clear_inputs():
            return (
                "",  # text_input
                None,  # file_input
                "ℹ️ Invoer gewist",  # status_display
                "Hier verschijnen de resultaten...",  # summary_output
                gr.update(value="", visible=False),  # detailed_output
                "",  # json_output
                gr.update(
                    value="🔍 **Start een fact check om resultaten te zien**",
                    visible=True,
                ),  # waiting_message
            )

        clear_btn.click(
            fn=clear_inputs,
            outputs=[
                text_input,
                file_input,
                status_display,
                summary_output,
                detailed_output,
                json_output,
                waiting_message,
            ],
        )

        # Simple fact check handler with timer
        async def handle_fact_check(input_type_val, text, file, check_type_val):
            start_time = datetime.now()

            # Show simple processing message
            status_msg = f"🚀 **{check_type_val.title()} fact checking gestart** - {start_time.strftime('%H:%M:%S')}"
            waiting_msg = f"⏳ **Bezig met {check_type_val} verificatie...**\n\n{'🔍 Multi-agent analyse - kan enkele minuten duren' if check_type_val == 'deep' else '⚡ Snelle verificatie in uitvoering'}"

            # Update UI to show we're processing
            yield (
                gr.update(
                    value="", visible=False
                ),  # detailed_output - hide during processing
                gr.update(value="⏳ Processing gestart..."),  # summary_output
                gr.update(value=status_msg),  # status_display
                gr.update(value="", visible=False),  # json_output
                gr.update(value=waiting_msg, visible=True),  # waiting_message
            )

            # Perform the actual fact checking
            try:
                if input_type_val == "Tekst invoer":
                    result = await ui_handler.process_text_input(text, check_type_val)
                else:
                    result = await ui_handler.process_file_upload(file, check_type_val)

                # Update UI with results
                detailed_results, summary, status, json_data = result

                yield (
                    gr.update(
                        value=detailed_results, visible=True
                    ),  # detailed_output - show results
                    gr.update(value=summary),  # summary_output
                    gr.update(value=status),  # status_display
                    gr.update(value=json_data, visible=True),  # json_output
                    gr.update(visible=False),  # waiting_message - hide after completion
                )

            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                error_summary = f"❌ **Fout opgetreden** na {duration:.1f} seconden"
                error_status = f"❌ Fout: {str(e)}"

                yield (
                    gr.update(value="", visible=False),  # detailed_output
                    gr.update(value=error_summary),  # summary_output
                    gr.update(value=error_status),  # status_display
                    gr.update(value="", visible=False),  # json_output
                    gr.update(visible=False),  # waiting_message
                )

        check_btn.click(
            fn=handle_fact_check,
            inputs=[input_type, text_input, file_input, check_type],
            outputs=[
                detailed_output,
                summary_output,
                status_display,
                json_output,
                waiting_message,
            ],
        )

        # Statistic verification handler (placeholder - can be expanded later)
        async def handle_stat_verification(statistic, context, year):
            if not statistic.strip():
                return "Error: Geen statistiek ingevoerd"

            try:
                # For now, use quick_fact_check
                result = await quick_fact_check(statistic)
                return json.dumps(result, indent=2, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, indent=2)

        verify_stat_btn.click(
            fn=handle_stat_verification,
            inputs=[statistic_input, context_input, year_input],
            outputs=[stat_result],
        )

        # History handlers
        refresh_history_btn.click(
            fn=ui_handler.get_history_summary, outputs=[history_display]
        )

        async def get_local_history():
            """Get history from local storage."""
            try:
                history_summary = ui_handler.get_history_summary()
                return history_summary
            except Exception as e:
                return f"Error loading history: {str(e)}"

        get_mcp_history_btn.click(fn=get_local_history, outputs=[history_display])

        def handle_export(json_data):
            result = ui_handler.export_results(json_data)
            if result and result.endswith(".json"):
                return gr.update(visible=True, value=result)
            else:
                return gr.update(visible=False)

        export_btn.click(
            fn=handle_export, inputs=[json_output], outputs=[download_link]
        )

    return interface


def launch_web_ui(host: str = "127.0.0.1", port: int = 7860, share: bool = False):
    """
    Launch de Gradio web interface

    Args:
        host: Host address (default: 127.0.0.1)
        port: Port nummer (default: 7860)
        share: Create public Gradio link (default: False)
    """

    print("\n" + "=" * 60)
    print("🌐 FACT CHECKER WEB UI")
    print("=" * 60)
    print(f"🔗 Starting server on http://{host}:{port}")
    print("💡 Tip: Gebruik Deep verificatie voor uitgebreide multi-agent analyse")
    print("=" * 60 + "\n")

    interface = create_gradio_interface()

    interface.launch(
        server_name=host, server_port=port, share=share, inbrowser=True, show_error=True
    )


if __name__ == "__main__":
    launch_web_ui()
