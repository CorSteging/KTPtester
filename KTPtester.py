import subprocess
import sys
import tempfile
import shutil
import os
import webbrowser
from pathlib import Path
from typing import Optional, List
import threading
import tkinter as tk
from tkinter import scrolledtext, PhotoImage, BooleanVar

ICON_FILE = "ktp_icon.png"
PROJECTS_DIR = Path("projects")

streamlit_process: Optional[subprocess.Popen] = None


# -------------------------------------------------
# Logger
# -------------------------------------------------
def setup_log_tags(log_widget: scrolledtext.ScrolledText) -> None:
    log_widget.configure(background="white", foreground="black", font=("Courier", 11))
    log_widget.tag_config("system", foreground="darkblue")
    log_widget.tag_config("warning", foreground="darkorange")
    log_widget.tag_config("error", foreground="red")
    log_widget.tag_config("student", foreground="black")


def log_message(log_widget: scrolledtext.ScrolledText, msg: str, tag: str = "system") -> None:
    for line in msg.rstrip().split("\n"):
        log_widget.insert(tk.END, line + "\n", tag)
    log_widget.see(tk.END)
    log_widget.update_idletasks()
    print(msg)


def run_subprocess_live(
    cmd: List[str],
    log_widget: scrolledtext.ScrolledText,
    cwd: Optional[Path] = None,
    tag: str = "student",
    env: Optional[dict] = None
) -> int:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        text=True,
        bufsize=1,
        env=env
    )

    if process.stdout:
        for line in process.stdout:
            log_widget.insert(tk.END, line, tag)
            log_widget.see(tk.END)
            log_widget.update_idletasks()

    process.wait()
    return process.returncode


# -------------------------------------------------
# Repo helpers
# -------------------------------------------------
def parse_repo_input(input_url: str) -> tuple[str, Optional[str]]:
    if "/commit/" in input_url:
        base, commit = input_url.split("/commit/")
        return base + ".git", commit
    return input_url, None


def extract_repo_info(repo_url: str) -> tuple[str, str]:
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1].replace(".git", "")


def clone_repo(repo_url: str, target_path: Path, log_widget: scrolledtext.ScrolledText) -> bool:
    log_message(log_widget, f"🔄 Cloning {repo_url}")
    return run_subprocess_live(
        ["git", "clone", repo_url, str(target_path)],
        log_widget,
        tag="system"
    ) == 0


def checkout_commit(target_path: Path, commit_hash: str, log_widget: scrolledtext.ScrolledText) -> bool:
    log_message(log_widget, f"🔄 Checking out commit {commit_hash}")
    return run_subprocess_live(
        ["git", "-C", str(target_path), "checkout", commit_hash],
        log_widget,
        tag="system"
    ) == 0


# -------------------------------------------------
# Project inspection
# -------------------------------------------------
def find_file(repo_path: Path, filename: str) -> Optional[Path]:
    for path in repo_path.rglob(filename):
        return path
    return None


def is_streamlit_project(repo_path: Path) -> bool:
    requirements = find_file(repo_path, "requirements.txt")
    if not requirements:
        return False
    return "streamlit" in requirements.read_text(errors="ignore").lower()


def create_venv(repo_path: Path) -> Path:
    venv_dir = repo_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    python_path = (
        venv_dir / "Scripts" / "python.exe"
        if sys.platform.startswith("win")
        else venv_dir / "bin" / "python"
    )
    return python_path.resolve()


def install_requirements(
    python_executable: Path,
    repo_path: Path,
    log_widget: scrolledtext.ScrolledText
) -> None:
    requirements_file = find_file(repo_path, "requirements.txt")
    if not requirements_file:
        log_message(log_widget, "⚠️ No requirements.txt found", "warning")
        return

    log_message(log_widget, f"📦 Installing dependencies from {requirements_file.relative_to(repo_path)}")
    run_subprocess_live(
        [str(python_executable), "-m", "pip", "install", "-r", str(requirements_file)],
        log_widget
    )


