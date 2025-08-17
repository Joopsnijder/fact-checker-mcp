#!/usr/bin/env python3
"""Test the improved markdown formatting"""

import sys
import importlib.util
from pathlib import Path
from datetime import datetime

# Import the module
spec = importlib.util.spec_from_file_location("fact_checker", "fact-checker.py")
fact_checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fact_checker)

# Create test data
test_report = {
    'original_text': 'Je vraagt ChatGPT iets en krijgt een perfect kloppend antwoord.',
    'total_claims': 2,
    'verified_claims': 1,
    'false_claims': 0,
    'unverifiable_claims': 1,
    'overall_reliability': 'Medium',
    'summary': 'De claims zijn gedeeltelijk waar. ChatGPT geeft over het algemeen goede antwoorden, maar niet altijd perfect.',
    'timestamp': datetime.now().isoformat(),
    'verifications': [
        {
            'original_claim': 'Je vraagt ChatGPT iets en krijgt een perfect kloppend antwoord',
            'claim_type': 'Scientific',
            'verification_status': 'Partially True',
            'confidence_score': 0.7,
            'correct_information': 'ChatGPT geeft over het algemeen nauwkeurige antwoorden, maar is niet altijd perfect.',
            'sources': [
                'https://botpress.com/nl/blog/how-accurate-is-chatgpt-in-providing-information-or-answers',
                'https://openai.com/research/gpt-4',
                'https://arxiv.org/abs/2303.08774'
            ],
            'explanation': 'Hoewel ChatGPT over het algemeen nauwkeurige antwoorden geeft, is het niet altijd perfect.'
        },
        {
            'original_claim': 'AI models kunnen context windows tot 1 miljoen tokens aan',
            'claim_type': 'Technical',
            'verification_status': 'Verified',
            'confidence_score': 0.95,
            'correct_information': 'Enkele moderne AI modellen zoals Gemini 1.5 Pro kunnen inderdaad tot 1 miljoen tokens verwerken.',
            'sources': [
                'https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/gemini',
                'https://blog.google/technology/ai/google-gemini-next-generation-model-february-2024/'
            ],
            'explanation': 'Dit is correct voor bepaalde modellen zoals Google Gemini 1.5 Pro.'
        }
    ]
}

# Generate markdown
output_file = fact_checker.export_to_markdown(test_report, "test_document.txt")

print(f"✅ Markdown file created: {output_file}")
print("\n" + "="*50)
print("PREVIEW OF FORMATTED MARKDOWN:")
print("="*50 + "\n")

# Read and display the file
with open(output_file, 'r') as f:
    content = f.read()
    # Show first 100 lines
    lines = content.split('\n')
    for line in lines[:100]:
        print(line)

print("\n" + "="*50)
print(f"✅ Full report saved to: {output_file}")
print("Open it in a markdown viewer to see the formatted result!")