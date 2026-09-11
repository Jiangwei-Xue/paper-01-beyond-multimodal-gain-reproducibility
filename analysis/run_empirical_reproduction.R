args <- commandArgs(trailingOnly = TRUE)
Sys.setenv(TZ = "UTC")
root <- normalizePath(if (length(args) >= 1L) args[[1]] else ".", mustWork = TRUE)
out_root <- if (length(args) >= 2L) args[[2]] else file.path(root, "rerun_results", "empirical")
source(file.path(root, "analysis", "empirical_common.R"))
source(file.path(root, "config", "nhanes_crosscheck_reproduction.R"))
cfg <- empirical_config
dir.create(out_root, recursive = TRUE, showWarnings = FALSE)

nhanes <- utils::read.csv(file.path(root, "input_data", "nhanes_analysis_public.csv"), stringsAsFactors = FALSE)
stopifnot(nrow(nhanes) == 6565L, sum(nhanes$Y_primary == 1L) == 903L)
nhanes_dir <- file.path(out_root, "nhanes")
dir.create(nhanes_dir, recursive = TRUE, showWarnings = FALSE)

set.seed(cfg$seed)
boot_weights <- lapply(seq_len(cfg$bootstrap_replicates), function(i) nhanes_boot_weights(nhanes))
witness_rows <- list(); boot_rows <- list()
for (hname in cfg$nhanes$outcome_names) for (k in cfg$nhanes$proxy_bins) {
  ycol <- paste0("Y_", hname); mcol <- paste0("M", k)
  d <- nhanes[!is.na(nhanes[[ycol]]), , drop = FALSE]
  bw <- lapply(boot_weights, function(w) w[!is.na(nhanes[[ycol]])])
  strata_levels <- sort(unique(d$C))
  stat <- function(dd, ww) observable_witness(make_collection(
    dd[[ycol]] + 1L, dd[[mcol]], dd$T, dd$C, ww,
    dims = c(2L, k, 4L), strata_levels = strata_levels
  ))
  point <- stat(d, d$analysis_weight)
  draws <- vapply(bw, function(w) stat(d, w), numeric(1))
  ci <- basic_interval(point, draws, cfg$confidence_level)
  perm <- conditional_permutation(
    d, mcol, c("T", "C", "cycle"), function(dd) stat(dd, dd$analysis_weight),
    cfg$permutation_replicates, cfg$seed + as.integer(cfg$nhanes$outcome_months[[hname]]) + k
  )
  key <- paste(hname, k, sep = "_")
  witness_rows[[key]] <- data.frame(
    outcome = hname, months = cfg$nhanes$outcome_months[[hname]], proxy_bins = k,
    n = nrow(d), deaths = sum(d[[ycol]] == 1), survey_weight_sum = sum(d$analysis_weight),
    plugin_witness_bits = point,
    bootstrap_bias_corrected_bits = max(0, 2 * point - mean(draws)),
    ci_lower = ci["lower"], ci_upper = ci["upper"],
    bootstrap_replicates = length(draws), conditional_permutation_p = perm$p_value,
    permutation_replicates = length(perm$draws)
  )
  boot_rows[[key]] <- data.frame(
    outcome = hname, proxy_bins = k, replicate = seq_along(draws), witness_bits = draws
  )
}
utils::write.csv(do.call(rbind, witness_rows), file.path(nhanes_dir, "witness_results.csv"), row.names = FALSE)
utils::write.csv(do.call(rbind, boot_rows), file.path(nhanes_dir, "witness_bootstrap_replicates.csv"), row.names = FALSE)

