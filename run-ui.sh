#!/bin/bash
docker run -d \
  --name metagpt-ui \
  -p 8000:8000 \
  -v /home/alfred/UI-meta:/app/UI-meta \
  -v ui-meta-venv:/app/UI-meta/venv \
  metagpt:local