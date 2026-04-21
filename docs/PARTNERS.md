# Comfac MEP Workbench — Partner & Ally Guide

**Welcome, potential collaborator.** This document is for humans and organizations who want to contribute to the Comfac MEP Workbench. Whether you're a developer, tester, artist, educator, standards expert, or just a curious FreeCAD user, there's a task card for you.

---

## How to Contribute

1. **Read this guide** — Find your skill match below
2. **Pick a task card** — Or propose your own
3. **Open a GitHub Issue** — Reference the task card ID (e.g., `TC-TEST-01`)
4. **Get aligned** — Core team will respond within 48 hours
5. **Ship it** — Submit a PR; we review within 7 days

**No commit bit required.** We accept patches, scenes, test data, documentation, and bug reports from anyone.

---

## Contributor Roles

### 🔬 Testers & QA

**You are:** Someone who uses FreeCAD, installs workbenches, and notices when things break. No coding required.

**Task Cards:**

| ID | Task | Difficulty | Time |
|----|------|------------|------|
| **TC-TEST-01** | Smoke test on FreeCAD 0.21 (Qt5) — install, launch, generate pipe network, generate duct network | Easy | 30 min |
| **TC-TEST-02** | Smoke test on FreeCAD 1.0+ (Qt6) — same as above | Easy | 30 min |
| **TC-TEST-03** | Stress test: generate a pipe network with 50+ segments, measure time | Medium | 1 hour |
| **TC-TEST-04** | Validate ASME pipe dimensions against a real-world catalog (e.g., Mueller, Viega) | Medium | 2 hours |
| **TC-TEST-05** | Test on macOS — report any path or UI issues | Easy | 30 min |
| **TC-TEST-06** | Test on Windows — report any path or UI issues | Easy | 30 min |
| **TC-TEST-07** | Create a reproducible bug report template for the project | Easy | 1 hour |

**Deliverable:** GitHub Issue with results, screenshots, and FreeCAD version info (`Help → About FreeCAD → Copy to clipboard`).

---

### 🎨 Creative Commons Scene Artists

**You are:** A 3D artist, worldbuilder, or technical artist who creates environments. You use FreeCAD, Blender, or similar tools.

**Task Cards:**

| ID | Task | Difficulty | Time |
|----|------|------------|------|
| **TC-ART-01** | Create a small factory floor scene with pipe/duct/cable networks (CC-BY or CC0) | Medium | 4 hours |
| **TC-ART-02** | Create a spaceship/engine room scene with dense pipe greebles (CC-BY or CC0) | Medium | 4 hours |
| **TC-ART-03** | Create a residential plumbing demo with visible pipe types color-coded (CC-BY or CC0) | Easy | 2 hours |
| **TC-ART-04** | Design a consistent icon set for all Comfac MEP toolbar commands (SVG, 64×64) | Medium | 8 hours |
| **TC-ART-05** | Record a 2-minute screen capture of pipe network generation for tutorial use | Easy | 1 hour |

**Deliverable:** `.FCStd` file or `.zip` with scene, uploaded to GitHub Release or linked in Issue. License must be CC-BY, CC-BY-SA, or CC0.

---

### 👨‍💻 Coders & Developers

**You are:** A Python developer, FreeCAD scripter, or software engineer who can read and write code.

**Task Cards:**

