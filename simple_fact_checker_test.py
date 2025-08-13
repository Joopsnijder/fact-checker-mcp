#!/usr/bin/env python3
"""
Simple Fact Checker Test - No API keys required
Auteur: Joop Snijder
"""

import sys
from pathlib import Path

def simple_fact_check_demo(text_file: str):
    """
    Demo fact checker that shows what would be checked without API calls
    """
    print("\n" + "="*60)
    print("FACT CHECKER - DEMO MODE (No API Keys Required)")
    print("="*60 + "\n")
    
    # Read the file
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{text_file}' not found")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    print(f"File: {text_file}")
    print(f"Content length: {len(content)} characters")
    print(f"Word count: {len(content.split())} words")
    
    # Simple claim detection (basic patterns)
    print("\n" + "-"*40)
    print("POTENTIAL CLAIMS DETECTED:")
    print("-"*40)
    
    lines = content.split('\n')
    claims_found = 0
    
    # Look for numerical claims
    import re
    number_patterns = [
        r'\d+%',  # Percentages
        r'\d+\s*(miljard|billion|miljoen|million)',  # Large numbers
        r'(\d{4})',  # Years
        r'\$\d+',  # Money amounts
        r'\d+\s*(users?|gebruikers?)',  # User counts
    ]
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        # Check for numbers and statistics
        for pattern in number_patterns:
            matches = re.findall(pattern, line, re.IGNORECASE)
            if matches:
                claims_found += 1
                print(f"\n[CLAIM {claims_found}] Line {i}: Statistical claim detected")
                print(f"  Text: {line[:100]}{'...' if len(line) > 100 else ''}")
                print(f"  Numbers found: {matches}")
                print(f"  → Would verify: {', '.join(matches)}")
        
        # Check for definitive statements
        definitive_words = ['is', 'has', 'was', 'will', 'can', 'moet', 'zal', 'heeft']
        if any(word in line.lower() for word in definitive_words):
            # Skip if it's just conversational
            if not any(skip in line.lower() for skip in ['i think', 'maybe', 'probably', 'ik denk', 'misschien']):
                if len(line) > 20 and any(char.isdigit() for char in line):
                    claims_found += 1
                    print(f"\n[CLAIM {claims_found}] Line {i}: Factual statement")
                    print(f"  Text: {line[:100]}{'...' if len(line) > 100 else ''}")
                    print(f"  → Would fact-check this statement")
    
    print(f"\n" + "-"*40)
    print(f"SUMMARY:")
    print(f"  Total potential claims found: {claims_found}")
    print(f"  File processed successfully")
    
    if claims_found == 0:
        print("\n  Note: This appears to be primarily conversational content")
        print("        with few verifiable factual claims.")
    else:
        print(f"\n  With API keys, this would:")
        print(f"    1. Extract and analyze each claim")
        print(f"    2. Search for authoritative sources")
        print(f"    3. Verify accuracy against multiple sources")
        print(f"    4. Generate detailed verification report")
    
    print("\n" + "="*60)
    print("To run full fact-checking, set up these environment variables:")
    print("  - OPENAI_API_KEY (for GPT-4 analysis)")
    print("  - SERPER_API_KEY (for web search, optional)")
    print("="*60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        simple_fact_check_demo(sys.argv[1])
    else:
        print("Usage: python simple_fact_checker_test.py <text_file>")