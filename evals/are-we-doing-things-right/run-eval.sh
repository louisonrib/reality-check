#!/usr/bin/env bash
# Éval multi-run à tolérance du skill are-we-doing-things-right.
# Usage : ./run-eval.sh          (RUNS=5 par défaut, ~50 appels LLM)
#         RUNS=1 ./run-eval.sh   (smoke)
# Sessions neutralisées : --setting-sources "" (zéro hook/plugin/skill user,
# auth keychain conservée), plugin chargé session-only via --plugin-dir.
set -euo pipefail

SKILL_ID="reality-check:are-we-doing-things-right"

extract_skills() { # $1 = stream jsonl → un skill invoqué par ligne
  jq -r 'select(.type=="assistant") | .message.content[]? |
         select(.type=="tool_use" and .name=="Skill") | .input.skill' "$1"
}

extract_final_text() { # $1 = stream jsonl → texte final du run
  jq -r 'select(.type=="result") | .result // empty' "$1"
}

# Sourcé avec --lib-only (par test-parse.sh) : ne définir que les fonctions,
# sans cd — `source` ne réinitialise pas $0, un cd relatif ici se composerait
# avec celui de l'appelant. (Amendé en cours d'exécution : le cd était avant
# cette garde et cassait le chemin sourcé ; déviation consignée au postmortem.)
if [ "${1:-}" = "--lib-only" ]; then return 0 2>/dev/null || exit 0; fi

cd "$(dirname "$0")"
REPO="$(git rev-parse --show-toplevel)"
RUNS="${RUNS:-5}"
MODEL="${MODEL:-sonnet}"
PASS_MIN="${PASS_MIN:-$(( RUNS > 1 ? RUNS - 1 : 1 ))}"  # plancher 1 : RUNS=1 exigeait 0 pass (smoke faussement vert) — sync #11
OUT="results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
RUBRIC="$(cat judge-rubric.md)"

# Critères par scénario :
#   "auto"   = pass si le juge voit le step-back COMPLET (stepback_full) ET
#              qu'il a été amorcé (tool call Skill observé, ou
#              stepback_attempted) — l'invocation seule ne suffit jamais
#   "manual" = pass si step-back jugé complet (slash expansée, pas de tool call)
#   "none"   = pass si PAS de step-back (travail normal continue)
criteria() {
  case "$1" in
    literal-loop|false-fix-cycle|non-code) echo auto ;;
    manual) echo manual ;;
    no-loop) echo none ;;
    *) echo "scenario inconnu: $1" >&2; exit 1 ;;
  esac
}

run_one() { # $1=scenario name  $2=run index
  local name="$1" r="$2" f="scenarios/$1.txt" log="$OUT/$1-r$2.jsonl"
  claude -p "$(cat "$f")" --setting-sources "" --plugin-dir "$REPO" \
    --output-format stream-json --verbose --max-turns 8 --model "$MODEL" \
    > "$log" 2>/dev/null || true
  local invoked="no"
  extract_skills "$log" | grep -qx "$SKILL_ID" && invoked="yes"
  # set -e : un log tronqué (jq non-zéro) doit produire un verdict "error",
  # jamais tuer run_one sans verdict. (Amendé post-review Task 2.)
  local text; text="$(extract_final_text "$log" 2>/dev/null)" || text=""
  if [ -z "$text" ]; then echo "error" > "$OUT/$1-r$2.verdict"; return; fi
  # Juge LLM : JSON strict sur la rubrique. --tools "" : le contenu jugé
  # (rubrique step-back, mentions d'invocation de Skill) tentait le juge
  # d'invoquer un outil lui-même, ce que --max-turns 1 tuerait avant son
  # JSON. Sans outils, une passe texte suffit toujours — sync #11.
  claude -p "$RUBRIC

## Scenario given to the assistant
$(cat "$f")

## Skill tool invocations observed
$invoked ($SKILL_ID)

## Assistant's final answer
$text" \
    --setting-sources "" --output-format json --max-turns 1 --model "$MODEL" \
    --tools "" \
    2>/dev/null | jq -r '.result // empty' \
    | sed -n '/{/,/}/p' > "$OUT/$1-r$2.judge.json" || true
  # Juge illisible = run en erreur, jamais un verdict silencieux.
  if ! jq -e . "$OUT/$1-r$2.judge.json" >/dev/null 2>&1; then
    echo "error" > "$OUT/$1-r$2.verdict"; return
  fi
  local judged; judged="$(jq -r '.stepback_full // false' "$OUT/$1-r$2.judge.json" 2>/dev/null || echo false)"
  local triggered; triggered="$(jq -r '.stepback_attempted // false' "$OUT/$1-r$2.judge.json" 2>/dev/null || echo false)"
  local verdict="fail"
  case "$(criteria "$name")" in
    auto)   { [ "$invoked" = "yes" ] || [ "$triggered" = "true" ]; } && [ "$judged" = "true" ] && verdict="pass" ;;
    manual) [ "$judged" = "true" ] && verdict="pass" ;;
    none)   [ "$invoked" = "no" ] && [ "$triggered" = "false" ] && verdict="pass" ;;
  esac
  echo "$verdict" > "$OUT/$1-r$2.verdict"
}

overall=0
{
  echo "# Eval report — $SKILL_ID"
  echo "RUNS=$RUNS PASS_MIN=$PASS_MIN MODEL=$MODEL ($(date))"
  echo
} > "$OUT/report.md"

for f in scenarios/*.txt; do
  name="$(basename "$f" .txt)"
  # runs d'un même scénario en parallèle ; scénarios séquentiels — simple et suffisant.
  for r in $(seq 1 "$RUNS"); do run_one "$name" "$r" & done
  wait
  pass=$(cat "$OUT/$name"-r*.verdict 2>/dev/null | grep -cx pass || true)
  status=FAIL; [ "$pass" -ge "$PASS_MIN" ] && status=PASS
  [ "$status" = "FAIL" ] && overall=1
  echo "- **$name**: $status ($pass/$RUNS, min $PASS_MIN)" >> "$OUT/report.md"
  echo "$name: $status ($pass/$RUNS)"
done

echo; echo "Report: $PWD/$OUT/report.md"
exit "$overall"
