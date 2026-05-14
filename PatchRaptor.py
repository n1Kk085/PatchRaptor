import os
import sys

#!/usr/bin/env python3
# Copyright (c) 2026 n1Kk085/PatchRaptor
# Licensed under the PATCHRAPTOR LICENSE AGREEMENT.
# See LICENSE file for details. Distribution prohibited.

"""
PatchRaptor GUI Wrapper
A GUI interface for main.py that matches config.py styling
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import customtkinter as ctk
from PIL import Image
from customtkinter import CTkImage
import subprocess
import threading
import queue
import sys
import os
import time
import psutil  # For process management
from patchraptor.gui_utils import resource_path, GUI_COLORS, GUI_FONTS

# Styling constants matching config.py
BUTTON_COLOR = GUI_COLORS["PRIMARY"]
FONT_NAME = GUI_FONTS["MAIN"]
FONT_SIZE = GUI_FONTS["SIZE"]
FRAME_COLOR = GUI_COLORS["DARK_BG"]

class PatchRaptorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PatchRaptor - Ark Server Management")
        self.root.resizable(True, True)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Process and threading variables
        self.process = None
        self.output_queue = queue.Queue()
        self.is_running = False
        self.output_thread = None
        
        # Threading synchronization
        self.output_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
        self.create_widgets()
        self.center_window()
        
        # Start reading output periodically
        self.update_output()
        
    def center_window(self):
        """Center the window on screen"""
        window_width = 800
        window_height = 900
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        pos_x = int((screen_width - window_width) / 2)
        pos_y = int((screen_height - window_height) / 2)
        
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.update_idletasks()
        self.root.geometry(f"+{pos_x}+{pos_y}")
    
    def create_widgets(self):
        """Create the GUI widgets"""
        # Load and place logo (same as config.py)
        try:
            image_path = resource_path("pr40.png")
            pil_image = Image.open(image_path)
            pil_image = pil_image.resize((40, 40), Image.Resampling.LANCZOS)
            self.logo_img = CTkImage(light_image=pil_image, dark_image=pil_image, size=(40, 40))
        except Exception as e:
            print("Failed to load image:", e)
            self.logo_img = None
        
        # Top frame with logo and title
        top_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR)
        top_frame.pack(fill="x", padx=10, pady=7)
        
        if self.logo_img:
            logo_label = ctk.CTkLabel(top_frame, image=self.logo_img, fg_color=FRAME_COLOR, text="")
            logo_label.pack(side="left", padx=(5, 5))
        
        title_label = ctk.CTkLabel(top_frame, text="PatchRaptor",
                                   text_color=BUTTON_COLOR,
                                   font=(FONT_NAME, 20, "bold"))
        title_label.pack(side="left", padx=(0, 0))
        
        # Status indicator
        self.status_label = ctk.CTkLabel(top_frame, text="● Stopped", 
                                        text_color="#ff4444",
                                        font=(FONT_NAME, 16))
        self.status_label.pack(side="right", padx=10)
        
        # Control buttons frame
        control_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR)
        control_frame.pack(fill="x", padx=10, pady=(0, 0))
        
        self.start_button = ctk.CTkButton(control_frame, text="Start Bot", width=100,
                                         fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                         command=self.start_bot,
                                         font=(FONT_NAME, FONT_SIZE))
        self.start_button.pack(side="left", padx=10, pady=10)
        
        self.stop_button = ctk.CTkButton(control_frame, text="Stop Bot", width=100,
                                        fg_color="#5B83C9", hover_color="#4665a7",
                                        command=self.stop_bot,
                                        font=(FONT_NAME, FONT_SIZE),
                                        state="disabled")
        self.stop_button.pack(side="left", padx=10, pady=10)
        
        self.clear_button = ctk.CTkButton(control_frame, text="Clear Output", width=100,
                                         fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                         command=self.clear_output,
                                         font=(FONT_NAME, FONT_SIZE))
        self.clear_button.pack(side="left", padx=10, pady=10)
        
        # Auto-scroll checkbox
        self.auto_scroll_var = ctk.BooleanVar(value=True)
        self.auto_scroll_cb = ctk.CTkCheckBox(control_frame, text="Auto-scroll",
                                             variable=self.auto_scroll_var,
                                             font=(FONT_NAME, FONT_SIZE))
        self.auto_scroll_cb.pack(side="right", padx=10, pady=10)
        
        # Output area
        output_label = ctk.CTkLabel(self.root, text="Bot Output:",
                                   text_color=BUTTON_COLOR,
                                   font=(FONT_NAME, 16, "bold"))
        output_label.pack(anchor="w", padx=22, pady=(0, 0))
        
        output_frame = ctk.CTkFrame(self.root, fg_color=FRAME_COLOR)
        output_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Create scrollable text widget
        self.output_text = ctk.CTkTextbox(output_frame, 
                                         font=(FONT_NAME, FONT_SIZE),
                                         wrap="word")
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def start_bot(self):
        """Start the main.py bot process with proper synchronization"""
        with self.state_lock:
            if self.is_running:
                return
                
            try:
                self.shutdown_event.clear()
                project_root = os.path.dirname(os.path.abspath(__file__))
                
                # Set up the environment with the project root in PYTHONPATH
                env = os.environ.copy()
                if 'PYTHONPATH' in env:
                    env['PYTHONPATH'] = project_root + os.pathsep + env['PYTHONPATH']
                else:
                    env['PYTHONPATH'] = project_root
                
                # Use the Python interpreter and main.py directly
                if getattr(sys, 'frozen', False):
                    # Running as compiled exe
                    # In one-file mode, sys.executable is the path to the exe itself
                    # We want the CWD to be where the exe is, not the temp folder
                    base_dir = os.path.dirname(sys.executable)
                    cmd = [os.path.join(base_dir, "Instinct.exe")]
                    cwd_path = base_dir  # Run in the exe folder
                else:
                    # Running as script
                    cmd = [sys.executable, "main.py"]
                    cwd_path = project_root # Run in the source folder
                
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1,
                    startupinfo=startupinfo,
                    cwd=cwd_path,
                    env=env  # Pass the modified environment
                )
                
                self.is_running = True
                self.start_button.configure(state="disabled")
                self.stop_button.configure(state="normal")
                self.status_label.configure(text="● Running", text_color=GUI_COLORS["SUCCESS"])
                
                self.output_thread = threading.Thread(target=self.read_output, daemon=True)
                self.output_thread.start()
                self.append_output("=== PatchRaptor Started ===\n")
                
            except Exception as e:
                self.is_running = False
                messagebox.showerror("Error", f"Failed to start bot:\n{str(e)}")
                self.status_label.configure(text="● Failed to start", text_color=GUI_COLORS["DANGER"])
    
    def stop_bot(self, force_kill=False):
        """Stop the bot process with proper synchronization
        
        Args:
            force_kill (bool): If True, force kill the process tree. Used when closing the app.
        """
        with self.state_lock:
            if not self.is_running:
                return
            
            try:
                # Signal shutdown to output thread
                self.shutdown_event.set()
                
                if self.process:
                    try:
                        # Always use psutil for a more robust cross-platform process tree termination
                        # This ensures child processes like cloudflared and RaptorChat are also killed
                        try:

                            parent = psutil.Process(self.process.pid)
                            for child in parent.children(recursive=True):
                                try:
                                    child.terminate()
                                except psutil.NoSuchProcess:
                                    pass
                            gone, alive = psutil.wait_procs(parent.children(), timeout=3)
                            for p in alive:
                                p.kill()
                            parent.terminate()
                            parent.wait(3)
                            if parent.is_running():
                                parent.kill()
                        except psutil.NoSuchProcess:
                            pass
                            
                        # Double check standard termination just in case psutil missed the handle
                        if self.process.poll() is None:
                            self.process.terminate()
                            try:
                                self.process.wait(timeout=1)
                            except subprocess.TimeoutExpired:
                                self.process.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                        self.append_output(f"Could not fully clean up process: {e}\n")
                    except Exception as e:
                        self.append_output(f"Error during process cleanup: {str(e)}\n")
                    finally:
                        self.process = None
                
                self.is_running = False
                
                # Update UI
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_label.configure(text="● Stopped", text_color="#ff4444")
                            
                self.append_output("=== PatchRaptor Stopped ===\n")
                
            except Exception as e:
                self.is_running = False
                self.append_output(f"Error stopping bot: {str(e)}\n")
                self.status_label.configure(text=f"Error stopping: {str(e)}")
                # Ensure we still clean up the process reference
                if hasattr(self, 'process') and self.process:
                    try:
                        self.process.kill()
                    except:
                        pass
                    self.process = None
    
    def read_output(self):
        """Read output from the process in a separate thread with proper synchronization"""
        if not self.process:
            return
        
        try:
            while not self.shutdown_event.is_set() and self.process and self.process.poll() is None:
                try:
                    line = self.process.stdout.readline()
                    if line:
                        with self.output_lock:
                            self.output_queue.put(line)
                except (IOError, OSError) as e:
                    with self.output_lock:
                        self.output_queue.put(f"Error reading output: {str(e)}\n")
                    break
                
                # Check shutdown event frequently
                if self.shutdown_event.wait(0.01):  # Small delay to prevent high CPU usage
                    break
                    
        except Exception as e:
            with self.output_lock:
                self.output_queue.put(f"Error reading output: {str(e)}\n")
        finally:
            # Process has ended
            with self.state_lock:
                if self.is_running:
                    with self.output_lock:
                        self.output_queue.put("=== Bot process has ended ===\n")
                    # Reset state in main thread
                    self.root.after(100, self.on_process_ended)
    
    def on_process_ended(self):
        """Handle when the process has ended unexpectedly with proper synchronization"""
        with self.state_lock:
            self.is_running = False
            self.shutdown_event.set()
            if self.process:
                self.process = None
        
        # Update UI outside the lock
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="● Stopped", text_color="#ff4444")
            
    def update_output(self):
        """Update the output display from the queue with proper synchronization"""
        try:
            lines_to_process = []
            with self.output_lock:
                # Get all available lines at once to minimize lock time
                while True:
                    try:
                        line = self.output_queue.get_nowait()
                        lines_to_process.append(line)
                    except queue.Empty:
                        break
            
            # Process lines outside the lock
            for line in lines_to_process:
                self.append_output(line)
                
        except Exception as e:
            self.append_output(f"Error updating output: {str(e)}\n")
        
        # Schedule the next update
        self.root.after(100, self.update_output)
    
    def append_output(self, text):
        """Append text to the output display"""
        try:
            self.output_text.insert("end", text)
            
            # Auto-scroll if enabled
            if self.auto_scroll_var.get():
                self.output_text.see("end")
                
        except Exception as e:
            print(f"Error appending output: {e}")
    
    def clear_output(self):
        """Clear the output display"""
        self.output_text.delete("1.0", "end")
    
    def on_closing(self):
        """Handle window closing with proper synchronization"""
        with self.state_lock:
            is_running = self.is_running

        if is_running:
            if messagebox.askokcancel("Quit", "Bot is still running. Stop and quit?"):
                self.stop_bot(force_kill=True)
                # The stop_bot function will handle process termination.
                # We can proceed to destroy the window.
                self.root.destroy()
        else:
            self.root.destroy()

def terminate_process_tree(pid=None):
    """Terminate a process and all its children safely using psutil"""
    try:
        if pid is None:
            pid = os.getpid()
            
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # Terminate children first
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
                
        # Wait for children to terminate
        psutil.wait_procs(children, timeout=3)
        
        # Kill any stragglers
        for child in children:
            try:
                if child.is_running():
                    child.kill()
            except psutil.NoSuchProcess:
                pass
                
        # Finally terminate parent (self if pid is None)
        try:
            if pid != os.getpid(): # Don't kill self yet if we are the parent
                 parent.terminate()
        except psutil.NoSuchProcess:
            pass
            
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        print(f"Error terminating process tree: {e}")

def main():
    """Main function"""
    try:
        # Set up a way to detect if we're running as a frozen executable
        is_frozen = getattr(sys, 'frozen', False)
        
        # If we're on Windows and not frozen, create a hidden console
        if sys.platform == "win32" and not is_frozen:
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            
            # Hide the console window
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
        
        root = ctk.CTk()
        app = PatchRaptorGUI(root)
        
        # Handle Ctrl+C in console
        def handle_sigint(signum, frame):
            print("\nShutting down...")
            try:
                # Try to clean up properly first
                if hasattr(app, 'on_closing'):
                    app.on_closing()
                else:
                    root.quit()
                    root.destroy()
            except:
                pass
            finally:
                # Ensure we exit
                terminate_process_tree()
                os._exit(0)
        
        if sys.platform != "win32":  # SIGINT not available on Windows
            signal.signal(signal.SIGINT, handle_sigint)
        
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted")
    except Exception as e:
        print(f"Application error: {e}")
        if 'root' in locals() and root:
            try:
                messagebox.showerror("Error", f"Application error:\n{str(e)}")
            except:
                pass
    finally:
        # Ensure we exit cleanly
        try:
            if 'root' in locals() and root:
                root.quit()
                root.destroy()
        except:
            pass
            
        # Make sure all processes are terminated
        terminate_process_tree()
        os._exit(0)

if __name__ == "__main__":
    main()
