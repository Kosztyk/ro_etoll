# RO eToll — Validation status

## v1.0.2 checks

GitHub Actions runs HACS validation (with no ignored checks), Home Assistant
Hassfest validation, and repository/package tests with Python compilation.

Run static checks from the repository root:

```bash
python3 tools/check_repository.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
```

These tests validate the package and its metadata only. They do not log into
portal.etoll.ro or test real vehicle, rovinietă, invoice, or bridge crossing data.

The README for an earlier beta described 97 functional tests, but those test
sources and referenced TESTING.md, API_NOTES.md, BRANDING.md, ORIGIN.md and
MIGRATION.md are not in the published repository. Their findings are not
reproduced by this packaging update.

Do not attach eToll credentials, tokens, number plates, invoices, or
personally identifiable information to public issue reports.
