#!/bin/bash
# usage: to_mp3.sh <wav dir> <dest dir> <prefix>...   (loudness-matched, mono, 96 kbps CBR)
src=$1; dst=$2; shift 2
for p in "$@"; do for w in "$src"/"$p"-[1-4].wav; do
  ffmpeg -loglevel error -y -i "$w" -af "loudnorm=I=-18:TP=-1.5:LRA=11" -ar 24000 -ac 1 -c:a libmp3lame -b:a 96k "$dst/$(basename "${w%.wav}").mp3"
done; done
