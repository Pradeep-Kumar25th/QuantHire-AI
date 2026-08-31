# QuantHire AI brand assets

Official logo: **Multi-Agent · Explainable · Evidence-Backed**

## Regenerate all assets (required after logo update)

Double-click or run in **cmd**:

```cmd
cd /d "d:\QuantHire AI\apps\web"
scripts\regenerate-brand-assets.cmd
```

Or:

```cmd
cd /d "d:\QuantHire AI\apps\web"
pip install Pillow
npm run brand:assets
```

**Source of truth:** `quanthire-logo-source.png` (official horizontal lockup)

**Generated files:**
| File | Use |
|------|-----|
| `quanthire-logo-full.png` | Home hero (includes feature pills) |
| `quanthire-logo-nav.png` | Sidebar, login, mobile header (no pills) |
| `quanthire-mark.png` | Circular Q favicon / mark |
| `../favicon.ico` | Browser tab |
| `../apple-icon.png` | Apple touch icon |

Commit all PNGs and favicon files before Docker deploy.

## UI placements (`QuantHireLogo`)

| Location | Variant | Height |
|----------|---------|--------|
| Home header | nav | 44px |
| Home hero | full | 140–196px |
| Sidebar | nav | 44px |
| Mobile header | nav | 36px |
| Login | nav | 56px |
| Browser tab | mark / favicon | 32px |
