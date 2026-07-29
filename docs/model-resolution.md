# Model resolution

`kvscope.resolve_model(source, ...)` reads only model metadata and returns a `ResolvedModel` containing `ModelSpec`, raw config, provenance, warnings, confidence, and resolver attempts.

Resolver order is explicit config/ModelSpec, local JSON, Hugging Face repository ID, then built-in registry. Local-looking paths are never sent to the network. Hugging Face support is optional: install `kvscope[huggingface]`. `offline=True` only uses an exact revision cache and never calls the network.

KVScope never downloads weights, imports `transformers`, executes repository code, or enables `trust_remote_code`.