k <- cfg$nhanes$primary_proxy_bins; strata_levels <- sort(unique(nhanes$C))
make_nhanes <- function(w) make_collection(
  nhanes$Y_primary + 1L, nhanes[[paste0("M", k)]], nhanes$T, nhanes$C, w,
  dims = c(2L, k, 4L), strata_levels = strata_levels
)
point_collection <- make_nhanes(nhanes$analysis_weight)
point_grid <- grid_rows(point_collection, cfg$sharp_id)
point_delta <- delta_grid_rows(point_collection, cfg$sharp_id)
G <- nrow(point_grid); DG <- nrow(point_delta); B <- length(boot_weights)
min_draw <- matrix(NA_real_, B, G); compat_draw <- matrix(FALSE, B, G)
lower_draw <- matrix(NA_real_, B, G); upper_draw <- matrix(NA_real_, B, G)
dmax_draw <- matrix(NA_real_, B, DG)
nhanes_grid_outputs <- parallel::mclapply(seq_len(B), function(b) {
  coll <- make_nhanes(boot_weights[[b]])
  list(grid = grid_rows(coll, cfg$sharp_id), delta = delta_grid_rows(coll, cfg$sharp_id))
}, mc.cores = min(cfg$parallel_cores, parallel::detectCores()), mc.preschedule = TRUE)
for (b in seq_len(B)) {
  bg <- nhanes_grid_outputs[[b]]$grid; bd <- nhanes_grid_outputs[[b]]$delta
  min_draw[b, ] <- bg$minimum_canonical_coordinate; compat_draw[b, ] <- bg$compatible
  lower_draw[b, ] <- bg$sharp_lower_bits; upper_draw[b, ] <- bg$sharp_upper_bits
  dmax_draw[b, ] <- bd$delta_max
}
comp <- point_grid[, c("alpha", "eta", "delta", "compatible", "minimum_canonical_coordinate")]
comp$bootstrap_compatibility_fraction <- colMeans(compat_draw)
intervals <- t(vapply(seq_len(G), function(i) {
  basic_interval(point_grid$minimum_canonical_coordinate[i], min_draw[, i], cfg$confidence_level)
}, numeric(2)))
comp$minimum_coordinate_ci_lower <- intervals[, 1]
comp$minimum_coordinate_ci_upper <- intervals[, 2]
comp$compatibility_inference <- ifelse(
  comp$minimum_coordinate_ci_lower >= 0, "certified_compatible",
  ifelse(comp$minimum_coordinate_ci_upper < 0, "rejected", "indeterminate")
)
point_grid$sharp_lower_boot_median <- apply(lower_draw, 2, stats::median, na.rm = TRUE)
point_grid$sharp_upper_boot_median <- apply(upper_draw, 2, stats::median, na.rm = TRUE)
point_grid$compatible_boot_replicates <- colSums(compat_draw)
point_delta$bootstrap_median <- apply(dmax_draw, 2, stats::median, na.rm = TRUE)
dints <- t(vapply(seq_len(DG), function(i) {
  basic_interval(point_delta$delta_max[i], dmax_draw[, i], cfg$confidence_level)
}, numeric(2)))
point_delta$ci_lower <- dints[, 1]; point_delta$ci_upper <- dints[, 2]
utils::write.csv(point_grid, file.path(nhanes_dir, "sharp_sensitivity.csv"), row.names = FALSE)
utils::write.csv(comp, file.path(nhanes_dir, "compatibility_bootstrap.csv"), row.names = FALSE)
utils::write.csv(point_delta, file.path(nhanes_dir, "delta_max.csv"), row.names = FALSE)

crosscheck <- utils::read.csv(file.path(root, "input_data", "crosscheck_pairs_public.csv"), stringsAsFactors = FALSE)
names(crosscheck)[names(crosscheck) == "participant_id"] <- "study_id"
stopifnot(nrow(crosscheck) == 5607L, length(unique(crosscheck$study_id)) == 60L)
crosscheck_dir <- file.path(out_root, "crosscheck")
dir.create(crosscheck_dir, recursive = TRUE, showWarnings = FALSE)
cross_strata <- sort(unique(crosscheck$C))
cross_stat <- function(w) observable_witness(make_collection(
  crosscheck$Y, crosscheck$M, crosscheck$T, crosscheck$C, w,
  dims = c(3L, 3L, 3L), strata_levels = cross_strata
))
cross_point <- cross_stat(crosscheck$analysis_weight)
set.seed(cfg$seed + 10000L)
cross_bweights <- lapply(seq_len(cfg$bootstrap_replicates), function(i) participant_boot_weights(crosscheck))
cross_draws <- vapply(cross_bweights, cross_stat, numeric(1))
cross_ci <- basic_interval(cross_point, cross_draws, cfg$confidence_level)
cross_perm <- conditional_permutation(
  crosscheck, "M", c("T", "C"),
  function(dd) observable_witness(make_collection(
    dd$Y, dd$M, dd$T, dd$C, dd$analysis_weight,
    dims = c(3L, 3L, 3L), strata_levels = cross_strata
  )), cfg$permutation_replicates, cfg$seed + 20000L
)
cross_result <- data.frame(
  n_pairs = nrow(crosscheck), participants = length(unique(crosscheck$study_id)),
  plugin_witness_bits = cross_point,
  bootstrap_bias_corrected_bits = max(0, 2 * cross_point - mean(cross_draws)),
  ci_lower = cross_ci["lower"], ci_upper = cross_ci["upper"],
  bootstrap_replicates = length(cross_draws), conditional_permutation_p = cross_perm$p_value,
  permutation_replicates = length(cross_perm$draws)
)
utils::write.csv(cross_result, file.path(crosscheck_dir, "witness_results.csv"), row.names = FALSE)
utils::write.csv(data.frame(replicate = seq_along(cross_draws), witness_bits = cross_draws),
                 file.path(crosscheck_dir, "witness_bootstrap_replicates.csv"), row.names = FALSE)

