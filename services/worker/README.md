"""RoadVision worker.

Install CUDA PyTorch before ultralytics when using a GPU:

  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

Match the wheel to nvidia-smi. This machine reports an RTX 3050 Laptop GPU.

Always use the solo pool (Windows and Linux Docker). Prefork after OpenCV/PyTorch import fails jobs in production:

  celery -A app.worker:celery_app worker --loglevel=INFO --concurrency=1 --pool=solo
"""
