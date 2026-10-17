#!/usr/bin/env bash
# Safe deploy: copies ONLY the app, manifest and icons into dist/, shows what will be published, asks, then deploys.
# Usage: ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

rm -rf dist
mkdir dist
cp relationship-crm.html dist/relationship-crm.html
cp relationship-crm.html dist/index.html
cp manifest.webmanifest icon-192.png icon-512.png apple-touch-icon.png dist/

echo "Files that will be published (dist/):"
find dist -type f | sort
echo

read -r -p "Deploy these files? (y/n) " answer
if [ "$answer" = "y" ]; then
  firebase deploy --only hosting --project personal-crm-31132
else
  echo "Cancelled. Nothing was deployed."
fi
