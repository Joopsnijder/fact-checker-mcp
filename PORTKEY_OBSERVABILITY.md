# Portkey Observability

De fact-checker integreert met [Portkey](https://portkey.ai) voor complete LLM observability en cost tracking.

## Setup

### 1. Verkrijg Portkey API Key

Registreer op [portkey.ai](https://portkey.ai) en verkrijg je API key.

### 2. Configureer Environment Variables

Voeg toe aan je `.env` file:

```bash
# Portkey Observability (optioneel)
PORTKEY_API_KEY=your_portkey_api_key
PORTKEY_PROVIDER_SLUG=@aitoday-anthropic  # Je Portkey provider slug
PORTKEY_MODEL_NAME=claude-sonnet-4-5-20250929
```

### 3. Run Fact Checker

De Portkey integratie is automatisch actief als `PORTKEY_API_KEY` is gezet:

```bash
python fact-checker.py --check document.txt
# Output: 🔍 Portkey observability enabled (Model Catalog)
```

## Metadata Tracking

Elke LLM call naar Anthropic wordt getagd met metadata:

```python
{
    "project": "fact-checker-mcp",  # Application identifier
    "agent": "claim_extractor",     # Welke agent (extract/research/verify/compile)
    "phase": "extract",             # Welke fase
    "user": "joopsnijder",         # System user
    "environment": "development",   # Dev/production
    "iteration": 1,                 # Retry iteration
    "text_length": 500,            # Additional context
}
```

## Dashboard Filtering

In het Portkey dashboard kun je filteren op:

### Per Project
```
project = "fact-checker-mcp"
```
Toont alle calls van deze applicatie

### Per Agent
```
agent = "claim_extractor"
agent = "research_specialist"
agent = "verification_analyst"
agent = "report_compiler"
```
Toont calls per agent

### Per Phase
```
phase = "extract"    # Claim extraction
phase = "research"   # Web research
phase = "verify"     # Claim verification
phase = "compile"    # Report compilation
```

### Per Environment
```
environment = "development"
environment = "production"
```

## Cost Tracking

Portkey dashboard toont:
- **Total cost** per fact check
- **Cost per agent** (welke agent is duurst?)
- **Token usage** (input/output tokens)
- **Latency** (response times)
- **Cache hits** (prompt caching effectiveness)

## Analytics Examples

**Vraag**: Welke agent kost het meest?
```
Group by: agent
Metric: total_cost
```

**Vraag**: Hoeveel tokens gebruikt de research phase?
```
Filter: phase = "research"
Metric: sum(input_tokens + output_tokens)
```

**Vraag**: Wat is de gemiddelde latency per fase?
```
Group by: phase
Metric: avg(latency_ms)
```

## Fallback

Als `PORTKEY_API_KEY` niet is gezet, valt de fact-checker automatisch terug naar de standaard Anthropic client zonder observability.

```bash
# Zonder Portkey
unset PORTKEY_API_KEY
python fact-checker.py --check document.txt
# Werkt normaal, maar zonder tracking
```

## Troubleshooting

### Portkey import error
```bash
pip install portkey-ai
```

### API key niet werkend
Controleer of je API key correct is en actief in je Portkey dashboard.

### Geen data in dashboard
- Verificeer dat `PORTKEY_API_KEY` is gezet
- Check of je de juiste `PORTKEY_PROVIDER_SLUG` gebruikt
- Wacht enkele seconden - data kan vertraagd verschijnen
