#!/bin/bash
# Run process in background, survives terminal disconnect

nohup uv run python process_model_nz_tiled_batch.py > process.log 2>&1 &

echo "Process started in background. PID: $!"
echo "Monitor with: tail -f process.log"
echo "Check status: ps aux | grep process_model_nz_tiled"
