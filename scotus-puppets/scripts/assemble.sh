#!/bin/bash
# assemble.sh ASSETS TLDIR OUTDIR NCHUNKS PAR [START_F END_F]
# env: AUDIO (argument mp3), META (meta.json), PRESET/CRF (x264), CLIP + AFADE (excerpt mode)
set -euo pipefail
ASSETS=$1; TL=$2; OUT=$3; N=$4; PAR=$5
SD=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-$SD/../bvenv/bin/python}
AUDIO=${AUDIO:-$SD/../work/audio.mp3}
mkdir -p $OUT/chunks
NF=$($PY -c "import json;print(json.load(open('$TL/timeline.json'))['nframes'])")
START=${6:-0}; END=${7:-$((NF + 192))}
TOTAL=$((END - START))
STEP=$(( (TOTAL + N - 1) / N ))
: > $OUT/chunks/list.txt
jobs=()
for i in $(seq 0 $((N - 1))); do
  a=$((START + i * STEP)); b=$((a + STEP)); [ $b -gt $END ] && b=$END
  [ $a -ge $b ] && continue
  f=$(printf "$OUT/chunks/c%03d.mp4" $i)
  echo "file '$f'" >> $OUT/chunks/list.txt
  [ -s "$f" ] || jobs+=("$a $b $f")
done
printf '%s\n' "${jobs[@]}" | xargs -P $PAR -L 1 bash -c "$PY $SD/compose.py $ASSETS $TL \$2.tmp.mp4 \$0 \$1 > \$2.log 2>&1 && mv \$2.tmp.mp4 \$2"
ffmpeg -v error -y -f concat -safe 0 -i $OUT/chunks/list.txt -c copy $OUT/video_only.mp4
SS=$($PY -c "print($START/24)"); DUR=$($PY -c "print($TOTAL/24)")
ffmpeg -v error -y -i $OUT/video_only.mp4 -ss $SS -i $AUDIO \
  -filter_complex "[1:a]apad,atrim=0:$DUR,aresample=44100${AFADE:-}[a]" -map 0:v -map "[a]" \
  -c:v copy -c:a aac -b:a 96k -ac 1 -movflags +faststart -shortest $OUT/final.mp4
ls -la $OUT/final.mp4
