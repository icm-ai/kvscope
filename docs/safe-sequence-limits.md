# Safe Active Sequence Limit Back-solving Specification

## Formula & Derivation

The safe maximum active sequence count $N_{\text{seqs,max}}$ is back-solved by computing the KV Cache storage requirement per active sequence under block alignment.

### Per-Sequence KV Storage Cost

$$T_{\text{effective}} = C_{\text{context}} + T_{\text{prefix}} + T_{\text{multimodal}}$$

$$T_{\text{allocated}} = \lceil \frac{T_{\text{effective}}}{S_{\text{block}}} \rceil \times S_{\text{block}}$$

$$S_{\text{sequence}} = 2 \times N_{\text{layers}} \times T_{\text{allocated}} \times N_{\text{kv\_heads}} \times D_{\text{head}} \times \text{bytes\_per\_elem}$$

### Sequence Limit Calculation

$$N_{\text{seqs,max}} = \lfloor \frac{\text{KV Budget}}{S_{\text{sequence}}} \rfloor$$

---

## Secondary Forward Verification

The back-solved active sequence limit is re-verified through forward execution of `estimate_kv_cache` and `assess_memory_feasibility`. If target feasibility status is not met, the limit is decremented by 1 until verified.

Each budget tier performs at most 100 forward-verification attempts. If the minimum active sequence count is reached without an accepted assessment, that tier returns no limit. A non-null allocatable-ceiling limit bypasses recommended headroom reserves; it is advisory and must not be used in production.
