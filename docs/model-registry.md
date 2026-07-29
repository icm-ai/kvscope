# Model registry

Model profiles live in `profiles/models/` and use schema `0.1`. Entries require a source and confidence; aliases and IDs are unique. YAML is loaded with `yaml.safe_load` when PyYAML is installed; JSON is supported without extra dependencies.

Registry data is a fallback for known profiles, not a silent replacement for a failed remote lookup. Registry configurations describe decoder metadata only. Parameter scale in a model name is never treated as an exact parameter count.