cross_collection <- make_collection(
  crosscheck$Y, crosscheck$M, crosscheck$T, crosscheck$C, crosscheck$analysis_weight,
  dims = c(3L, 3L, 3L), strata_levels = cross_strata
)
cross_grid <- grid_rows(cross_collection, cfg$sharp_id)
cross_delta <- delta_grid_rows(cross_collection, cfg$sharp_id)
B <- length(cross_bweights); G <- nrow(cross_grid); DG <- nrow(cross_delta)
min_draw <- matrix(NA_real_, B, G); compat_draw <- matrix(FALSE, B, G); dmax_draw <- matrix(NA_real_, B, DG)
cross_grid_outputs <- parallel::mclapply(seq_len(B), function(b) {
  coll <- make_collection(
    crosscheck$Y, crosscheck$M, crosscheck$T, crosscheck$C, cross_bweights[[b]],
    dims = c(3L, 3L, 3L), strata_levels = cross_strata
  )
  list(grid = grid_rows(coll, cfg$sharp_id), delta = delta_grid_rows(coll, cfg$sharp_id))
}, mc.cores = min(cfg$parallel_cores, parallel::detectCores()), mc.preschedule = TRUE)
for (b in seq_len(B)) {
  bg <- cross_grid_outputs[[b]]$grid; bd <- cross_grid_outputs[[b]]$delta
  min_draw[b, ] <- bg$minimum_canonical_coordinate; compat_draw[b, ] <- bg$compatible
  dmax_draw[b, ] <- bd$delta_max
}
cross_comp <- cross_grid[, c("alpha", "eta", "delta", "compatible", "minimum_canonical_coordinate")]
cross_comp$bootstrap_compatibility_fraction <- colMeans(compat_draw)
ints <- t(vapply(seq_len(G), function(i) {
  basic_interval(cross_grid$minimum_canonical_coordinate[i], min_draw[, i], cfg$confidence_level)
}, numeric(2)))
cross_comp$minimum_coordinate_ci_lower <- ints[, 1]
cross_comp$minimum_coordinate_ci_upper <- ints[, 2]
cross_comp$compatibility_inference <- ifelse(
  cross_comp$minimum_coordinate_ci_lower >= 0, "certified_compatible",
  ifelse(cross_comp$minimum_coordinate_ci_upper < 0, "rejected", "indeterminate")
)
cross_grid$compatible_boot_replicates <- colSums(compat_draw)
cross_delta$bootstrap_median <- apply(dmax_draw, 2, stats::median, na.rm = TRUE)
dints <- t(vapply(seq_len(DG), function(i) {
  basic_interval(cross_delta$delta_max[i], dmax_draw[, i], cfg$confidence_level)
}, numeric(2)))
cross_delta$ci_lower <- dints[, 1]; cross_delta$ci_upper <- dints[, 2]
utils::write.csv(cross_grid, file.path(crosscheck_dir, "sharp_sensitivity.csv"), row.names = FALSE)
utils::write.csv(cross_comp, file.path(crosscheck_dir, "compatibility_bootstrap.csv"), row.names = FALSE)
utils::write.csv(cross_delta, file.path(crosscheck_dir, "delta_max.csv"), row.names = FALSE)

writeLines(c(
  paste0("r_version=", paste(R.version$major, R.version$minor, sep = ".")),
  "reproduction_timezone=UTC",
  "external_packages=none"
), file.path(out_root, "environment.txt"))
cat("EMPIRICAL_REPRODUCTION_STATUS=PASS\n")
