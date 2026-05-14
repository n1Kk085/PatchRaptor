import sys
import os
import argparse
import multiprocessing
from patchraptor.log_manager import logger
import traceback

def start_gui():
    """Start the GUI"""
    logger.log("Starting GUI...", level="INFO", category="SYSTEM", context={"component": "Entry"})
    try:
        # Import PatchRaptor only when needed to avoid overhead in other modes
        # PatchRaptor.py must be in the same directory or in path
        import importlib.util
        import os
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        script_path = os.path.join(root_dir, "PatchRaptor.py")
        
        if not os.path.exists(script_path):
             logger.log("PatchRaptor.py not found in root directory", level="ERROR", category="SYSTEM", context={"component": "Entry"})
             sys.exit(1)
             
        spec = importlib.util.spec_from_file_location("PatchRaptorApp", script_path)
        PatchRaptorApp = importlib.util.module_from_spec(spec)
        sys.modules["PatchRaptorApp"] = PatchRaptorApp
        spec.loader.exec_module(PatchRaptorApp)
        
        if hasattr(PatchRaptorApp, 'main'):
             PatchRaptorApp.main()
        else:
             logger.log("PatchRaptor module missing main()", level="ERROR", category="SYSTEM", context={"component": "Entry"})
             sys.exit(1)
    except ImportError as e:
        logger.log(f"Failed to import PatchRaptor GUI: {e}\nEnsure PatchRaptor.py is in the same directory.", level="ERROR", category="SYSTEM", context={"component": "Entry"})
        sys.exit(1)
    except Exception as e:
        logger.log(f"GUI crashed: {e}", level="ERROR", category="SYSTEM", context={"component": "Entry"})
        import traceback
        traceback.print_exc()
        sys.exit(1)

def start_bot():
    """Launch the Bot (main.py logic)"""
    import main
    import asyncio
    asyncio.run(main.main())

def start_web():
    """Launch Web Panel (pr_live.py logic)"""
    import pr_live
    pr_live.main()

def main():
    # Windows-specific multiprocessing fix
    multiprocessing.freeze_support()
    
    # Configure shared logger
    # logger.set_global_context(component="Entry")
    
    parser = argparse.ArgumentParser(description="PatchRaptor Unified Entry Point")
    parser.add_argument("mode", choices=["gui", "bot", "web"], nargs="?", default="gui", help="Execution mode")
    
    args = parser.parse_args()
    
    mode = args.mode
    
    logger.log(f"Starting PatchRaptor in {mode} mode", level="INFO", category="SYSTEM", context={"component": "Entry"})

    if mode == "gui":
        start_gui()
    elif mode == "bot":
        start_bot()
    elif mode == "web":
        start_web()

if __name__ == "__main__":
    main()
