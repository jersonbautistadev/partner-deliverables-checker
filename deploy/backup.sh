#!/bin/sh
# Run from the repository on the Compose host, with its private environment configured.
set -eu
trap 'docker compose start app worker' EXIT INT TERM
docker compose stop app worker
docker compose --profile operations run --rm backup backup_bundle --directory /backups --traffic-paused --retention-days 30
docker compose --profile operations run --rm backup maintain_data
