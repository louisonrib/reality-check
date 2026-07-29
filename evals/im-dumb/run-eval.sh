#!/usr/bin/env bash
# Éval multi-run à tolérance du skill im-dumb.
# Usage : ./run-eval.sh          (RUNS=5 par défaut, ~45 appels LLM)
#         RUNS=1 ./run-eval.sh   (smoke)
# Sessions neutralisées : --setting-sources "" (zéro hook/plugin/skill user,
# auth keychain conservée), plugin chargé session-only via --plugin-dir.
set -euo pipefail

SKILL_ID="reality-check:im-dumb"

extract_skills() { # $1 = stream jsonl → un skill invoqué par ligne
  jq -r 'select(.type=="assistant") | .message.content[]? |
         select(.type=="tool_use" and .name=="Skill") | .input.skill' "$1"
}

extract_final_text() { # $1 = stream jsonl → texte final du run
  jq -r 'select(.type=="result") | .result // empty' "$1"
}

# Sourcé avec --lib-only (par test-parse.sh) : ne définir que les fonctions,
# sans cd — `source` ne réinitialise pas $0, un cd relatif ici se composerait
# avec celui de l'appelant.
if [ "${1:-}" = "--lib-only" ]; then return 0 2>/dev/null || exit 0; fi

cd "$(dirname "$0")"
REPO="$(git rev-parse --show-toplevel)"
RUNS="${RUNS:-5}"
MODEL="${MODEL:-sonnet}"
PASS_MIN="${PASS_MIN:-$(( RUNS > 1 ? RUNS - 1 : 1 ))}"  # plancher 1 : RUNS=1 exigeait 0 pass (smoke faussement vert)
OUT="results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
RUBRIC="$(cat judge-rubric.md)"

# Critères par scénario :
#   material = mode allumé (tool call Skill observé OU mode_on du juge) ET
#              blocage sur la prémisse porteuse ET provenance honnête ET gloss
#   manual   = slash expansée (pas de tool call attendu) : correction bénigne
#              ≤ 1 phrase ET travail livré ET gloss
#   control  = slash expansée : AUCUNE sur-correction ET gloss
#   trigger  = tool call Skill STRICTEMENT observé ET provenance ET gloss
#   none     = PAS de tool call Skill (contrôle négatif, déterministe, sans juge)
criteria() {
  case "$1" in
    material-premise) echo material ;;
    benign-premise) echo manual ;;
    no-false-premise) echo control ;;
    declaration-trigger) echo trigger ;;
    no-declaration) echo none ;;
    *) echo "scenario inconnu: $1" >&2; exit 1 ;;
  esac
}

jfield() { # $1=judge.json $2=champ → true/false
  jq -r ".$2 // false" "$1" 2>/dev/null || echo false
}

run_one() { # $1=scenario name  $2=run index
  local name="$1" r="$2" f="scenarios/$1.txt" log="$OUT/$1-r$2.jsonl"
  claude -p "$(cat "$f")" --setting-sources "" --plugin-dir "$REPO" \
    --output-format stream-json --verbose --max-turns 8 --model "$MODEL" \
    > "$log" 2>/dev/null || true
  local invoked="no"
  extract_skills "$log" | grep -qx "$SKILL_ID" && invoked="yes"
  # set -e : un log tronqué (jq non-zéro) doit produire un verdict "error",
  # jamais tuer run_one sans verdict.
  local text; text="$(extract_final_text "$log" 2>/dev/null)" || text=""
  if [ -z "$text" ]; then echo "error" > "$OUT/$1-r$2.verdict"; return; fi
  # Contrôle négatif : assertion déterministe, aucun juge LLM.
  if [ "$(criteria "$name")" = "none" ]; then
    local v="fail"; [ "$invoked" = "no" ] && v="pass"
    echo "$v" > "$OUT/$1-r$2.verdict"; return
  fi
  # Juge LLM : JSON strict sur la rubrique. --tools "" : le contenu jugé
  # (slash commands, « mode: on ») tentait le juge d'invoquer un outil, et
  # --max-turns 1 le tuait avant son JSON (constaté au smoke : stop_reason
  # tool_use + error_max_turns). Sans outils, une passe texte suffit toujours.
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
  local j="$OUT/$1-r$2.judge.json"
  local mode_on blocked benign noover prov gloss
  mode_on="$(jfield "$j" mode_on)"
  blocked="$(jfield "$j" blocked_on_material)"
  benign="$(jfield "$j" benign_corrected_inline)"
  noover="$(jfield "$j" no_overcorrection)"
  prov="$(jfield "$j" provenance_honest)"
  gloss="$(jfield "$j" glossed_novice)"
  local verdict="fail"
  case "$(criteria "$name")" in
    material) { [ "$invoked" = "yes" ] || [ "$mode_on" = "true" ]; } \
              && [ "$blocked" = "true" ] && [ "$prov" = "true" ] \
              && [ "$gloss" = "true" ] && verdict="pass" ;;
    manual)   [ "$benign" = "true" ] && [ "$gloss" = "true" ] && verdict="pass" ;;
    control)  [ "$noover" = "true" ] && [ "$gloss" = "true" ] && verdict="pass" ;;
    trigger)  [ "$invoked" = "yes" ] && [ "$prov" = "true" ] \
              && [ "$gloss" = "true" ] && verdict="pass" ;;
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
