| variant | publishers M | anims/elem | nested | layer rules | big map | style ms / restyle | task ms | µs per publisher | first restyle ms | value ok |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| m160-sib | 160 | 64 | sib | 1 | 0 | 10.4 | 11.9 | 65 | 11.6 | y |
| m160-nest | 160 | 64 | y | 1 | 0 | 13.7 | 15.0 | 86 | 17.2 | y |
| m160-nest-l12 | 160 | 64 | y | 12 | 0 | 19.0 | 20.2 | 119 | 17.0 | y |
| m160-nest-big | 160 | 64 | y | 1 | 30000 | 37.4 | 38.5 | 234 | 46.5 | y |
| m160-nest-l12-big | 160 | 64 | y | 12 | 30000 | 41.2 | 42.4 | 257 | 39.9 | y |
| m160-sib-l12-big | 160 | 64 | sib | 12 | 30000 | 35.4 | 36.4 | 221 | 38.3 | y |
| m1200-nest | 1200 | 64 | y | 1 | 0 | 120.8 | 121.9 | 101 | 118.6 | - |
| m1200-nest-l12 | 1200 | 64 | y | 12 | 0 | 147.7 | 148.9 | 123 | 145.7 | - |
| m1200-nest-big | 1200 | 64 | y | 1 | 30000 | 158.3 | 159.4 | 132 | 150.1 | - |
| m1200-nest-l12-big | 1200 | 64 | y | 12 | 30000 | 180.2 | 181.2 | 150 | 175.0 | - |
| m1200-sib-l12-big | 1200 | 64 | sib | 12 | 30000 | 161.9 | 162.9 | 135 | 160.0 | y |
| m20-sib-l12-big | 20 | 64 | sib | 12 | 30000 | 20.4 | 21.5 | 1018 | 24.2 | y |
| m20-nest-l12-big | 20 | 64 | y | 12 | 30000 | 19.6 | 20.9 | 978 | 21.2 | y |
| a48x64-nest-l12-big | 48 | 64 | y | 12 | 30000 | 84.8 | 125.9 | 1768 | 87.1 | y |
| a6x512-nest-l12-big | 6 | 512 | y | 12 | 30000 | 85.3 | 197.2 | 14224 | 82.2 | y |
| a48x64-nest | 48 | 64 | y | 1 | 0 | 58.7 | 101.8 | 1223 | 60.0 | y |
| a6x512-nest | 6 | 512 | y | 1 | 0 | 57.6 | 167.8 | 9607 | 54.8 | y |

Per publishing element (style ms per restyle / M):
- siblings, 1 layer rule, small map: 65 µs (160) — includes applying its 64 declarations
- nested vs siblings (160): +21 µs/element for the inherited-map delta copy of the chain
- 12 @container layer-rule variants (nested, 160): +33 µs/element
- 30k inherited props declared on the ancestor: +23.7 ms per restyle at M=160, +-0.8 ms nested-vs-sib at M=20, +37.5 ms at M=1200 -> a per-pass cost of the ancestor's declarations, NOT per publisher
- M=1200 nested: 101 µs/element; with 12 layer rules: 123; + big map: 150
- animated consumers (3,072 carriers changed per mutation): 48 x 64 nested = 58.7 ms style / 101.8 ms task vs 6 x 512 = 57.6 / 167.8; with 12 layer rules + big map: 84.8 / 125.9 vs 85.3 / 197.2

