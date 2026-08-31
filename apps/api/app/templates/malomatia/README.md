# Malomatia official JD Word templates

QuantHire fills these **exact** `.docx` files to preserve Malomatia fonts, spacing, colors, and page breaks.

## Required files

| Bundled name | Official source |
|---|---|
| `leader_template.docx` | `JD Template_Leader position (1).docx` |
| `non_leader_template.docx` | `JD Template_Non-Leader position (2).docx` |
| `data_center_manager_reference.docx` | `Data Center Manager JD (1).docx` (reference only) |

## One-time setup (Windows CMD)

From repo root:

```cmd
scripts\setup_malomatia_templates.cmd
```

This copies from `Downloads` or `Downloads\JD Templates` into this folder.

## Verify structure

```cmd
cd apps\api
python ..\..\scripts\dump_malomatia_structure.py
```

## Deploy note

These files are included in the backend Docker image via `COPY apps/api /app`. Run setup **before** building/pushing the backend image for NPD.
