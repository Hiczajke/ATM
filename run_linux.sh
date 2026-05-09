#!/usr/bin/env bash
# Uruchomienie aplikacji ATM w katalogu projektu.
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 app.py
else
  python app.py
fi
