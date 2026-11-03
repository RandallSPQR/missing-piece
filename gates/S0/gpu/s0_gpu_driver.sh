#!/bin/bash
# Missing Piece S0-GPU, run ON THE POD (started by gates/S0/gpu/launch.py), one model per pod (MP_MODEL).
# Adapted from StPT's gates/S0/gpu/box_identity.sh (same stack, same upload pattern). Steps:
#   1 stack: vLLM 0.19.1 serving venv (lineup pins); pipeline v1.3.0 + Missing Piece at MP_COMMIT in a second venv
#   2 weights at the pinned revision; calibrate.preflight_weights --hash must reproduce the lineup weight_hash
#   3 start 0, mode strict:                 part1 (tokens, options, stop ids, repeats, fallback, link-check prompts), C3 strict
#   4 start 1, mode throughput (dev mode):  C1, C2, C3
#   5 start 2, mode throughput_invariant:   C1, C2, C3 (if the server starts; a failure to start is a result)
#   6 summary; weights deleted; results uploaded after every step
# Environment: HF_TOKEN (RunPod secret), MP_RESULTS_REPO, MP_RUN_ID, PIPE_COMMIT, MP_COMMIT, MP_MODEL.
set -uo pipefail
M=$MP_MODEL; OUT=/root/out/$MP_RUN_ID/$M; mkdir -p "$OUT/logs"
export HF_HOME=/root/hf HF_HUB_DISABLE_TELEMETRY=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TOKENIZERS_PARALLELISM=false
exec > >(tee -a "$OUT/logs/driver.log") 2>&1
step() { echo "=== $(date -u +%FT%TZ) $*"; }
PY=/root/venv/bin/python; VPY=/root/venv_vllm_lineup/bin/python

upload() {
  $PY - "$OUT" <<'PYX' || echo "upload failed (results stay on the pod until the deadline)"
import os, sys, json
from huggingface_hub import HfApi
api, repo, out = HfApi(), os.environ["MP_RESULTS_REPO"], sys.argv[1]
dest = f"missing-piece/S0/{os.environ['MP_RUN_ID']}/{os.environ['MP_MODEL']}"
state = "/root/upload_state.json"
st = json.load(open(state)) if os.path.exists(state) else {}
kw = dict(repo_id=repo, repo_type="dataset", folder_path=out, path_in_repo=dest, commit_message=f"MP S0-GPU {os.environ['MP_MODEL']} {os.environ['MP_RUN_ID']}")
try:
    if st.get("revision"):
        api.upload_folder(revision=st["revision"], **kw)
    else:
        api.upload_folder(**kw)
    print("uploaded", st.get("revision", "main"))
except Exception as e:
    if st.get("revision"):
        raise
    print("direct commit refused:", type(e).__name__, str(e)[:200], "-> pull request")
    r = api.upload_folder(create_pr=True, **kw)
    st["revision"] = r.pr_revision if hasattr(r, "pr_revision") else str(r).split("/tree/")[-1]
    json.dump(st, open(state, "w")); print("uploaded to", st["revision"])
PYX
}

serve() {   # serve MODE START_INDEX DEVMODE -> sets VPID, UP
  local MODE=$1 J=$2 DEV=$3
  CMD=$(LINEUP_VLLM_PYTHON=$VPY /root/venv/bin/lineup-serve-cmd "$M" --mode "$MODE")
  [ "$DEV" = 1 ] && CMD="VLLM_SERVER_DEV_MODE=1 $CMD"
  echo "$CMD" > "$OUT/serve_cmd_${MODE}.txt"
  bash -c "$CMD" > "$OUT/logs/vllm_${MODE}.log" 2>&1 & VPID=$!
  UP=0; for _ in $(seq 1 360); do curl -s localhost:8000/v1/models >/dev/null 2>&1 && { UP=1; break; }; kill -0 $VPID 2>/dev/null || break; sleep 5; done
  echo "{\"mode\": \"$MODE\", \"start_index\": $J, \"up\": $UP, \"at\": \"$(date -u +%FT%TZ)\"}" > "$OUT/server_${MODE}.json"
  [ $UP = 1 ] || { echo "server $MODE did not come up"; tail -60 "$OUT/logs/vllm_${MODE}.log"; }
}
unserve() { kill $VPID 2>/dev/null; sleep 5; pkill -9 -f "[v]llm.entrypoints" 2>/dev/null
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do kill -9 "$p" 2>/dev/null; done; sleep 5; }

step "stack"
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
uv() { python3 -m uv "$@"; }
uv venv -q -p 3.11 /root/venv_vllm_lineup && uv pip install -q -p $VPY "vllm==0.19.1" "torch==2.10.0" "transformers==5.5.3" \
  "tokenizers==0.22.2" "huggingface-hub==1.10.2" > "$OUT/logs/pip_vllm.log" 2>&1
