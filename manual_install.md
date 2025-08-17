# Manual Installation Instructions

## Quick Install Command
```bash
# Run this from Terminal:
cp -R /Users/joopsnijder/Projects/fact-checker-mcp/FactChecker.workflow ~/Library/Services/
killall Finder
```

## Or Create New in Automator:

1. Open **Automator** (find it in Applications or use Spotlight)

2. Choose **"Quick Action"** (or "Service" on older macOS)

3. Configure the workflow:
   - Set "Workflow receives current" to: **files or folders**
   - in: **Finder.app**

4. Search for "Run Shell Script" in the actions library and drag it to the workflow

5. Configure the shell script action:
   - Shell: **/bin/bash**
   - Pass input: **as arguments**

6. Paste this exact script:
```bash
#!/bin/bash

# Get the input file path
for f in "$@"
do
    /Users/joopsnijder/Projects/fact-checker-mcp/fact_check_automator.sh "$f"
done
```

7. Save it as "Fact Check Document" (⌘S)

## After Installation:

### Make it appear in Finder:
1. **Restart Finder**: Press ⌥⌘ESC, select Finder, click Relaunch
2. Or run: `killall Finder` in Terminal

### Check if it's enabled:
1. Go to **System Settings** (or System Preferences)
2. Navigate to **Privacy & Security** → **Extensions** → **Finder**
3. Make sure "Fact Check Document" is checked ✓

### Test it:
1. Right-click any `.txt` or `.md` file
2. Look for **Quick Actions** submenu
3. You should see "Fact Check Document"

## Troubleshooting:

### If Quick Actions menu doesn't appear:
- Make sure you're right-clicking on a text file (not a folder)
- Try a simple `.txt` file first
- Some file types might not trigger the action

### If the action appears but doesn't work:
Check that the script is executable:
```bash
chmod +x /Users/joopsnijder/Projects/fact-checker-mcp/fact_check_automator.sh
```

### To see error messages:
Open Console.app and filter for "fact" or "automator" while running the action

## Alternative: Make an App

If Quick Actions don't work, create an app instead:
1. In Automator, choose "Application" instead of "Quick Action"
2. Add the same Run Shell Script action
3. Save as "Fact Checker.app" to your Applications folder
4. Drag text files onto the app icon to process them