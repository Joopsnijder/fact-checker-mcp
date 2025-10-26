# Fact Checker - Mac Automator Quick Action

This setup allows you to right-click any text file in Finder and run a fact check on it directly.

## 🚀 Quick Installation

```bash
# From the fact-checker-mcp directory, run:
./install_automator.sh
```

## 📋 What Gets Installed

1. **Quick Action**: "Fact Check Document" in your right-click menu
2. **Shell Script**: `fact_check_automator.sh` - handles the processing
3. **Workflow**: Installed to `~/Library/Services/FactChecker.workflow`

## 🎯 How to Use

1. **Right-click** any text file (`.txt`, `.md`, etc.) in Finder
2. Select **Quick Actions** → **Fact Check Document**
3. You'll see a notification that processing has started
4. When complete, the markdown report opens automatically
5. Files are saved in the same folder as your input file:
   - `fc_[filename].md` - Markdown report
   - `[filename]_fact_check_[timestamp].json` - JSON data

## 🛠 Manual Installation

If the automatic installation doesn't work:

### Option 1: Using Automator App

1. Open **Automator** (in Applications)
2. Choose **Quick Action** (or Service on older macOS)
3. Set "Service receives selected" to **files or folders** in **Finder**
4. Add a **Run Shell Script** action
5. Set "Pass input" to **as arguments**
6. Paste this script:

```bash
for f in "$@"
do
    /Users/joopsnijder/Projects/fact-checker-mcp/fact_check_automator.sh "$f"
done
```

7. Save as "Fact Check Document"

### Option 2: Double-click Installation

1. Navigate to the `fact-checker-mcp` folder in Finder
2. Double-click `FactChecker.workflow`
3. Click "Install" when prompted
4. The Quick Action is now available in your right-click menu

## ⚙️ Configuration

### Customize the Script

Edit `fact_check_automator.sh` to change:
- Python environment path
- Notification messages
- File opening behavior

### System Preferences

Manage the Quick Action in:
**System Preferences** → **Extensions** → **Finder** → **Fact Check Document**

## 🔧 Troubleshooting

### Quick Action doesn't appear
1. Check if installed: `ls ~/Library/Services/`
2. Restart Finder: `killall Finder`
3. Check System Preferences → Extensions → Finder

### Error: Python environment not found
1. Ensure virtual environment exists:
   ```bash
   cd /Users/joopsnijder/Projects/fact-checker-mcp
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

### Error: Permission denied
1. Make scripts executable:
   ```bash
   chmod +x fact_check_automator.sh
   chmod +x install_automator.sh
   ```

### Fact check takes too long
- The first run may take longer as models load
- Complex documents with many claims take more time
- Check Activity Monitor for Python process

## 📱 Alternative: Command Line

If you prefer the terminal:

```bash
# Direct command
python fact-checker.py --check /path/to/file.txt --markdown

# Create an alias in ~/.zshrc or ~/.bash_profile
alias factcheck='python /Users/joopsnijder/Projects/fact-checker-mcp/fact-checker.py --check'

# Then use:
factcheck document.txt --markdown
```

## 🗑 Uninstall

To remove the Quick Action:

```bash
rm -rf ~/Library/Services/FactChecker.workflow
```

Or via System Preferences → Extensions → Finder → Uncheck "Fact Check Document"

## 📝 File Types Supported

The Quick Action works with:
- `.txt` - Plain text files
- `.md` - Markdown files  
- `.text` - Text documents
- Any file macOS recognizes as text

## 🎨 Customization Ideas

### Add to Touch Bar
If you have a MacBook with Touch Bar:
1. System Preferences → Extensions → Touch Bar
2. Customize Control Strip
3. Add Quick Actions

### Keyboard Shortcut
1. System Preferences → Keyboard → Shortcuts
2. Services → Fact Check Document
3. Add your preferred shortcut (e.g., ⌘⇧F)

### Multiple Languages
Modify `fact_check_automator.sh` to detect file language and adjust accordingly.

## 🐛 Debug Mode

### Log Files

**Log files are now automatically preserved!** Every fact-check run creates timestamped log files:

- `fact_check_log_YYYYMMDD_HHMMSS.txt` - Standard output and progress
- `fact_check_error_YYYYMMDD_HHMMSS.txt` - Errors and warnings

These files are saved in the same directory as your input file and are **never deleted**.

### Using Debug Script

For detailed debugging output, use the debug script:

```bash
./debug_automator.sh "/path/to/your/document.txt"
```

This provides detailed step-by-step output to help diagnose issues.

## 💡 Tips

1. **Batch Processing**: Select multiple files and run the Quick Action on all at once
2. **Preview**: Press Space on the generated `.md` file for quick preview
3. **Integration**: The markdown reports work great with Obsidian, Notion, etc.

## 📚 Examples

### Fact-checking a blog post
```
Right-click → blog_post.txt → Quick Actions → Fact Check Document
Output: fc_blog_post.md
```

### Fact-checking meeting notes
```
Right-click → meeting_notes.md → Quick Actions → Fact Check Document  
Output: fc_meeting_notes.md
```

## 🔗 Related

- [Main README](README.md) - General fact-checker documentation
- [Web UI](web_ui.py) - Browser-based interface
- [API Usage](fact-checker.py) - Python API documentation