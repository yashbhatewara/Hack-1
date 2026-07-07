#!/usr/bin/env python3
import os
import sys
import subprocess
import threading
import time
import socket
import signal

# ANSI Color Codes
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Check if on Windows and enable ANSI support
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        # Fall back to no colors if console setup fails
        CYAN = GREEN = YELLOW = RED = RESET = BOLD = ""

def print_log(prefix, color, message):
    """Print prefixed log message with color."""
    sys.stdout.write(f"{color}{BOLD}[{prefix}]{RESET} {message}\n")
    sys.stdout.flush()

def read_stream(stream, prefix, color):
    """Read stream line by line and print with prefix."""
    try:
        for line in iter(stream.readline, ''):
            if not line:
                break
            print_log(prefix, color, line.rstrip())
    except Exception:
        pass

def is_port_open(host, port):
    """Check if a port is open."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, port))
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "eng-memory-os", "backend")
    frontend_dir = os.path.join(root_dir, "eng-memory-os", "frontend")

    print_log("System", CYAN, "Starting local development stack...")

    # Step 1: Boot databases via Docker Compose
    print_log("Docker", CYAN, "Starting PostgreSQL and Qdrant databases via Docker Compose...")
    try:
        subprocess.run(
            ["docker-compose", "up", "postgres", "qdrant", "-d"],
            cwd=root_dir,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print_log("Docker", RED, f"Failed to start databases via Docker Compose: {e}")
        print_log("Docker", RED, "Please ensure Docker Desktop is running.")
        sys.exit(1)
    except FileNotFoundError:
        print_log("Docker", RED, "docker-compose command not found. Please ensure Docker is installed and in your PATH.")
        sys.exit(1)

    # Step 2: Wait for databases to be healthy
    print_log("System", CYAN, "Waiting for databases to be ready...")
    for _ in range(30):
        postgres_ready = is_port_open("localhost", 5432)
        qdrant_ready = is_port_open("localhost", 6333)
        if postgres_ready and qdrant_ready:
            print_log("System", GREEN, "Databases are healthy and accepting connections.")
            break
        time.sleep(1)
    else:
        print_log("System", RED, "Timeout waiting for databases to become ready.")
        sys.exit(1)

    # Step 3: Run Alembic migrations
    print_log("Database", CYAN, "Running database migrations...")
    try:
        # Determine whether to use 'uv run alembic' or just 'alembic'
        # Check if uv is in PATH
        use_uv = False
        try:
            subprocess.run(["uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            use_uv = True
        except FileNotFoundError:
            pass

        migration_cmd = ["uv", "run", "alembic", "upgrade", "head"] if use_uv else ["alembic", "upgrade", "head"]
        
        # Add local python venv to path if not using uv
        env = os.environ.copy()
        if not use_uv:
            venv_bin = os.path.join(root_dir, ".venv", "Scripts" if sys.platform == "win32" else "bin")
            if os.path.exists(venv_bin):
                env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")

        subprocess.run(migration_cmd, cwd=backend_dir, env=env, check=True)
        print_log("Database", GREEN, "Database migrations applied successfully.")
    except subprocess.CalledProcessError as e:
        print_log("Database", RED, f"Database migration failed: {e}")
        print_log("Database", RED, "Please check database connection settings in eng-memory-os/.env")
        sys.exit(1)

    # Step 4: Start local services
    processes = []
    
    # Prep environment with PYTHONPATH
    backend_env = env.copy()
    backend_env["PYTHONPATH"] = os.path.join(backend_dir, "src")

    # Command configuration
    api_cmd = ["uv", "run", "uvicorn", "eng_memory_os.cmd.api_server:app", "--reload", "--port", "8000"] if use_uv else ["uvicorn", "eng_memory_os.cmd.api_server:app", "--reload", "--port", "8000"]
    worker_cmd = ["uv", "run", "python", "-m", "eng_memory_os.cmd.worker"] if use_uv else ["python", "-m", "eng_memory_os.cmd.worker"]
    
    # Frontend command (needs shell=True on Windows to resolve npm correctly)
    frontend_cmd = "npm run dev"
    
    try:
        # Start API Server
        print_log("System", CYAN, "Starting API Server...")
        api_proc = subprocess.Popen(
            api_cmd,
            cwd=backend_dir,
            env=backend_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append((api_proc, "API", CYAN))

        # Start Worker
        print_log("System", CYAN, "Starting Background Worker...")
        worker_proc = subprocess.Popen(
            worker_cmd,
            cwd=backend_dir,
            env=backend_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append((worker_proc, "Worker", YELLOW))

        # Start Frontend UI
        print_log("System", CYAN, "Starting Frontend Dev Server...")
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append((frontend_proc, "UI", GREEN))

    except Exception as e:
        print_log("System", RED, f"Failed to start local services: {e}")
        # Clean up already started processes
        for p, _, _ in processes:
            p.terminate()
        sys.exit(1)

    # Start reader threads for stdout and stderr
    threads = []
    for proc, prefix, color in processes:
        t_out = threading.Thread(target=read_stream, args=(proc.stdout, prefix, color), daemon=True)
        t_err = threading.Thread(target=read_stream, args=(proc.stderr, prefix, color), daemon=True)
        t_out.start()
        t_err.start()
        threads.extend([t_out, t_err])

    print_log("System", GREEN, "All services started! Press Ctrl+C to stop all services.")

    # Graceful shutdown handler
    def shutdown(signum, frame):
        print_log("System", YELLOW, "\nShutting down all local services...")
        # Terminate local processes
        for proc, name, _ in processes:
            print_log("System", CYAN, f"Terminating {name}...")
            proc.terminate()
        
        # Wait for them to finish
        for proc, _, _ in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        print_log("System", GREEN, "Local services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep main thread alive and monitor processes
    try:
        while True:
            for proc, name, color in processes:
                poll = proc.poll()
                if poll is not None:
                    print_log("System", RED, f"Process {name} exited with code {poll}")
                    # Trigger shutdown if any process fails
                    shutdown(None, None)
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
