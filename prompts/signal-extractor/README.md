# Signal extractor prompts

`v001.md` is paired with the shared `BusinessSignalExtractorOutput` v001 schema. Versions are
selected explicitly; there is no `latest` fallback. Once used, a version is immutable.

The corresponding generated contract is `packages/schemas/json/signal_extractor.v001.schema.json`. Provider and model selection are runtime configuration and must not be hardcoded in this folder.
