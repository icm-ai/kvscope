# Safe Context Length Back-solving Specification

## Formula & Derivation

The safe maximum context length $C_{\text{max}}$ is back-solved by holding fixed memory overheads constant and allocating remaining memory budget to KV Cache.

### Fixed Components

$$\text{Fixed Overhead} = \text{Resident Weights} + \text{Runtime Overhead}$$

$$\text{Fixed Tokens} = T_{\text{prefix}} + T_{\text{multimodal}}$$

### Available KV Budget

$$\text{KV Budget} = B_{\text{target}} - \text{Fixed Overhead}$$

For Guaranteed Safe:
$$B_{\text{target}} = \text{recommended\_allocatable.lower} - \text{weights.upper} - \text{runtime.upper}$$

For Expected Safe:
$$B_{\text{target}} = \text{recommended\_allocatable.expected} - \text{weights.expected} - \text{runtime.expected}$$

### Per-Token KV Storage Cost

$$S_{\text{token}} = 2 \times N_{\text{layers}} \times N_{\text{kv\_heads}} \times D_{\text{head}} \times \text{bytes\_per\_elem} \times N_{\text{seqs}}$$

### Block Alignment & Back-solving

$$\text{Max Allocated Tokens} = \lfloor \frac{\text{KV Budget}}{S_{\text{token}}} \rfloor$$

$$\text{Aligned Tokens} = \lfloor \frac{\text{Max Allocated Tokens}}{S_{\text{block}}} \rfloor \times S_{\text{block}}$$

$$C_{\text{max}} = \text{Aligned Tokens} - \text{Fixed Tokens}$$

---

## Secondary Forward Verification

Algebraically back-solved context limits are strictly re-verified by:
1. Constructing a trial `InferenceConfig` with `context_length = C_{\text{max}}`.
2. Re-computing KV Cache storage via `estimate_kv_cache` / `calculate_kv_cache`.
3. Executing Phase 7 `assess_memory_feasibility`.
4. If verification fails, $C_{\text{max}}$ is decremented by $S_{\text{block}}$ (or 1) until target feasibility status is achieved.
