#!/bin/bash
docker run -it \
  --name metagpt-dev \
  -v /home/alfred/MetaGPT/workspace:/app/metagpt/workspace \
  -v /home/alfred/MetaGPT/logs:/app/metagpt/logs \
  -v /home/alfred/MetaGPT/config:/app/metagpt/config \
  -v /home/alfred/MetaGPT:/app/metagpt \
  metagpt:local
