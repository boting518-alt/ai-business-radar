# Intelligence Translation Validation

Local validation data; not production intelligence.

- Generated: 20260907T163243Z
- Processed: 6 entities / 14 fields
- Prompt SHA-256: `1519c6cb9aa7569db5988f45119769ea8595b509cecac7c3df3c01bcb1edb28e`

## signal `0a74cce1-79ee-47e1-b270-b7da6f6f5736`

- Translated: statement, evidence_text
- Reused: none
- Provider/model: openai / gpt-5.6-terra
- Version: translation-zh-CN-v001
- Tokens: input=460, output=80

## signal `3f5b6fcd-b047-4bf1-9785-678f9de34311`

- Translated: statement, evidence_text
- Reused: none
- Provider/model: openai / gpt-5.6-terra
- Version: translation-zh-CN-v001
- Tokens: input=480, output=97

## signal `4097d6ce-4c26-4e38-b190-c7da02030778`

- Translated: statement, evidence_text
- Reused: none
- Provider/model: openai / gpt-5.6-terra
- Version: translation-zh-CN-v001
- Tokens: input=462, output=69

## opportunity `7eea70c0-eeee-4db5-9cd0-ca73dcd42861`

- Translated: name, one_line_thesis, problem, solution
- Reused: none
- Provider/model: openai / gpt-5.6-terra
- Version: translation-zh-CN-v001
- Tokens: input=528, output=154

## Source hashes

- `opportunity/name`: `4b9ddcb925658f24320705fc20313afc3b5a0320c2c84c282aa747f084524798`
- `opportunity/one_line_thesis`: `fb37c286b643cdd0de1b51e77828461218fc0985573a52e5f26daa20c7f5ec20`
- `opportunity/problem`: `01bc1f1062737bf23e5349e9a0c446762b663023fba9eff0ffec63be74d1bcff`
- `opportunity/solution`: `be55a257f7bb4591203044dd2fbfbaa201dae8e331a8dfc0225ec9f836a5df45`
- `0a74cce1/statement`: `fb37c286b643cdd0de1b51e77828461218fc0985573a52e5f26daa20c7f5ec20`
- `0a74cce1/evidence_text`: `c5938ac0115177adcabf4096fd4923cfa744ce80f47b61e6e9559c18f92c5c5a`
- `3f5b6fcd/statement`: `276092c9dd41c872ba562b888bc06d9ae2c7548310e18955f07bc989d43626d2`
- `3f5b6fcd/evidence_text`: `1bdd89a15b1a5830ef620d3ba37012695d3abbe3ff6988ccc29ec06ec324180f`
- `4097d6ce/statement`: `62c38c44a9e1821ce84f586c8b36e354106e55e8ef21f77d814d65e731a13d75`
- `4097d6ce/evidence_text`: `367a6f13d9e77c6cc52e64945ca738902225f517bd164551e027d9d43ef5bfbf`
- `63eda4a9/statement`: `6c3b94275aae56a98d51476bd5da69d5dd69d7633a5c61f7c6fab867bb25ed41`
- `63eda4a9/evidence_text`: `83f962fa18333a6d8b7e957e698bcde889ae5a13d67ced1374796a99b2a25cb1`
- `6926dc73/statement`: `3a4a002702098febe382e2e582da906ee9bda3f5238931a5050cd08ba708ce41`
- `6926dc73/evidence_text`: `3f5d0f238af4983b4bf317a0bcbb277142ccbb8620c37e485d544e6cb17e4e02`

Database verification: 14/14 hashes match the current canonical field; 14/14 rows have prompt hash,
provider request ID, and input/output token audit values.

## API locale and fallback verification

- The Radar query service returned localized Chinese content for all five signals and the active
  opportunity when called with `locale=zh-CN`.
- `locale=en-US` returned canonical English for the same records.
- Original evidence remained available independently of the translated evidence projection.
- Video titles and channel names were unchanged.
- Missing-projection fallback was verified with signal
  `87a98d7b-a35e-4522-8b1d-995d68a3603a`; its `zh-CN` read returned canonical content.
- Product reads used the database-only localization service and made no translation-provider call.

## Quality observations

- `VitalDesk` was preserved in translated content.
- Claim/evidence quotations stayed attributed rather than being promoted to facts.
- Four signal translations and the opportunity read naturally enough for validation.
- Signal `0a74cce1-79ee-47e1-b270-b7da6f6f5736` contains awkward word order around `VitalDesk` and
  should be included in TASK-035 prompt-quality review; it was retained here as the real provider
  output rather than silently edited.

## signal `63eda4a9-3176-45ad-8ecf-fecfcd7c954d`

- Translated: statement, evidence_text
- Reused: none
- Provider/model: openai / gpt-5.6-terra
- Version: translation-zh-CN-v001
- Tokens: input=474, output=94

## signal `6926dc73-ae72-4378-80df-c29a659dcd35`

- Translated: statement, evidence_text
- Reused: none
- Provider/model: openai / gpt-5.6-terra
- Version: translation-zh-CN-v001
- Tokens: input=462, output=69
