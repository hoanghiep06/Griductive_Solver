# Kết quả tests Dataset V2 — 10/11/2026

Python 3.14.4, pytest 9.2.0; python-sat 1.9.dev21 / MiniSat22.

Lệnh: `.venv/bin/python -m pytest -q --junitxml=/tmp/phuoc-v2-tests.xml`

PASSED: **253**; FAILED: **0**; SKIPPED: **30**; ERRORS: **0**.

**BLOCKED:** 30 integration tests cần DPLL của Huy và Encoder của Phong. BLOCKED là lý do cho cùng 30 SKIPPED, không phải 30 test khác.

Đã thực chạy: reference CNF/evaluator truth tables; minimum support; uniqueness blocking;
row-major no-guess; privacy; trace corruption; invalid data; backup; reproducibility;
graph invariance; generation/publication rollback; preview data; full GameEngine reveals với SAT tham chiếu.
Core + reference integration không được tính là DPLL/CNF của nhóm.

| Module | Passed | Failed | Skipped | Errors |
|---|---:|---:|---:|---:|
| tests.test_entailment | 60 | 0 | 0 | 0 |
| tests.test_game_engine.GameEngineTests | 17 | 0 | 0 | 0 |
| tests.test_integration_phuoc | 17 | 0 | 30 | 0 |
| tests.test_public_kb.PublicKBTests | 10 | 0 | 0 | 0 |
| tests.test_puzzle_validator.PuzzleValidatorTests | 15 | 0 | 0 | 0 |
| tests.test_puzzles | 38 | 0 | 0 | 0 |
| tests.test_puzzles_multiclue | 90 | 0 | 0 | 0 |
| tests.test_variable_map.VariableMapTests | 6 | 0 | 0 | 0 |

## Kiểm tra preview qua trình duyệt

- Đã chọn lần lượt cả 15 map, xác nhận số card là 9/16/25 tương ứng.
- Đã chuyển baseline/V2, next step, highlight support và toggle đáp án.
- Mặc định ẩn đáp án; chỉ hiển thị clue đã công khai theo slider.
- Ảnh review: phuoc_dataset_v2_preview.jpg. Không tính browser smoke thành pytest tests.

