# Reference asset attribution

The eight `.usda` files are modified, structure-only excerpts of **ForgeCAD / simready-assets**, authored by **ForgeCAD**, licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) ([legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en)). No endorsement is implied.

Source: https://huggingface.co/datasets/ForgeCAD/simready-assets
Pinned revision: `b94ea770666b6c0f82e09a78e9fcb375b223e3b1`.

`catalog.json` records each original asset URL, source file URL, SHA256, file size, package license, derivative hash and split. Four files per asset were read: root USD, physics layer, geometry layer and SimReady package manifest. The raw source geometry is not redistributed here.

Changes: compose the source physics/geometry layers under the source root; retain default world transforms as reset transforms, rigid-body flags, complete joint specifications, source geometry-member paths and collider counts. Remove visual/collision meshes, materials, animation and runtime physics scene. These excerpts are **not full renderable or simulation-certified SimReady packages**. Source dimensions/limits describe the reference asset only.

Eight assets: articulation_test_bench, bench_vise, bearing_pulley_shaft_kit, toggle_clamp_fixture_plate, gas_lift_bar_stool, gear_meshing_kit, planetary_gearbox, bar_clamp. The bearing/shaft kit and gear kit have no authored joints; retain them as negative examples. Coupling metadata in some other assets is preserved but not solved.

Reproduce with `python scripts/build_reference_templates.py <source-directory>` after downloading the exact four files per asset to their catalog paths. The script verifies pinned hashes when the catalog already exists. Runtime tools read packaged files without downloading anything.
