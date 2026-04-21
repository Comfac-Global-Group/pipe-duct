# Comfac MEP Workbench — Roadmap

This document is the authoritative project roadmap. Items are organized by quarter, with clear entry points for contributors.

---

## Q1 2026 — Foundation (In Progress)

| Priority | Item | Status | Owner | Partner Entry |
|----------|------|--------|-------|---------------|
| **P0** | PySide6 / Qt6 compatibility | ✅ DONE | Core team | — |
| **P0** | Unified workbench registration (Dodo + Comfac) | ✅ DONE | Core team | — |
| **P0** | JSON standards reorganization | ✅ DONE | Core team | — |
| **P0** | Technical debt catalog (`TECH_DEBT.md`) | ✅ DONE | Core team | — |
| **P1** | Smoke testing framework (FreeCAD headless) | 🔲 OPEN | — | See `PARTNERS.md` — Testers |
| **P1** | Pipe standard expansion (ISO, JIS, DIN) | 🔲 OPEN | — | See `PARTNERS.md` — Standards |
| **P2** | README + documentation suite polish | ✅ DONE | Core team | — |
| **P2** | BOM CSV format standardization | 🔲 OPEN | — | See `PARTNERS.md` — Analysts |

**Exit criteria for Q1:**
- All FreeCAD 1.0+ users can install and launch without import errors
- At least one automated smoke test passes in CI
- Documentation suite is complete and accurate

---

## Q2 2026 — Interoperability & Performance

| Priority | Item | Rationale | Partner Entry |
|----------|------|-----------|---------------|
| **P0** | IFC export integration | BIM collaboration; FreeCAD 1.0 BIM workbench is now core | Coders, BIM experts |
| **P0** | Performance: optimize boolean fusion for 100+ segment networks | Current `Refine=True` on all outputs is slow | Coders, algorithm people |
| **P1** | Unified UI theme / icon set | Dodo icons are legacy; Comfac needs consistent branding | Designers, UX |
| **P1** | Duct standard expansion (ISO 15065, DW/144) | Global market reach | Standards experts |
| **P2** | Refactor pipe/duct shared code (~70% duplication) | `HD-02` in `TECH_DEBT.md` | Coders |
| **P2** | Live parametric observers for Dodo frames | `HD-03` in `TECH_DEBT.md` | Coders |

**Exit criteria for Q2:**
- Pipe/duct networks export valid IFC that opens in Revit/BIMcollab
- 100-segment network generates in < 5 seconds
- No new duplicate code introduced; old duplication reduced by 50%

---

## Q3 2026 — Engineering Features

| Priority | Item | Rationale | Partner Entry |
|----------|------|-----------|---------------|
| **P0** | Clash detection (pipe-pipe, pipe-duct, pipe-structure) | MEP coordination workflow | Coders, engineers |
| **P0** | Automatic hanger/support placement | Generate support geometry from network topology | Engineers, coders |
| **P1** | Cloud-ready BOM (JSON API, not just CSV) | Integration with procurement/ERP | Coders, ERP integrators |
| **P1** | Pressure drop / flow calculation hooks | Connect to external solvers (e.g., EPANET) | Engineers, scientists |
| **P2** | Cable tray routing with bend radius rules | NEC/BS compliance for fiber optics | Standards experts |
| **P2** | Sheet metal unfolding / flat patterns | Fabrication-ready outputs | Fabricators, coders |

**Exit criteria for Q3:**
- Clash detection runs on a 500-element model in < 10 seconds
- BOM can be consumed by at least one external tool (ERP or spreadsheet)

---

## Q4 2026 — Advanced & Community

| Priority | Item | Rationale | Partner Entry |
|----------|------|-----------|---------------|
| **P1** | Generative routing — auto-route between terminals with constraints | AI/optimization-assisted design | ML researchers, coders |
| **P1** | AR/VR preview mode | Export to glTF / USD for headset viewing | XR developers |
| **P2** | Community scene library (Creative Commons) | Shareable demo projects | Artists, educators |
| **P2** | Interactive tutorials embedded in workbench | Onboarding for new users | Educators, UX writers |
| **P3** | Plugin architecture for custom fitting types | Third-party extensibility | Coders, integrators |

---

## Long-term Vision

**Goal:** Be the standard open-source MEP workbench for FreeCAD — comparable to what BIM Workbench is for architecture.

**Key bets:**
1. **Procedural generation** beats manual modeling for MEP scale
2. **Open standards** (IFC, JSON, CSV) beat proprietary formats
3. **Live parametrics** beat static imports
4. **Community contributions** in standards, scenes, and testing beat closed development

---

## How to Claim a Roadmap Item

1. Open a GitHub Issue referencing this roadmap and the item ID
2. Comment on the issue with your plan and estimated timeline
3. Core team will assign and provide guidance
4. Submit PR; review within 7 days

See `PARTNERS.md` for skill-matched task cards and first-time contributor guidance.