| Testcase | Trạng thái |
|---|---|
| `tests.test_entailment::test_classification[clauses0-1-CRIMINAL]` | PASSED |
| `tests.test_entailment::test_classification[clauses1-1-INNOCENT]` | PASSED |
| `tests.test_entailment::test_classification[clauses2-1-UNKNOWN]` | PASSED |
| `tests.test_entailment::test_classification[clauses3-1-INCONSISTENT]` | PASSED |
| `tests.test_entailment::test_classification[clauses4-2-CRIMINAL]` | PASSED |
| `tests.test_entailment::test_classification[clauses5-1-UNKNOWN]` | PASSED |
| `tests.test_entailment::test_classification[clauses6-1-INCONSISTENT]` | PASSED |
| `tests.test_entailment::test_classification[clauses7-1-UNKNOWN]` | PASSED |
| `tests.test_entailment::test_classification[clauses8-8-UNKNOWN]` | PASSED |
| `tests.test_entailment::test_immutability_repeated_calls_even_with_mutating_solver` | PASSED |
| `tests.test_entailment::test_batch_checks_consistency_once_and_tracks_calls` | PASSED |
| `tests.test_entailment::test_batch_inconsistent_or_empty[clauses0-1]` | PASSED |
| `tests.test_entailment::test_batch_inconsistent_or_empty[clauses1-1]` | PASSED |
| `tests.test_entailment::test_first_forced_is_row_major_independent_of_mapping_and_variable_ids` | PASSED |
| `tests.test_entailment::test_first_forced_never_selects_unknown_or_inconsistent[clauses0]` | PASSED |
| `tests.test_entailment::test_first_forced_never_selects_unknown_or_inconsistent[clauses1]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[None-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses1-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[1-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses3-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses4-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses5-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses6-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses7-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses8-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses9-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_cnf[clauses10-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_variable[0-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_variable[-1-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_variable[True-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_variable[1.0-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_variable[1-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_variable[None-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved0-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[None-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved2-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved3-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved4-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved5-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved6-TypeError]` | PASSED |
| `tests.test_entailment::test_invalid_unresolved[unresolved7-ValueError]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[None]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[0]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[1]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[SAT]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[UNSAT]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[output5]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[output6]` | PASSED |
| `tests.test_entailment::test_invalid_solver_status_never_uses_truthiness[output7]` | PASSED |
| `tests.test_entailment::test_invalid_both_assumptions_unsat_raises` | PASSED |
| `tests.test_entailment::test_invalid_assumption_status_is_rejected[answers0]` | PASSED |
| `tests.test_entailment::test_invalid_assumption_status_is_rejected[answers1]` | PASSED |
| `tests.test_entailment::test_explicit_solver_adapter_and_error_propagation` | PASSED |
| `tests.test_entailment::test_constructor_contract` | PASSED |
| `tests.test_entailment::test_official_map_rejects_auxiliaries_mismatches_and_unallocated_literals` | PASSED |
| `tests.test_entailment::test_bridge_uses_official_entailment_result[clauses0]` | PASSED |
| `tests.test_entailment::test_bridge_uses_official_entailment_result[clauses1]` | PASSED |
| `tests.test_entailment::test_bridge_uses_official_entailment_result[clauses2]` | PASSED |
| `tests.test_entailment::test_bridge_uses_official_entailment_result[clauses3]` | PASSED |
| `tests.test_entailment::test_privacy_checker_only_accepts_public_cnf_and_mapping` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_already_solved_character_is_rejected` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_bad_input_and_wrong_proof_target_are_rejected` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_character_info_is_detached_and_character_is_immutable` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_entailment_result_requires_consistent_sat_evidence` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_forced_verdict_is_accepted_and_reveals_clue_atomically` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_inconsistent_public_kb_has_explicit_response` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_initial_reveals_seed_public_kb_only` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_integrity_guard_rejects_forced_status_conflicting_with_hidden_key` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_load_failure_preserves_current_game` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_opposite_forced_status_is_contradicted_without_state_change` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_public_state_does_not_expose_hidden_data_or_unrevealed_clues` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_reload_makes_previous_entailment_result_stale` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_restart_restores_initial_state_and_keeps_variable_mapping` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_row_major_order_is_independent_of_json_order` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_sample_names_are_alphabetical_across_rows` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_stale_entailment_result_is_rejected` | PASSED |
| `tests.test_game_engine.GameEngineTests::test_unknown_is_not_provable_for_both_claimed_statuses` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[3x3_01]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[3x3_02]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[3x3_03]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[3x3_04]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[3x3_05]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[4x4_01]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[4x4_02]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[4x4_03]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[4x4_04]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[4x4_05]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[5x5_01]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[5x5_02]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[5x5_03]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[5x5_04]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_loads_dataset_and_exposes_only_public_initial_state[5x5_05]` | PASSED |
| `tests.test_integration_phuoc::test_real_core_accepts_bridge_from_public_fact_with_test_solver` | PASSED |
| `tests.test_integration_phuoc::test_real_core_rejects_unproved_and_contradicted_bridge_with_test_solver` | PASSED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[3x3_01]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[3x3_02]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[3x3_03]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[3x3_04]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[3x3_05]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[4x4_01]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[4x4_02]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[4x4_03]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[4x4_04]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[4x4_05]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[5x5_01]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[5x5_02]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[5x5_03]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[5x5_04]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_progressive_and_deterministic[5x5_05]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[3x3_01]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[3x3_02]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[3x3_03]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[3x3_04]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[3x3_05]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[4x4_01]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[4x4_02]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[4x4_03]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[4x4_04]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[4x4_05]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[5x5_01]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[5x5_02]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[5x5_03]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[5x5_04]` | SKIPPED |
| `tests.test_integration_phuoc::test_real_dpll_encoder_uniqueness_blocks_only_primary_variables[5x5_05]` | SKIPPED |
| `tests.test_public_kb.PublicKBTests::test_clue_cannot_be_revealed_before_its_owner_is_proved` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_conflicting_verdict_is_rejected_and_identical_is_idempotent` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_duplicate_clue_is_idempotent_but_conflicting_id_is_rejected` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_exposed_collections_are_detached` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_record_reveal_is_atomic_and_increments_version_once` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_record_reveal_rejects_bad_owner_without_partial_update` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_snapshot_contains_unit_clauses` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_snapshot_is_read_only_and_clone_preserves_version` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_unknown_character_is_rejected` | PASSED |
| `tests.test_public_kb.PublicKBTests::test_verdicts_become_correct_unit_clauses` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_count_outside_region_size_is_rejected` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_duplicate_coordinate_is_rejected` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_explicit_region_duplicate_is_rejected` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_extension_clue_requires_and_uses_registered_evaluator` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_false_clue_under_hidden_solution_is_rejected` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_hidden_solution_must_be_boolean_and_complete` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_legacy_clue_dictionary_format_remains_readable` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_missing_character_is_rejected` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_sample_has_exactly_one_complete_assignment` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_sample_is_sequentially_solvable_without_guessing` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_sample_loads_and_every_clue_matches_hidden_solution` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_sequential_checker_detects_the_previous_stuck_sample` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_sequential_checker_refuses_large_exhaustive_run_by_default` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_unexpected_parameters_are_rejected` | PASSED |
| `tests.test_puzzle_validator.PuzzleValidatorTests::test_unknown_clue_reference_is_rejected` | PASSED |
| `tests.test_puzzles::test_exactly_fifteen_dataset_files_and_five_per_size` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[3x3_01]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[3x3_02]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[3x3_03]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[3x3_04]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[3x3_05]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[4x4_01]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[4x4_02]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[4x4_03]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[4x4_04]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[4x4_05]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[5x5_01]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[5x5_02]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[5x5_03]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[5x5_04]` | PASSED |
| `tests.test_puzzles::test_schema_semantics_unique_solution_and_progressive_proof[5x5_05]` | PASSED |
| `tests.test_puzzles::test_all_six_templates_four_regions_and_varied_boards` | PASSED |
| `tests.test_puzzles::test_generator_is_byte_for_byte_reproducible` | PASSED |
| `tests.test_puzzles::test_fixed_seed_is_local_and_alternate_seed_is_valid` | PASSED |
| `tests.test_puzzles::test_3x3_exhaustive_cross_check_independent_of_constructive_proof[3x3_01]` | PASSED |
| `tests.test_puzzles::test_3x3_exhaustive_cross_check_independent_of_constructive_proof[3x3_02]` | PASSED |
| `tests.test_puzzles::test_3x3_exhaustive_cross_check_independent_of_constructive_proof[3x3_03]` | PASSED |
| `tests.test_puzzles::test_3x3_exhaustive_cross_check_independent_of_constructive_proof[3x3_04]` | PASSED |
| `tests.test_puzzles::test_3x3_exhaustive_cross_check_independent_of_constructive_proof[3x3_05]` | PASSED |
| `tests.test_puzzles::test_neighbors_eight_directions_center_excluded` | PASSED |
| `tests.test_puzzles::test_public_inference_soundness_and_contradiction` | PASSED |
| `tests.test_puzzles::test_progressive_reasoner_receives_only_revealed_clues` | PASSED |
| `tests.test_puzzles::test_unique_does_not_imply_no_guess` | PASSED |
| `tests.test_puzzles::test_ambiguous_full_clues_are_not_marked_unique` | PASSED |
| `tests.test_puzzles::test_corrupt_dataset_is_rejected[duplicate_region]` | PASSED |
| `tests.test_puzzles::test_corrupt_dataset_is_rejected[invalid_cell]` | PASSED |
| `tests.test_puzzles::test_corrupt_dataset_is_rejected[false_clue]` | PASSED |
| `tests.test_puzzles::test_corrupt_dataset_is_rejected[bad_name]` | PASSED |
| `tests.test_puzzles::test_corrupt_dataset_is_rejected[coordinate]` | PASSED |
| `tests.test_puzzles::test_corrupt_dataset_is_rejected[count]` | PASSED |
| `tests.test_puzzles::test_manifest_matches_recomputed_reports` | PASSED |
| `tests.test_puzzles::test_validator_cli_reports_failed_schema_without_traceback` | PASSED |
| `tests.test_puzzles::test_local_enumeration_limit_prevents_board_wide_search` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[3x3_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[3x3_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[3x3_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[3x3_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[3x3_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[4x4_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[4x4_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[4x4_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[4x4_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[4x4_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[5x5_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[5x5_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[5x5_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[5x5_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_reference_cnf_matches_independent_semantics_for_every_local_assignment[5x5_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[0-EXACTLY]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[0-AT_LEAST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[0-AT_MOST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[1-EXACTLY]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[1-AT_LEAST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[1-AT_MOST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[2-EXACTLY]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[2-AT_LEAST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[2-AT_MOST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[3-EXACTLY]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[3-AT_LEAST]` | PASSED |
| `tests.test_puzzles_multiclue::test_counting_boundaries[3-AT_MOST]` | PASSED |
| `tests.test_puzzles_multiclue::test_two_clue_support_preserves_all_known_verdicts` | PASSED |
| `tests.test_puzzles_multiclue::test_three_clue_support_exhausts_every_pair` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[3x3_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[3x3_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[3x3_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[3x3_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[3x3_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[4x4_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[4x4_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[4x4_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[4x4_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[4x4_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[5x5_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[5x5_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[5x5_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[5x5_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_exact_minimality_and_multi_clue_targets[5x5_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_forged_certificates_are_rejected[multi_label]` | PASSED |
| `tests.test_puzzles_multiclue::test_forged_certificates_are_rejected[hidden_clue]` | PASSED |
| `tests.test_puzzles_multiclue::test_forged_certificates_are_rejected[known_facts]` | PASSED |
| `tests.test_puzzles_multiclue::test_forged_certificates_are_rejected[wrong_verdict]` | PASSED |
| `tests.test_puzzles_multiclue::test_unsat_puzzle_reference_solver_rejects_without_fabricated_key` | PASSED |
| `tests.test_puzzles_multiclue::test_structural_fingerprint_is_invariant_under_cell_renaming` | PASSED |
| `tests.test_puzzles_multiclue::test_structural_diversity_and_baseline_improvement` | PASSED |
| `tests.test_puzzles_multiclue::test_failed_generation_leaves_existing_dataset_unchanged` | PASSED |
| `tests.test_puzzles_multiclue::test_baseline_backup_exactly_matches_original_commit` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[3x3_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[3x3_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[3x3_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[3x3_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[3x3_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[4x4_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[4x4_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[4x4_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[4x4_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[4x4_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[5x5_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[5x5_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[5x5_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[5x5_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_real_game_engine_full_reveal_with_reference_sat_and_checker[5x5_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[3x3_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[3x3_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[3x3_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[3x3_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[3x3_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[4x4_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[4x4_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[4x4_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[4x4_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[4x4_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[5x5_01]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[5x5_02]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[5x5_03]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[5x5_04]` | PASSED |
| `tests.test_puzzles_multiclue::test_uniqueness_block_contains_primary_variables_only[5x5_05]` | PASSED |
| `tests.test_puzzles_multiclue::test_invalid_initial_reveal_is_rejected[initial0]` | PASSED |
| `tests.test_puzzles_multiclue::test_invalid_initial_reveal_is_rejected[initial1]` | PASSED |
| `tests.test_puzzles_multiclue::test_invalid_initial_reveal_is_rejected[initial2]` | PASSED |
| `tests.test_puzzles_multiclue::test_new_count_clues_are_not_tautological_or_singleton` | PASSED |
| `tests.test_puzzles_multiclue::test_preview_embeds_actual_fifteen_maps_and_both_versions` | PASSED |
| `tests.test_puzzles_multiclue::test_public_reasoning_does_not_consult_private_key_for_decisions` | PASSED |
| `tests.test_puzzles_multiclue::test_publication_io_error_restores_original_files` | PASSED |
| `tests.test_variable_map.VariableMapTests::test_assigned_module_paths_reuse_the_canonical_contract` | PASSED |
| `tests.test_variable_map.VariableMapTests::test_bulk_registration_is_deterministic_by_display_name` | PASSED |
| `tests.test_variable_map.VariableMapTests::test_cnf_contract` | PASSED |
| `tests.test_variable_map.VariableMapTests::test_duplicate_and_invalid_registration_are_rejected` | PASSED |
| `tests.test_variable_map.VariableMapTests::test_freeze_and_auxiliary_variable_lifecycle` | PASSED |
| `tests.test_variable_map.VariableMapTests::test_literals_follow_criminal_innocent_convention` | PASSED |
