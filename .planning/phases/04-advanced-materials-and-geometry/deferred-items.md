# Deferred Items — Phase 04

## Pre-existing Test Failures (out of scope for 04-02)

The following tests were found in test_tracer.py during 04-02 execution but belong to unimplemented plans:

### From Plan 04-03 (SolidCylinder/SolidPrism):
- `test_solid_cylinder_face_count_and_names` — needs `SolidCylinder` in `solid_body.py`
- `test_solid_cylinder_cap_normals_outward`
- `test_solid_cylinder_face_optics_propagates`
- `test_solid_prism_triangle_face_count`
- `test_solid_prism_hexagon_face_count`
- `test_solid_prism_side_normals_outward`
- `test_solid_prism_square_edge_length`
- `test_project_solid_cylinders_default_empty`
- `test_project_solid_prisms_default_empty`

### From Plan 04-04 (BSDF):
- `test_load_bsdf_csv_valid_file`
- `test_load_bsdf_csv_missing_columns`
- `test_validate_bsdf_rejects_energy_gain`
- `test_validate_bsdf_accepts_valid_profile`
- `test_sample_bsdf_uniform_roughly_hemispherical`
- `test_sample_bsdf_returns_unit_vectors`
- `test_material_bsdf_profile_name_default`

These will be resolved when Plans 04-03 and 04-04 are executed.