git clone -q https://github.com/RandallSPQR/missing-piece /root/mp && git -C /root/mp checkout -q "$MP_COMMIT"
uv venv -q -p 3.11 /root/venv && uv pip install -q -p $PY "transformers==5.17.0" jinja2 huggingface_hub \
  "sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT" -e /root/mp > "$OUT/logs/pip_mp.log" 2>&1
$VPY -c "import sys, vllm, torch, transformers; print(sys.version.split()[0], 'vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.version.cuda, 'transformers', transformers.__version__, torch.cuda.get_device_name(0))" | tee "$OUT/stack.txt"
$VPY -m pip freeze > "$OUT/pip_freeze_vllm.txt" 2>/dev/null || uv pip freeze -p $VPY > "$OUT/pip_freeze_vllm.txt"
$PY -c "import sae_ethos_pipeline as s; print('pipeline', s.__version__)" | tee -a "$OUT/stack.txt"
echo "mp $(git -C /root/mp rev-parse HEAD)" | tee -a "$OUT/stack.txt"
[ -s "$OUT/stack.txt" ] || { echo "STOP: stack did not install"; upload; exit 3; }
upload

step "$M: weights"; df -h / | tail -1
export MODEL_PROFILE_FILE=$($PY -c "import sae_ethos_pipeline, lineup; print(lineup.profile_path('$M'))")
read HFID REV WANT < <($PY -c "import sae_ethos_pipeline, lineup; e=lineup.models()['$M']; print(e['hf_id'], e['revision'], e['weight_hash'])")
$PY -c "from huggingface_hub import snapshot_download as s; s('$HFID', revision='$REV', allow_patterns=['*.json','*.safetensors','tokenizer*','*.jinja','*.model','merges.txt','vocab.json'])" \
  > "$OUT/logs/download.log" 2>&1
ROOTDIR=$($PY -c 'import sae_ethos_pipeline as s; print(s.ROOT)')
(cd "$ROOTDIR" && $PY -m calibrate.preflight_weights --repo "$HFID" --revision "$REV" --allow '*.json' '*.safetensors' 'tokenizer*' \
   --hash --out "$OUT/preflight.json") > "$OUT/logs/preflight.log" 2>&1
GOT=$($PY -c "import json; print(json.load(open('$OUT/preflight.json'))['repos'][0]['weight_hash'])" 2>/dev/null)
echo "{\"weight_hash_got\": \"$GOT\", \"weight_hash_want\": \"$WANT\", \"ok\": $([ "$GOT" = "$WANT" ] && echo true || echo false)}" | tee "$OUT/weight_hash.json"
[ "$GOT" = "$WANT" ] || { echo "STOP: weight hash mismatch"; upload; exit 4; }
upload

G="$PY /root/mp/gates/S0/gpu/s0_gpu.py"
step "$M: start 0 strict"; serve strict 0 0
if [ $UP = 1 ]; then
  $G part1 "$M" "$OUT/part1_$M.json" --start 0 > "$OUT/logs/part1.log" 2>&1; tail -3 "$OUT/logs/part1.log"
  $G c3 "$M" "$OUT/c3_strict_$M.json" strict --start 0 > "$OUT/logs/c3_strict.log" 2>&1; tail -3 "$OUT/logs/c3_strict.log"
fi
unserve; upload
J=1
for MODE in throughput throughput_invariant; do
  step "$M: start $J $MODE"; serve $MODE $J 1
  if [ $UP = 1 ]; then
    $G c12 "$M" "$OUT/c12_${MODE}_$M.json" $MODE --start $J > "$OUT/logs/c12_$MODE.log" 2>&1; tail -2 "$OUT/logs/c12_$MODE.log"
    $G c3 "$M" "$OUT/c3_${MODE}_$M.json" $MODE --start $J > "$OUT/logs/c3_$MODE.log" 2>&1; tail -2 "$OUT/logs/c3_$MODE.log"
  fi
  unserve; upload; J=$((J+1))
done
step "$M: summary"; $G summary "$M" "$OUT" > "$OUT/logs/summary.log" 2>&1; tail -2 "$OUT/logs/summary.log"
rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"
step "done"; touch "$OUT/DONE"; upload
echo "pod key present: $([ -n "${RUNPOD_API_KEY:-}" ] && echo yes || echo no)" >> "$OUT/logs/selfstop.log"
curl -s -w ' http %{http_code}\n' -X DELETE -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID" >> "$OUT/logs/selfstop.log" 2>&1
upload
runpodctl remove pod "$RUNPOD_POD_ID" >> /root/selfstop_fallback.log 2>&1 || runpodctl stop pod "$RUNPOD_POD_ID" >> /root/selfstop_fallback.log 2>&1
