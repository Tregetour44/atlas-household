#!/bin/bash
# to_mp3.sh SRC_DIR VOICE OUT_DIR [ids...]: loudness-match each <VOICE>-<id>.wav to -18 LUFS, mono 96 kbps MP3,
# plus <VOICE>-all.mp3 joining L01..L10 with 0.5 s of silence between lines.
set -e
src=$1; v=$2; out=$3; shift 3
ids=${@:-L01 L02 L03 L04 L05 L06 L07 L08 L09 L10}
tmp=$(mktemp -d); list=$tmp/list.txt
ffmpeg -loglevel error -f lavfi -i anullsrc=r=24000:cl=mono -t 0.5 -ar 24000 -ac 1 $tmp/gap.wav
for id in $ids; do
  ffmpeg -loglevel error -y -i $src/$v-$id.wav -af loudnorm=I=-18:TP=-1.5:LRA=11,aresample=24000 -ac 1 -ar 24000 $tmp/$id.wav
  ffmpeg -loglevel error -y -i $tmp/$id.wav -codec:a libmp3lame -b:a 96k $out/$v-$id.mp3
  [ -s $list ] && echo "file '$tmp/gap.wav'" >> $list
  echo "file '$tmp/$id.wav'" >> $list
done
if [ "$ids" = "L01 L02 L03 L04 L05 L06 L07 L08 L09 L10" ]; then
  ffmpeg -loglevel error -y -f concat -safe 0 -i $list -codec:a libmp3lame -b:a 96k $out/$v-all.mp3
fi
rm -rf $tmp
