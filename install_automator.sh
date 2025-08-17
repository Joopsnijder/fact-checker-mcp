#!/bin/bash

# Fact Checker Automator Installation Script
# This script installs the Fact Checker as a Quick Action in macOS

echo "========================================="
echo "Fact Checker Automator Installation"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "fact-checker.py" ]; then
    echo "❌ Error: fact-checker.py not found."
    echo "Please run this script from the fact-checker-mcp directory."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found."
    echo "Please set up the Python environment first with:"
    echo "  python -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Create the Services directory if it doesn't exist
SERVICES_DIR="$HOME/Library/Services"
if [ ! -d "$SERVICES_DIR" ]; then
    echo "Creating Services directory..."
    mkdir -p "$SERVICES_DIR"
fi

# Copy the workflow to Services
WORKFLOW_NAME="FactChecker.workflow"
if [ -d "$WORKFLOW_NAME" ]; then
    echo "Installing Fact Checker Quick Action..."
    
    # Remove old version if it exists
    if [ -d "$SERVICES_DIR/$WORKFLOW_NAME" ]; then
        echo "Removing old version..."
        rm -rf "$SERVICES_DIR/$WORKFLOW_NAME"
    fi
    
    # Copy new version
    cp -R "$WORKFLOW_NAME" "$SERVICES_DIR/"
    
    if [ $? -eq 0 ]; then
        echo "✅ Fact Checker Quick Action installed successfully!"
        echo ""
        echo "📝 How to use:"
        echo "1. Right-click any text file in Finder"
        echo "2. Select 'Quick Actions' > 'Fact Check Document'"
        echo "3. Wait for the fact check to complete"
        echo "4. The markdown report will open automatically"
        echo ""
        echo "📁 Reports are saved in the same folder as the input file:"
        echo "   - fc_[filename].md (Markdown report)"
        echo "   - [filename]_fact_check_[timestamp].json (JSON data)"
        echo ""
        echo "⚙️  To customize or remove:"
        echo "   System Preferences > Extensions > Finder > Fact Check Document"
    else
        echo "❌ Error: Failed to install workflow"
        exit 1
    fi
else
    echo "❌ Error: FactChecker.workflow not found"
    echo "Please ensure the workflow files have been created."
    exit 1
fi

echo ""
echo "🎉 Installation complete!"