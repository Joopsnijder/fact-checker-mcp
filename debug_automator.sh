#!/bin/bash

# Debug version of the automator script
# This version shows more detailed output for troubleshooting

echo "=== DEBUG FACT CHECKER AUTOMATOR ==="
echo "Input file: $1"

# Get the input file path
INPUT_FILE="$1"

# Check if file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Error: File not found: $INPUT_FILE"
    exit 1
fi

# Set up paths
FACT_CHECKER_DIR="/Users/joopsnijder/Projects/fact-checker-mcp"
PYTHON_PATH="$FACT_CHECKER_DIR/.venv/bin/python"
FACT_CHECKER_SCRIPT="$FACT_CHECKER_DIR/fact-checker.py"

echo "Fact checker dir: $FACT_CHECKER_DIR"
echo "Python path: $PYTHON_PATH"
echo "Script path: $FACT_CHECKER_SCRIPT"

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ Error: Python virtual environment not found at $PYTHON_PATH"
    exit 1
fi

# Get file info
FILENAME=$(basename "$INPUT_FILE")
DIR_PATH=$(dirname "$INPUT_FILE")
BASE_NAME_NO_EXT="${FILENAME%.*}"

echo "Filename: $FILENAME"
echo "Directory: $DIR_PATH" 
echo "Base name (no ext): $BASE_NAME_NO_EXT"

# Change to the fact-checker directory
echo "Changing to fact-checker directory..."
cd "$FACT_CHECKER_DIR"

# Set up log files with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$DIR_PATH/fact_check_log_${TIMESTAMP}.txt"
ERROR_FILE="$DIR_PATH/fact_check_error_${TIMESTAMP}.txt"

echo "Log file: $LOG_FILE"
echo "Error file: $ERROR_FILE"

echo ""
echo "🚀 Starting fact check..."
echo "Command: \"$PYTHON_PATH\" \"$FACT_CHECKER_SCRIPT\" --check \"$INPUT_FILE\" --markdown"

# Run fact checker
"$PYTHON_PATH" "$FACT_CHECKER_SCRIPT" --check "$INPUT_FILE" --markdown > "$LOG_FILE" 2> "$ERROR_FILE"
EXIT_CODE=$?

echo ""
echo "✅ Fact check completed with exit code: $EXIT_CODE"

# Show what files were created
echo ""
echo "📁 Files in output directory:"
ls -la "$DIR_PATH"/ | grep -E "(fc_|fact_check)"

echo ""
echo "🔍 Looking for markdown files..."

# Expected markdown file
EXPECTED_MARKDOWN="$DIR_PATH/fc_${BASE_NAME_NO_EXT}.md"
echo "Expected markdown: $EXPECTED_MARKDOWN"

if [ -f "$EXPECTED_MARKDOWN" ]; then
    echo "✅ Found expected markdown file!"
    echo "📄 Opening: $EXPECTED_MARKDOWN"
    open "$EXPECTED_MARKDOWN"
else
    echo "❌ Expected markdown file not found"
    
    # Look for any fc_*.md files
    echo "🔍 Searching for any fc_*.md files in $DIR_PATH..."
    FC_FILES=$(ls "$DIR_PATH"/fc_*.md 2>/dev/null)
    
    if [ -n "$FC_FILES" ]; then
        echo "✅ Found fc_*.md files:"
        echo "$FC_FILES"
        # Open the first one found
        FIRST_FC=$(echo "$FC_FILES" | head -n 1)
        echo "📄 Opening: $FIRST_FC"
        open "$FIRST_FC"
    else
        echo "❌ No fc_*.md files found"
        
        # Check for JSON files
        JSON_FILES=$(ls "$DIR_PATH"/*fact_check*.json 2>/dev/null)
        if [ -n "$JSON_FILES" ]; then
            echo "✅ Found JSON files:"
            echo "$JSON_FILES"
        else
            echo "❌ No fact_check JSON files found either"
        fi
        
        # Show recent errors if any
        if [ -f "$ERROR_FILE" ]; then
            echo ""
            echo "🚨 Last few lines from error log:"
            tail -n 10 "$ERROR_FILE"
        fi
        
        echo ""
        echo "🗂️ Opening output directory for manual inspection..."
        open "$DIR_PATH"
    fi
fi

echo ""
echo "=== DEBUG COMPLETE ==="