# Run everything concurrently (Databases in Docker, Backend/Worker/UI locally):
# python run_local.py

# Run everything in full Docker containers:
# docker-compose up --build





# Back end (Using uv)

# 1) cd eng-memory-os/backend
# uv run python -m eng_memory_os.cmd.worker

# 2) uv run uvicorn eng_memory_os.cmd.api_server:app --reload --port 8000

# Back end (Using standard pip & requirements.txt)

# 1) pip install -r requirements.txt
# 2) cd eng-memory-os/backend
# 3) python -m eng_memory_os.cmd.worker
# 4) uvicorn eng_memory_os.cmd.api_server:app --reload --port 8000

 # Front end
# 5) cd eng-memory-os/frontend
# >> npm install
# >> npm run dev

