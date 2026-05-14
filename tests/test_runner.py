import subprocess
import sys
import re
import os

# ANSI Color Codes
PR_BLUE = "\033[38;2;52;152;219m"  # PatchRaptor Blue (approx #3498db)
PR_ORANGE = "\033[38;2;230;126;34m" # Orange for failure
RESET = "\033[0m"

def translate_name(nodeid):
    """Translate pytest nodeid to simple readable text."""
    parts = nodeid.split('::')
    if len(parts) >= 2:
        file_part = parts[0]
        method_part = parts[-1]
        
        # Clean file name
        file_clean = file_part.replace('tests/test_', '').replace('tests\\test_', '').replace('.py', '').replace('_', ' ').title()
        
        # Clean method name
        method_clean = method_part.replace('test_', '').replace('_', ' ').capitalize()
        
        return f"{file_clean} > {method_clean}"
    return nodeid

def run():
    print(f"{PR_BLUE}========================================{RESET}")
    print(f"{PR_BLUE}PatchRaptor Simple Test Runner{RESET}")
    print(f"{PR_BLUE}========================================{RESET}\n")
    
    # Enable ANSI escape sequences in Windows terminal
    os.system("")
    
    # Ensure pytest is installed
    try:
        import pytest
    except ImportError:
        print("ERROR: pytest is not installed. Please run: pip install -r requirements-dev.txt")
        sys.exit(1)

    print("Running tests, please wait...\n")
    
    # Run pytest and capture output
    # We pass --color=no so we can parse cleanly and add our own colors
    pytest_args = [sys.executable, "-m", "pytest", "-c", "tests/pytest.ini", "-v", "--color=no"] + sys.argv[1:]
    process = subprocess.Popen(
        pytest_args, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    for line in iter(process.stdout.readline, ''):
        # Match test progress lines
        # e.g.: tests/test_backup_manager.py::TestBackupManagerInit::test_init_with_paths PASSED [  3%]
        # Need to handle Windows paths too sometimes
        match = re.match(r'^((?:tests/|tests\\).*?\.py::[^\s]+)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s+\[\s*(\d+%)\s*\]', line)
        if match:
            nodeid, status, percent = match.groups()
            translated = translate_name(nodeid)
            
            # Determine color
            color = PR_ORANGE if status in ("FAILED", "ERROR") else PR_BLUE
            
            # Format: "File > Method .............................. [ PASSED ] [ 10%]"
            # The % uses the color, the text can be default or colored
            
            # Ensure perfect alignment by truncating excessively long test names
            if len(translated) > 90:
                translated = translated[:87] + "..."
                
            padding_len = max(5, 95 - len(translated))
            padding = "." * padding_len
            
            if status in ("FAILED", "ERROR"):
                print(f"{PR_ORANGE}{translated} {padding} [ {status:6} ] [ {percent:>4} ]{RESET}")
            else:
                print(f"{translated} {padding} [ {status:6} ] {color}[ {percent:>4} ]{RESET}")
        elif "===========================" in line:
            # Color summary lines
            color = PR_ORANGE if "failed" in line.lower() or "error" in line.lower() else PR_BLUE
            print(f"{color}{line.strip()}{RESET}")
        else:
            # Print tracebacks and other stuff as is
            print(line, end="")
            
    process.wait()
    
    print(f"\n{PR_BLUE}========================================{RESET}")
    print(f"{PR_BLUE}Test run complete.{RESET}")
    print(f"{PR_BLUE}========================================{RESET}")
    
    sys.exit(process.returncode)

if __name__ == "__main__":
    run()