# -------------------------------------------------
# Streamlit
# -------------------------------------------------
def run_streamlit_app(
    python_executable: Path,
    app_file: Path,
    log_widget: scrolledtext.ScrolledText
) -> None:
    global streamlit_process

    log_message(log_widget, f"🌐 Running Streamlit app ({app_file.relative_to(app_file.parents[1])})")

    env = dict(os.environ)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "false"

    streamlit_process = subprocess.Popen(
        [str(python_executable), "-m", "streamlit", "run", str(app_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=app_file.parent,
        env=env
    )

    if streamlit_process.stdout:
        for line in streamlit_process.stdout:
            log_widget.insert(tk.END, line, "student")
            log_widget.see(tk.END)
            log_widget.update_idletasks()

            if "Local URL:" in line:
                url = line.split("Local URL:")[-1].strip()
                webbrowser.open(url)


def run_main(
    python_executable: Path,
    repo_path: Path,
    log_widget: scrolledtext.ScrolledText
) -> None:
    if is_streamlit_project(repo_path):
        app_file = (
            find_file(repo_path, "main.py")
            or find_file(repo_path, "app.py")
            or find_file(repo_path, "streamlit_app.py")
        )
        if not app_file:
            log_message(log_widget, "⚠️ Streamlit detected but no app file found", "warning")
            return

        run_streamlit_app(python_executable, app_file, log_widget)
        return

    main_file = find_file(repo_path, "main.py")
    if not main_file:
        log_message(log_widget, "⚠️ No main.py found", "warning")
        return

    log_message(log_widget, f"▶️ Running {main_file.relative_to(repo_path)}")
    run_subprocess_live(
        [str(python_executable), str(main_file)],
        log_widget,
        cwd=main_file.parent
    )


# -------------------------------------------------
# Execution
# -------------------------------------------------
def run_repo(input_url: str, log_widget: scrolledtext.ScrolledText, store_locally: bool) -> None:
    repo_url, commit_hash = parse_repo_input(input_url)
    username, repo_name = extract_repo_info(repo_url)

    if store_locally:
        target_path = PROJECTS_DIR / username / repo_name
        if target_path.exists():
            shutil.rmtree(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        tmpdir = tempfile.TemporaryDirectory()
        target_path = Path(tmpdir.name) / repo_name

    target_path = target_path.resolve()

    if not clone_repo(repo_url, target_path, log_widget):
        return

    if commit_hash and not checkout_commit(target_path, commit_hash, log_widget):
        return

    python_executable = create_venv(target_path)

    run_subprocess_live(
        [str(python_executable), "-m", "pip", "install", "--upgrade", "pip"],
        log_widget,
        tag="system"
    )

    install_requirements(python_executable, target_path, log_widget)
    run_main(python_executable, target_path, log_widget)


def start_run_thread(url: str, log_widget: scrolledtext.ScrolledText, store_var: BooleanVar) -> None:
    if not url.strip():
        return

    threading.Thread(
        target=run_repo,
        args=(url.strip(), log_widget, store_var.get()),
        daemon=True
    ).start()


# -------------------------------------------------
# GUI
# -------------------------------------------------
def center_window(root: tk.Tk, width: int, height: int) -> None:
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")


def main() -> None:
    root = tk.Tk()
    root.title("KTP Project Tester")
    center_window(root, 650, 700)

    try:
        icon = PhotoImage(file=ICON_FILE)
        root.iconphoto(True, icon)
    except Exception:
        pass

    tk.Label(root, text="Enter student GitHub repo URL:", font=("Arial", 17)).pack(pady=(10, 0))

    entry = tk.Entry(root, width=50, font=("Arial", 14))
    entry.pack(pady=5)
    entry.focus()

    store_var = BooleanVar(value=False)
    tk.Checkbutton(
        root,
        text="Store project locally (projects/<user>/<repo>)",
        variable=store_var,
        font=("Arial", 12)
    ).pack(pady=3)

    run_button = tk.Button(
        root,
        text="Run",
        font=("Arial", 12),
        command=lambda: start_run_thread(entry.get(), log_widget, store_var)
    )
    run_button.pack(pady=6)

    tk.Label(root, text="Logs:", font=("Arial", 14, "bold")).pack(pady=(8, 0))

    log_widget = scrolledtext.ScrolledText(root, width=70, height=30)
    log_widget.pack(pady=5)
    setup_log_tags(log_widget)

    tk.Label(root, text="Made by Cor Steging", font=("Arial", 8), fg="gray").pack(side="bottom", pady=5)

    def on_close() -> None:
        global streamlit_process
        if streamlit_process and streamlit_process.poll() is None:
            streamlit_process.terminate()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.bind("<Return>", lambda _: start_run_thread(entry.get(), log_widget, store_var))

    root.mainloop()


if __name__ == "__main__":
    main()
