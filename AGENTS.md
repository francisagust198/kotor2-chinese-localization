# Maintainer instructions

- Authoritative public text: `translations/final/{base,mod,gff}.jsonl`. Keep IDs and `source_sha256` unchanged when editing translations.
- English sources are recovered from a local legitimate installation; do not commit full game tables, archives, executables, saves or credentials.
- Use `data/current-map.json`, including transparent step 193. Never replace it with older column16 or failed HI32 maps.
- Fonts, mapped text and compatibility resources must be updated together. Compact controls, multiline descriptions and subtitles have different layout metrics.
- Run `tools/validate_public_data.py`, regression tests and local source verification for changed records. Report runtime validation separately from offline checks.
- Preserve original saves. Converter changes are restricted to recognized same-reference cached display text and produce new copies.
- Project code uses MIT; translated content, fonts and third-party code retain their own rights and provenance. Preserve `COPYRIGHT.md` and upstream notices.
- Use Issues/PRs for collaboration. Do not publish updates or contact others without maintainer authorization.