| ID | Task | Difficulty | Time | Skills |
|----|------|------------|------|--------|
| **TC-DEV-01** | Add ISO 4200 pipe standard to `PipeData.json` | Easy | 2 hours | JSON, standards research |
| **TC-DEV-02** | Add JIS G 3454 pipe standard to `PipeData.json` | Easy | 2 hours | JSON, standards research |
| **TC-DEV-03** | Write a headless smoke test: import all modules, verify no import errors | Medium | 3 hours | Python, pytest, FreeCAD API |
| **TC-DEV-04** | Refactor shared pipe/duct code: extract common observer logic into `mep/core/` | Hard | 8 hours | Python, OOP, FreeCAD |
| **TC-DEV-05** | Add IFC export for pipe networks (using `IfcOpenShell` or FreeCAD's built-in IFC) | Hard | 16 hours | Python, IFC, BIM |
| **TC-DEV-06** | Optimize boolean fusion: skip `Refine=True` on intermediate shapes, apply only at end | Medium | 4 hours | Python, FreeCAD Part API |
| **TC-DEV-07** | Add automatic hanger/support placement along pipe/duct networks | Medium | 8 hours | Python, geometry |
| **TC-DEV-08** | Implement clash detection (bounding-box first, then mesh intersection) | Hard | 12 hours | Python, computational geometry |
| **TC-DEV-09** | Add DW/144 duct standard to `ASHRAE_SMACNA_Rectangular.json` | Easy | 2 hours | JSON, standards research |
| **TC-DEV-10** | Write a BOM JSON API endpoint (CLI tool that outputs structured JSON) | Medium | 4 hours | Python, JSON |

**Deliverable:** Pull Request with code, tests (if applicable), and documentation update.

**First-time contributor tip:** Start with `TC-DEV-01`, `TC-DEV-02`, or `TC-DEV-09` — they require no FreeCAD API knowledge, just accurate standards research and JSON editing.

---

### 📚 Technical Writers & Translators

**You are:** Someone who writes clearly, creates tutorials, or speaks multiple languages.

**Task Cards:**

| ID | Task | Difficulty | Time |
|----|------|------------|------|
| **TC-DOC-01** | Write a "Getting Started with Pipe Networks" tutorial (with screenshots) | Easy | 3 hours |
| **TC-DOC-02** | Write a "Getting Started with Duct Networks" tutorial (with screenshots) | Easy | 3 hours |
| **TC-DOC-03** | Translate README.md to Filipino/Tagalog | Easy | 2 hours |
| **TC-DOC-04** | Translate README.md to Spanish | Easy | 2 hours |
| **TC-DOC-05** | Write a "Contributing Standards Data" guide | Easy | 2 hours |
| **TC-DOC-06** | Create a FAQ from common GitHub Issues | Easy | 2 hours |

**Deliverable:** Markdown file in a GitHub Issue or Pull Request.

---

### 🏗️ Standards Experts & Engineers

**You are:** A mechanical engineer, HVAC designer, plumber, or standards researcher who knows the codes.

**Task Cards:**

| ID | Task | Difficulty | Time |
|----|------|------------|------|
| **TC-STD-01** | Review ASME B36.10M data in `PipeData.json` for accuracy | Easy | 1 hour |
| **TC-STD-02** | Add Philippine National Plumbing Code pipe tables | Medium | 3 hours |
| **TC-STD-03** | Add UK Water Regulations pipe/fitting data | Medium | 3 hours |
| **TC-STD-04** | Review ASHRAE duct gauge rules for correctness | Easy | 1 hour |
| **TC-STD-05** | Propose a new data format for pressure-drop coefficients | Medium | 2 hours |

**Deliverable:** GitHub Issue with data, source citations, and proposed JSON structure.

---

### 🎓 Educators & Curriculum Designers

**You are:** A teacher, professor, or trainer who uses open-source tools in the classroom.

**Task Cards:**

| ID | Task | Difficulty | Time |
|----|------|------------|------|
| **TC-EDU-01** | Design a 1-hour lesson plan: "Introduction to MEP with FreeCAD" | Easy | 3 hours |
| **TC-EDU-02** | Design a 3-hour workshop: "Sketch-Driven Pipe Networks" | Easy | 4 hours |
| **TC-EDU-03** | Create a rubric for assessing student MEP models | Easy | 2 hours |
| **TC-EDU-04** | Record a 15-minute video walkthrough of the workbench | Easy | 2 hours |

**Deliverable:** Markdown or PDF in a GitHub Issue. We will link to it from the project wiki.

---

## Skill-Matching Quick Reference

| I know how to... | Start with... |
|------------------|---------------|
| Install FreeCAD and click buttons | `TC-TEST-01`, `TC-TEST-02` |
| Model in FreeCAD / Blender | `TC-ART-01`, `TC-ART-02`, `TC-ART-03` |
| Edit JSON files and read standards | `TC-DEV-01`, `TC-DEV-02`, `TC-STD-01` |
| Write Python | `TC-DEV-03`, `TC-DEV-06`, `TC-DEV-10` |
| Write FreeCAD scripts / macros | `TC-DEV-04`, `TC-DEV-07` |
| Work with IFC / BIM | `TC-DEV-05`, `TC-DEV-08` |
| Write tutorials / translate | `TC-DOC-01`–`TC-DOC-06` |
| Teach classes | `TC-EDU-01`–`TC-EDU-04` |
| Read engineering standards | `TC-STD-01`–`TC-STD-05` |

---

## Recognition

All contributors are recognized in:
- `CONTRIBUTORS.md` (we will create this after the first external contribution)
- Release notes for each version
- Project wiki contributor gallery

**Creative Commons scene artists** retain full credit and license control over their scenes. We only require a CC license so the community can reuse and learn from them.

---

## Code of Conduct

- Be respectful and constructive
- Assume good intent
- Focus on the work, not the person
- Ask questions — no question is too basic

Report conduct issues to the core team via GitHub Issues (private issue, or email if available).

---

## Contact

- **GitHub Issues:** [github.com/Comfac-Global-Group/pipe-duct/issues](https://github.com/Comfac-Global-Group/pipe-duct/issues)
- **Task cards:** This document — pick one and open an issue
- **General questions:** Open a GitHub Discussion (when enabled) or Issue with label `question`
