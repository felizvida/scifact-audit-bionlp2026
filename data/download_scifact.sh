#!/usr/bin/env bash
# Download and extract the SciFact dataset (Wadden et al. 2020).
# Source: https://github.com/allenai/scifact
#
# This places the dataset under data/scifact/ alongside this script.
# Required for revision/run_haiku_experiments.py and revision/build_packets.py.

set -euo pipefail

cd "$(dirname "$0")"

if [[ -f "scifact/claims_dev.jsonl" && -f "scifact/corpus.jsonl" ]]; then
  echo "SciFact dataset already present at $(pwd)/scifact/. Nothing to do."
  exit 0
fi

URL="https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
TARBALL="data.tar.gz"

if [[ ! -f "$TARBALL" ]]; then
  echo "Downloading SciFact tarball from $URL ..."
  curl -fsSL -o "$TARBALL" "$URL"
fi

echo "Extracting into $(pwd)/scifact/ ..."
mkdir -p scifact
tar xzf "$TARBALL" -C scifact --strip-components=1

echo "Done. Files at $(pwd)/scifact/:"
ls scifact/
