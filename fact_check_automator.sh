#!/bin/bash

# Fact Checker Automator Script
# This script is designed to be called from Mac Automator
# It processes the selected file and runs the fact checker

# Get the input file path
INPUT_FILE="$1"

# Check if file exists
if [ ! -f "$INPUT_FILE" ]; then
    osascript -e "display dialog \"Error: File not found: $INPUT_FILE\" buttons {\"OK\"} default button \"OK\" with icon stop"
    exit 1
fi

# Set up paths
FACT_CHECKER_DIR="/Users/joopsnijder/Projects/fact-checker-mcp"
PYTHON_PATH="$FACT_CHECKER_DIR/.venv/bin/python"
FACT_CHECKER_SCRIPT="$FACT_CHECKER_DIR/fact-checker.py"

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    osascript -e "display dialog \"Error: Python virtual environment not found. Please ensure the fact-checker is properly installed.\" buttons {\"OK\"} default button \"OK\" with icon stop"
    exit 1
fi

# Get the filename for display
FILENAME=$(basename "$INPUT_FILE")
DIR_PATH=$(dirname "$INPUT_FILE")

# Show progress notification
osascript -e "display notification \"Starting fact check for $FILENAME\" with title \"Fact Checker\" subtitle \"Processing...\""

# Change to the fact-checker directory
cd "$FACT_CHECKER_DIR"

# Run the fact checker with markdown export
# Redirect output to a log file for debugging
LOG_FILE="$DIR_PATH/fact_check_log.txt"
ERROR_FILE="$DIR_PATH/fact_check_error.txt"

# Run fact checker
"$PYTHON_PATH" "$FACT_CHECKER_SCRIPT" --check "$INPUT_FILE" --markdown > "$LOG_FILE" 2> "$ERROR_FILE"

# Check if the command was successful
if [ $? -eq 0 ]; then
    # Success - find the generated markdown file
    MARKDOWN_FILE="$DIR_PATH/fc_$(basename "$INPUT_FILE" .txt).md"
    JSON_FILE="$DIR_PATH/$(basename "$INPUT_FILE" .txt)_fact_check_*.json"
    
    # Check if markdown file was created
    if [ -f "$MARKDOWN_FILE" ]; then
        # Show success notification
        osascript -e "display notification \"Fact check complete! Results saved to fc_$(basename "$INPUT_FILE" .txt).md\" with title \"Fact Checker\" subtitle \"Success\" sound name \"Glass\""
        
        # Open the markdown file in the default editor
        open "$MARKDOWN_FILE"
    else
        # Look for any fc_*.md file created in the last minute
        RECENT_MD=$(find "$DIR_PATH" -name "fc_*.md" -mmin -1 -type f | head -n 1)
        if [ -n "$RECENT_MD" ]; then
            osascript -e "display notification \"Fact check complete! Results saved to $(basename "$RECENT_MD")\" with title \"Fact Checker\" subtitle \"Success\" sound name \"Glass\""
            open "$RECENT_MD"
        else
            osascript -e "display dialog \"Fact check completed but markdown file not found. Check $DIR_PATH for results.\" buttons {\"OK\"} default button \"OK\" with icon caution"
        fi
    fi
else
    # Error occurred
    ERROR_MSG=$(tail -n 5 "$ERROR_FILE" | tr '\n' ' ')
    osascript -e "display dialog \"Error during fact check: $ERROR_MSG\" buttons {\"OK\"} default button \"OK\" with icon stop"
fi

# Clean up log files if successful
if [ $? -eq 0 ]; then
    rm -f "$LOG_FILE" "$ERROR_FILE"
fi