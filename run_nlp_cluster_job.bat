@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m src.pipeline.clustering_export >> data\logs\nlp_cluster_job.log 2>&1
wsl -d Ubuntu -- bash -c "cd '/mnt/c/Users/hmnth/Desktop/Portfolio/project_AI/threads-ai-content' && source ~/threads-clustering-env/bin/activate && python3 -m src.pipeline.cluster_wsl" >> data\logs\nlp_cluster_job.log 2>&1
.venv\Scripts\python.exe -m src.pipeline.clustering_import >> data\logs\nlp_cluster_job.log 2>&1
