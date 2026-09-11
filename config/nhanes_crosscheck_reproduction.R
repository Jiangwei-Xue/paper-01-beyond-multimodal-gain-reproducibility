empirical_config <- list(
  protocol_version = "nhanes-crosscheck-formal-v1",
  seed = 2026090501L,
  bootstrap_replicates = 1000L,
  permutation_replicates = 1000L,
  parallel_cores = 10L,
  confidence_level = 0.95,
  nhanes = list(
    proxy_bins = c(2L, 3L, 4L),
    outcome_names = c("primary", "robustness"),
    outcome_months = c(primary = 120L, robustness = 60L),
    primary_proxy_bins = 4L
  ),
  sharp_id = list(
    alpha_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05),
    eta_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05),
    delta_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05),
    compatibility_tolerance = 1e-10
  ),
  positive_floor = list(
    protocol_version = "nhanes-positive-floor-representation-sensitivity-v1",
    seed = 2026090502L,
    bootstrap_replicates = 1000L,
    parallel_cores = 10L,
    floor_values = c(0, 0.0025, 0.005, 0.01, 0.02, 0.05)
  )
)
