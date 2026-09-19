import json, sys
sys.path.insert(0, 'tools')
import numpy as np
import build_gpt2_block_css as b, build_hybrid_twelve_block as h
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_signed_hvar_chain import quantize_float_rows
from gen_proto_b import inputs
t = SafeTensors(MODEL_PATH); d = b.model_data(0)
qfc = quantize_float_rows(d['fc_weight'], bits=b.QUANT_BITS); qproj = quantize_float_rows(d['mlp_proj_weight'], bits=b.QUANT_BITS)
gfc = h.font_group(0, 'fc', qfc); gproj = h.font_group(0, 'proj', qproj)
n2 = inputs(d, t)[1]
rfc = max(1e-6, np.max(np.abs(n2))) * 1.001
fc_bases = np.sum(np.stack(gfc[1].row_bases), axis=0); proj_bases = np.sum(np.stack(gproj[1].row_bases), axis=0)
pre = n2 @ qfc.reconstructed.T + d['fc_bias']; hid = b.gelu_new(pre)
rproj = max(1e-6, np.max(np.abs(hid))) * 1.001
out = hid @ qproj.reconstructed.T + d['mlp_proj_bias']
fc_w = [(fc_bases[i] + float(qfc.codes[i].astype(float) @ (n2 / rfc))) * 512 / 1000 for i in range(4)]
pj_w = [[(gproj[1].row_bases[j][i] + float(qproj.codes[i, 256*j:256*j+256].astype(float) @ (hid[256*j:256*j+256] / rproj))) * 512 / 1000 for j in range(12)] for i in range(2)]
json.dump({'range_fc': rfc, 'range_proj': rproj, 'pre': pre[:4].tolist(), 'hidden': hid[:4].tolist(), 'out': out[:4].tolist(),
           'fc_row_width_px': fc_w, 'proj_row_width_px': pj_w, 'hm0_px': float(np.max(np.abs(hid[:256])) * 1024),
           'fc_bases': fc_bases[:4].tolist(), 'shard_row_bases_0': [int(gproj[1].row_bases[j][0]) for j in range(12)]}, open('results/debug_b_expected.json', 'w'), indent=1)
print(open('results/debug_b_expected.json').read()[:1500])
