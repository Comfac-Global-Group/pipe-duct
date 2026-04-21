# Comfac MEP Workbench — Use Cases

This document describes real-world and creative scenarios where the workbench delivers value. Each use case includes:
- **User persona** — who is using it
- **Workflow** — step-by-step
- **Value** — what they gain
- **Partner opportunity** — how allies can help

---

## UC-01: Commercial HVAC Design

**Persona:** HVAC designer / MEP consultant  
**Context:** Designing ductwork for a 10-storey office building.

### Workflow
1. Import architectural floor plans as DXF/DWG into FreeCAD
2. Draw duct routing sketches on each floor (rectangular main ducts, round branches)
3. Use **Generate Smart Duct Network** with ASHRAE/SMACNA presets
4. Auto-generate elbows, tees, and reducers at junctions
5. Adjust sketch paths; duct network updates live
6. Run BOM export for material takeoff (sheet metal gauges, insulation areas)
7. Export to IFC for clash detection with structural model

### Value
- **Hours → minutes:** Sketch-driven generation vs. manual extrusion of every duct segment
- **Standards compliance:** Gauge and pressure class rules enforced automatically
- **Change resilience:** Sketch edits propagate through entire network

### Partner Opportunity
- **Engineers:** Validate ASHRAE rules against local codes; add regional standards
- **Testers:** Create a sample 10-storey model, benchmark generation time
- **Artists:** Publish a Creative Commons demo building scene

---

## UC-02: Industrial Electrical Routing

**Persona:** Electrical designer / plant engineer  
**Context:** Routing cable trays and conduits through a factory floor.

### Workflow
1. Define equipment locations (pumps, motors, control panels)
2. Use **Smart Pipe Router** to route conduits in 3D view with axis locking
3. Select EMT, IMC, or Rigid from ASME pipe tables
4. Auto-place locknuts, couplings, and bushings at terminals
5. Generate cable trays along parallel routes with **Cable Generator**
6. Export BOM with conduit lengths, fitting counts, and tray quantities

### Value
- **NEC compliance:** Pipe types and fittings match code tables
- **Collision avoidance:** 3D routing with magnetic snapping avoids clashes
- **Procurement-ready:** BOM exports directly to purchase orders

### Partner Opportunity
- **Standards experts:** Add IEC cable tray standards, local electrical codes
- **Coders:** Integrate BOM with ERPNext / SAP procurement APIs
- **Testers:** Verify fitting placement accuracy against manufacturer catalogs

---

## UC-03: Plumbing & Drainage

**Persona:** Plumbing designer / contractor  
**Context:** Residential or commercial water supply and drainage systems.

### Workflow
1. Draw pipe routing sketches with 45° and 90° bends
2. Select Copper K/L/M or PVC schedules from pipe tables
3. Generate pipe network with auto-fittings (tees, wyes, caps)
4. Add transition reducers where pipe sizes change
5. Color-code by material using `PipeColors.json`
6. Export to IFC for coordination with architect

### Value
- **Material accuracy:** Copper type K vs. L vs. M dimensions are exact
- **Visualization:** Color-coded pipes make system types instantly readable
- **Coordination:** IFC export prevents field conflicts

### Partner Opportunity
- **Standards experts:** Add local plumbing codes (e.g., Philippine NPC, UK Water Regulations)
- **Testers:** Validate pipe wall thickness against real-world measurements

---

## UC-04: Sci-Fi / Creative Commons Scene Building

**Persona:** Indie game developer / 3D artist / worldbuilder  
**Context:** Building a spaceship interior, industrial facility, or cyberpunk alley.

### Workflow
1. Sketch pipe/duct/cable routes for "greeble" detail
2. Generate dense networks with varying pipe sizes and materials
3. Use **Sheet Metal** for corrugated wall panels and perforated screens
4. Combine with **Dodo Frames** for structural trusses and scaffolding
5. Export to glTF or OBJ for import into Blender, Godot, Unreal
6. Publish scene under Creative Commons for community reuse

### Value
- **Procedural detail:** Dense, realistic infrastructure without manual modeling
- **Parametric edits:** Change the layout, everything rebuilds
- **CC sharing:** Contribute to a shared library of MEP scenes

### Partner Opportunity
- **Artists:** Create and share CC-licensed demo scenes (factories, ships, stations)
- **Technical artists:** Write tutorials for Blender/FreeCAD/Godot workflows
- **Community managers:** Curate a scene gallery

---

## UC-05: MEP Education & Training

**Persona:** Vocational instructor / university professor  
**Context:** Teaching MEP design principles in a classroom without expensive proprietary software.

### Workflow
1. Students install FreeCAD + Comfac MEP Workbench (free, open-source)
2. Instructor provides a starter building model (from UC-01 partner scenes)
3. Students sketch pipe/duct routes and generate networks
4. Students experiment with standards: "What happens if we switch from Copper L to K?"
5. Students export BOMs and compare material costs
6. Students run clash detection (Q3 2026 feature) between MEP and structural

### Value
- **Zero license cost:** Every student can install on personal laptops
- **Hands-on standards:** JSON data files are readable; students inspect real tables
- **Industry-relevant skills:** FreeCAD + IFC workflow mirrors professional BIM pipelines

### Partner Opportunity
- **Educators:** Develop curricula and assignment rubrics
- **Technical writers:** Write step-by-step tutorials with screenshots
- **Translators:** Localize documentation and UI strings

---

## UC-06: Retrofit & Renovation Survey

**Persona:** Facility manager / renovation consultant  
**Context:** Documenting existing MEP systems in an old building for renovation planning.

### Workflow
1. Import laser scan point cloud or photogrammetry mesh into FreeCAD
2. Trace existing pipe/duct routes with sketches overlaid on scan data
3. Generate parametric models from traced routes
4. Compare existing vs. proposed layouts
5. Export BOM for demolition and replacement materials

### Value
- **As-built modeling:** Convert survey data into editable parametric models
- **Change tracking:** Sketch-based editing makes "what-if" scenarios fast
- **Material planning:** Accurate takeoffs from existing geometry

### Partner Opportunity
- **Surveyors:** Test point-cloud-to-sketch workflows; provide feedback
- **Coders:** Integrate with Open3D or CloudCompare for point cloud processing

---

## Submitting a New Use Case

1. Copy this template, fill in your scenario
2. Open a GitHub Issue with label `use-case`
3. If you have a demo scene, attach it or link to a CC-licensed repo

We especially welcome use cases from:
- Regions with unique building codes (e.g., seismic zones, tropical climates)
- Niche industries (food processing, data centers, shipbuilding)
- Creative fields (game dev, film VFX, virtual production)
