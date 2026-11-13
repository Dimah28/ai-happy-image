# The Happiest Morning

Entry for the make.fun bounty **"Make the AI judge happy"**
([ai-happy-01](https://make.fun/bounty/ai-happy-01), $250, ends Sat 14 Nov
2026 23:00 WIB).

## The image

`entry.png` — a 1024×1024 picture drawn entirely procedurally: the
happiest morning. One huge smiling sun rises over rolling green hills —
closed happy eyes with long lashes, a big smile, rosy cheeks, and a
daisy flower crown — with a rainbow arcing across a warm dawn sky,
hot-air balloons drifting, birds, butterflies, and a meadow full of
daisies and poppies. Down on the hill, a little white bunny waves at
the sun with a carrot beside it, a red-and-yellow kite with its own
tiny smiley face dances under the rainbow, and a red-checked picnic
blanket waits with a teapot and two cups while gold sparkles drift in
the dawn light.

The idea is a specific moment (the first morning light, the whole world
waking up smiling) rather than a stock smiley or a generic sunny scene:
one huge warm sun as the hero, so the picture still lands at ~300
pixels across.

## The program

`main.py` — Python 3.13, **standard library only** (no install step, no
network, no API key). It contains a tiny software rasteriser (scanline
polygon fill, discs, rings, arcs, thick lines, gradients, glows) and a
hand-written PNG encoder (zlib, colour type 2, per-row filter choice), so
the whole entry is one self-contained file that always writes
byte-identical output.

Run locally:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```
