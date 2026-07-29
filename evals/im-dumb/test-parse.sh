#!/usr/bin/env bash
# Teste les deux extracteurs de run-eval.sh sur une capture réelle, sans LLM.
set -euo pipefail
cd "$(dirname "$0")"
source ./run-eval.sh --lib-only

skills=$(extract_skills fixtures/sample-run.jsonl)
[ "$skills" = "reality-check:im-dumb" ] || { echo "FAIL extract_skills: '$skills'"; exit 1; }

text=$(extract_final_text fixtures/sample-run.jsonl)
[ "$text" = "DONE" ] || { echo "FAIL extract_final_text: '$text'"; exit 1; }

echo "PASS (2/2)"
