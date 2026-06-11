#!/bin/bash

echo "--- Starting MasteryAI Curriculum Ingestion ---"
date

# We use -v to force the container to see the host's docs folder!
docker compose --profile fullstack run -T --rm -v /var/www/html/mastery_ai/docs:/app/docs --no-deps backend python -m backend.scripts.reset_and_reseed_curriculum --seed-reset --qdrant-batch-size 24 --qdrant-timeout-seconds 240

echo "--- Ingestion Finished Successfully ---"
date
