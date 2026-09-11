formal_config <- list(
  protocol_version = "nhanes-crosscheck-formal-v1",
  freeze_date = "2026-09-05",
  seed = 2026090501L,
  processing = list(
    method = "NCI-compatible minute-count processing",
    valid_days = 4L,
    valid_wk_days = 0L,
    valid_we_days = 0L,
    days_distinct = TRUE,
    nonwear_window = 60L,
    nonwear_tol = 2L,
    nonwear_tol_upper = 100L,
    weartime_minimum = 600L,
    weartime_maximum = 1440L,
    artifact_threshold = 32767L,
    artifact_action = "replace by rounded mean of nearest non-artifact neighbors",
    cpm_definition = "total counts during wear on valid days divided by total valid wear minutes"
  ),
  nhanes = list(
    adult_min_age = 18L,
    report_variable = "PAQ180",
    report_levels = 1:4,
    outcome_months = c(primary = 120L, robustness = 60L),
    proxy_variable = "cpm",
    proxy_bins = c(2L, 3L, 4L),
    primary_proxy_bins = 4L,
    covariate_strata = "RIAGENDR x I(RIDAGEYR >= 60)",
    pooled_weight = "WTMEC2YR / 2",
    bootstrap_unit = "SDMVPSU within cycle-specific SDMVSTRA",
    bootstrap_replicates = 1000L,
    permutation_replicates = 1000L
  ),
  crosscheck = list(
    max_gap_days = 7L,
    min_sensor_fields = 3L,
    sensor_fields = c(
      "loc_dist_ep_0",
      "audio_convo_duration_ep_0",
      "unlock_duration_ep_0",
      "light_mean_ep_0"
    ),
    report_bins = 3L,
    outcome_bins = 3L,
    proxy_bins = 3L,
    participant_equal_weight = TRUE,
    bootstrap_unit = "study_id",
    bootstrap_replicates = 1000L,
    permutation_replicates = 1000L
  ),
  sharp_id = list(
    alpha_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05),
    eta_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05),
    delta_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05),
    compatibility_tolerance = 1e-10,
    confidence_level = 0.95
  )
)
