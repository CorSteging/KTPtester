import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List
import threading
import tkinter as tk
from tkinter import scrolledtext, PhotoImage, BooleanVar

ICON_FILE = "ktp_icon.png"
PROJECTS_DIR = Path("projects")


# --- Logger Helpers ---
def setup_log_tags(log_widget: scrolledtext.ScrolledText) -> None:
    """Configure colored tags for different log levels, keeping white background."""
    log_widget.configure(background="white", foreground="black", font=("Courier", 12))
    log_widget.tag_config("system", foreground="darkblue")
    log_widget.tag_config("warning", foreground="darkorange")
    log_widget.tag_config("error", foreground="red")
    log_widget.tag_config("student", foreground="black")


def log_message(log_widget: scrolledtext.ScrolledText, msg: str, tag: str = "system") -> None:
    """Append a colored log message with a given tag, stripped and clean."""
    for line in msg.rstrip().split("\n"):
        log_widget.insert(tk.END, line + "\n", tag)
    log_widget.see(tk.END)
    log_widget.update_idletasks()
    print(msg)


def run_subprocess_live(cmd: List[str], log_widget: scrolledtext.ScrolledText,
                        cwd: Optional[Path] = None, tag: str = "student") -> int:
    """Run a subprocess and stream output live into the log widget with readable colors."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        text=True,
        bufsize=1
    )

    if process.stdout:
        for line in process.stdout:
            line = line.rstrip()
            log_widget.insert(tk.END, line + "\n", tag)
            log_widget.see(tk.END)
            log_widget.update_idletasks()

    process.wait()
    return process.returncode


# --- Repo Management ---
def clone_repo(repo_url: str, target_path: Path, log_widget: scrolledtext.ScrolledText) -> bool:
    log_message(log_widget, f"🔄 Cloning {repo_url}", "system")
    try:
        run_subprocess_live(["git", "clone", repo_url, str(target_path)], log_widget, tag="system")
        return True
    except Exception as e:
        log_message(log_widget, f"❌ Git clone failed: {e}", "error")
        return False


def checkout_commit(target_path: Path, commit_hash: str, log_widget: scrolledtext.ScrolledText) -> bool:
    log_message(log_widget, f"🔄 Checking out commit {commit_hash}", "system")
    try:
        run_subprocess_live(["git", "-C", str(target_path), "checkout", commit_hash], log_widget, tag="system")
        return True
    except Exception as e:
        log_message(log_widget, f"❌ Git checkout failed: {e}", "error")
        return False


def create_venv(target_path: Path) -> Path:
    """Create a virtual environment and return the Python executable path."""
    venv_dir = target_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    return venv_dir / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")


def install_requirements(python_executable: Path, requirements_file: Path,
                         log_widget: scrolledtext.ScrolledText) -> None:
    if requirements_file.exists():
        log_message(log_widget, "✅ requirements.txt found:", "system")
        log_message(log_widget, "🔄 Installing dependencies:", "system")
        run_subprocess_live([str(python_executable), "-m", "pip", "install", "-r", str(requirements_file)], log_widget)
    else:
        log_message(log_widget, "⚠️ No requirements.txt found", "warning")


def run_main(python_executable: Path, main_file: Path, log_widget: scrolledtext.ScrolledText) -> None:
    if main_file.exists():
        log_message(log_widget, "✅ main.py found:", "system")
        log_message(log_widget, f"🔄 Running {main_file}:", "system")
        run_subprocess_live([str(python_executable), str(main_file)], log_widget)
    else:
        log_message(log_widget, "⚠️ No main.py found", "warning")


# --- Input Handling ---
def parse_repo_input(input_url: str) -> tuple[str, Optional[str]]:
    if "/commit/" in input_url:
        parts = input_url.split("/commit/")
        return parts[0] + ".git", parts[1]
    return input_url, None


def extract_repo_info(repo_url: str) -> tuple[str, str]:
    """
    Extract username and repo name from GitHub URL.
    Example: https://github.com/user/repo.git -> ("user", "repo")
    """
    parts = repo_url.rstrip("/").split("/")
    username = parts[-2]
    repo_name = parts[-1].replace(".git", "")
    return username, repo_name


def run_repo(input_url: str, log_widget: scrolledtext.ScrolledText, store_locally: bool) -> None:
    repo_url, commit_hash = parse_repo_input(input_url)
    username, repo_name = extract_repo_info(repo_url)

    if store_locally:
        target_path = PROJECTS_DIR / username / repo_name
        if target_path.exists():
            shutil.rmtree(target_path)  # override old version
        target_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        tmpdir = tempfile.TemporaryDirectory()
        target_path = Path(tmpdir.name) / repo_name

    if not clone_repo(repo_url, target_path, log_widget):
        return
    if commit_hash and not checkout_commit(target_path, commit_hash, log_widget):
        return

    python_executable = create_venv(target_path)
    run_subprocess_live([str(python_executable), "-m", "pip", "install", "--upgrade", "pip"], log_widget,
                        tag="system")
    install_requirements(python_executable, target_path / "requirements.txt", log_widget)
    run_main(python_executable, target_path / "main.py", log_widget)

    log_message(log_widget, "✅ Finished testing", "system")


def start_run_thread(url: str, log_widget: scrolledtext.ScrolledText, store_var: BooleanVar) -> None:
    if not url.strip():
        return
    threading.Thread(
        target=run_repo,
        args=(url.strip(), log_widget, store_var.get()),
        daemon=True
    ).start()


# --- GUI Helpers ---
def center_window(root: tk.Tk, width: int, height: int) -> None:
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")


def main() -> None:
    root = tk.Tk()
    root.title("KTP Project Tester")
    window_width, window_height = 600, 650
    center_window(root, window_width, window_height)

    # Set icon if available
    try:
        icon_img = PhotoImage(file=ICON_FILE)
        root.iconphoto(True, icon_img)
    except Exception:
        pass

    # Top label and entry
    tk.Label(root, text="Enter student GitHub repo URL:", font=("Arial", 17)).pack(pady=(10, 0))
    entry = tk.Entry(root, width=50, font=("Arial", 14))
    entry.pack(pady=5)
    entry.focus()

    # Store locally checkbox
    store_var = BooleanVar(value=False)
    tk.Checkbutton(root, text="Store project locally", variable=store_var, font=("Arial", 12)).pack(pady=2)

    # Run button
    run_button = tk.Button(root, text="Run", command=lambda: start_run_thread(entry.get(), log_widget, store_var))
    run_button.pack(pady=5)

    # Log title
    tk.Label(root, text="Logs:", font=("Arial", 14, "bold")).pack(pady=(5, 0))

    # Scrollable log
    log_widget = scrolledtext.ScrolledText(root, width=65, height=30, font=("Courier", 10))
    log_widget.pack(pady=5)
    setup_log_tags(log_widget)

    # Footer
    footer = tk.Label(root, text="Made by Cor Steging", font=("Arial", 8), fg="gray")
    footer.pack(side="bottom", pady=5)

    # Enter key triggers run
    root.bind("<Return>", lambda event: start_run_thread(entry.get(), log_widget, store_var))

    root.mainloop()


if __name__ == "__main__":
    main()
