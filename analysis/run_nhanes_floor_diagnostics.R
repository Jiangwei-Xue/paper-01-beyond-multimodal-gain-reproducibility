args <- commandArgs(trailingOnly = TRUE)
Sys.setenv(TZ = "UTC")
root <- normalizePath(if (length(args) >= 1L) args[[1]] else ".", mustWork = TRUE)
out_root <- if (length(args) >= 2L) args[[2]] else file.path(root, "rerun_results", "floor_diagnostics")
source(file.path(root, "analysis", "empirical_common.R"))
source(file.path(root, "config", "nhanes_crosscheck_reproduction.R"))
cfg <- empirical_config
d <- utils::read.csv(file.path(root, "input_data", "nhanes_analysis_public.csv"), stringsAsFactors = FALSE)
stopifnot(nrow(d) == 6565L, sum(d$Y_primary == 1L) == 903L)

# Canonical boundary-safe compatibility screen.
boundary_dir <- file.path(out_root, "canonical_boundary")
dir.create(boundary_dir, recursive = TRUE, showWarnings = FALSE)
strata_levels <- sort(unique(d$C))
collection <- make_collection(
  d$Y_primary + 1L, d$M4, d$T, d$C, d$analysis_weight,
  dims = c(2L, 4L, 4L), strata_levels = strata_levels
)
D <- prod(collection$dims)
beta_each <- (1 - cfg$confidence_level) / length(strata_levels)
radii <- do.call(rbind, lapply(strata_levels, function(s) {
  z <- d[d$C == s, , drop = FALSE]
  cluster_mass <- tapply(z$analysis_weight, z$survey_psu, sum)
  a <- as.numeric(cluster_mass / sum(cluster_mass))
  eps <- sqrt(2 * sum(a^2) * (D * log(2) + log(1 / beta_each)))
  data.frame(
    context_stratum = s, psu_clusters = length(a), effective_psu_count = 1 / sum(a^2),
    simultaneous_l1_radius = min(2, eps), raw_radius = eps
  )
}))
canonical_operator <- function(alpha, eta, delta, dims) {
  mat <- matrix(0, prod(dims), prod(dims))
  for (j in seq_len(prod(dims))) {
    basis <- array(0, dim = dims); basis[j] <- 1
    mat[, j] <- as.vector(canonical_tensor(basis, alpha, eta, delta))
  }
  mat
}
grid <- expand.grid(
  alpha = cfg$sharp_id$alpha_values,
  eta = cfg$sharp_id$eta_values,
  delta = cfg$sharp_id$delta_values
)
boundary_rows <- vector("list", nrow(grid))
for (i in seq_len(nrow(grid))) {
  a <- grid$alpha[i]; e <- grid$eta[i]; dd <- grid$delta[i]
  operator <- canonical_operator(a, e, dd, collection$dims)
  lipschitz <- apply(operator, 1, function(v) (max(v) - min(v)) / 2)
  point_list <- lapply(strata_levels, function(s) as.vector(canonical_tensor(collection$tensors[[s]], a, e, dd)))
  upper_list <- Map(function(point, eps) point + lipschitz * eps, point_list, radii$simultaneous_l1_radius)
  lower_list <- Map(function(point, eps) point - lipschitz * eps, point_list, radii$simultaneous_l1_radius)
  point <- unlist(point_list, use.names = FALSE); upper <- unlist(upper_list, use.names = FALSE)
  lower <- unlist(lower_list, use.names = FALSE)
  rejected <- any(upper < 0); certified <- all(lower >= 0)
  boundary_rows[[i]] <- data.frame(
    alpha = a, eta = e, delta = dd,
    point_compatible = all(point >= -cfg$sharp_id$compatibility_tolerance),
    minimum_point_coordinate = min(point), minimum_outer_upper = min(upper),
    minimum_outer_lower = min(lower),
    compatibility_inference = if (rejected) "rejected" else if (certified) "certified_compatible" else "not_rejected",
    rejected = rejected, certified_compatible = certified, canonical_cells = length(point)
  )
}
boundary <- do.call(rbind, boundary_rows)
diagonal <- boundary[boundary$alpha == boundary$eta & boundary$eta == boundary$delta, ]
utils::write.csv(boundary, file.path(boundary_dir, "canonical_compatibility_region.csv"), row.names = FALSE)
utils::write.csv(diagonal, file.path(boundary_dir, "canonical_compatibility_diagonal.csv"), row.names = FALSE)
utils::write.csv(radii, file.path(boundary_dir, "context_l1_radii.csv"), row.names = FALSE)
utils::write.csv(data.frame(
  protocol_version = cfg$protocol_version,
  analysis = "boundary-safe conservative PSU-block l1 compatibility screen",
  confidence_level = cfg$confidence_level,
  canonical_design = "10-year mortality; 4 CPM bins; 4 PAQ180 levels; sex-by-age context",
  interpretation = paste(
    "not_rejected means the conservative outer screen cannot reject the restriction;",
    "it is not scientific calibration and does not make an incompatible plug-in sharp endpoint estimable"
  ),
  assumption = "independent PSU blocks with observed normalized PSU masses treated as fixed"
), file.path(boundary_dir, "protocol_record.csv"), row.names = FALSE)

# Post-canonical representation sensitivity. These designs change the estimand.
positive_dir <- file.path(out_root, "positive_floor_sensitivity")
dir.create(positive_dir, recursive = TRUE, showWarnings = FALSE)
pcfg <- cfg$positive_floor
designs <- list(
  list(id = "C1_M2_T4", description = "Four-level PAQ report, two-bin accelerometer proxy, no context stratification", t = 4L, m = 2L),
  list(id = "age2_M2_T4", description = "Four-level PAQ report, two-bin accelerometer proxy, age-group context", t = 4L, m = 2L),
  list(id = "C4_M2_T2", description = "Two-level PAQ report, two-bin accelerometer proxy, sex-by-age context", t = 2L, m = 2L)
)
make_design_data <- function(design_id, data = d) {
  z <- data
  if (design_id == "C1_M2_T4") {
    z$T_sensitivity <- z$T; z$C_sensitivity <- "all"
  } else if (design_id == "age2_M2_T4") {
    z$T_sensitivity <- z$T
    z$C_sensitivity <- ifelse(z$age60plus == 1L, "age60plus", "age18to59")
  } else if (design_id == "C4_M2_T2") {
    z$T_sensitivity <- ifelse(z$T <= 2L, 1L, 2L); z$C_sensitivity <- z$C
  } else stop("Unknown design")
  z$M_sensitivity <- z$M2; z
}
grid_cfg <- list(
  alpha_values = pcfg$floor_values, eta_values = pcfg$floor_values,
  delta_values = pcfg$floor_values, compatibility_tolerance = cfg$sharp_id$compatibility_tolerance
)
set.seed(pcfg$seed)
boot_weights <- lapply(seq_len(pcfg$bootstrap_replicates), function(i) nhanes_boot_weights(d))
summary_rows <- list(); grid_rows_all <- list(); compat_rows_all <- list(); delta_rows_all <- list()
for (design in designs) {
  z <- make_design_data(design$id); levels <- sort(unique(z$C_sensitivity)); dims <- c(2L, design$m, design$t)
  make <- function(w) make_collection(
    z$Y_primary + 1L, z$M_sensitivity, z$T_sensitivity, z$C_sensitivity, w,
    dims = dims, strata_levels = levels
  )
  point_collection <- make(z$analysis_weight); point <- observable_witness(point_collection)
  witness_draws <- vapply(boot_weights, function(w) observable_witness(make(w)), numeric(1))
  witness_ci <- basic_interval(point, witness_draws, cfg$confidence_level)
  summary_rows[[design$id]] <- data.frame(
    design_id = design$id, description = design$description, n = nrow(z), deaths = sum(z$Y_primary == 1L),
    report_levels = design$t, proxy_bins = design$m, context_strata = length(levels),
    plugin_witness_bits = point,
    bootstrap_bias_corrected_bits = max(0, 2 * point - mean(witness_draws)),
    ci_lower = witness_ci[["lower"]], ci_upper = witness_ci[["upper"]],
    bootstrap_replicates = length(witness_draws), stringsAsFactors = FALSE
  )
  pg <- grid_rows(point_collection, grid_cfg); pd <- delta_grid_rows(point_collection, grid_cfg)
  G <- nrow(pg); DG <- nrow(pd)
  min_draw <- matrix(NA_real_, pcfg$bootstrap_replicates, G)
  compat_draw <- matrix(FALSE, pcfg$bootstrap_replicates, G)
  dmax_draw <- matrix(NA_real_, pcfg$bootstrap_replicates, DG)
  boot_outputs <- parallel::mclapply(seq_len(pcfg$bootstrap_replicates), function(b) {
    coll <- make(boot_weights[[b]])
    list(grid = grid_rows(coll, grid_cfg), delta = delta_grid_rows(coll, grid_cfg))
  }, mc.cores = min(pcfg$parallel_cores, parallel::detectCores()), mc.preschedule = TRUE)
  for (b in seq_len(pcfg$bootstrap_replicates)) {
    bg <- boot_outputs[[b]]$grid; bd <- boot_outputs[[b]]$delta
    min_draw[b, ] <- bg$minimum_canonical_coordinate; compat_draw[b, ] <- bg$compatible
    dmax_draw[b, ] <- bd$delta_max
  }
  comp <- pg[, c("alpha", "eta", "delta", "compatible", "minimum_canonical_coordinate")]
  comp$bootstrap_compatibility_fraction <- colMeans(compat_draw)
  ints <- t(vapply(seq_len(G), function(i) basic_interval(pg$minimum_canonical_coordinate[i], min_draw[, i], cfg$confidence_level), numeric(2)))
  comp$minimum_coordinate_ci_lower <- ints[, 1]; comp$minimum_coordinate_ci_upper <- ints[, 2]
  comp$compatibility_inference <- ifelse(comp$minimum_coordinate_ci_lower >= 0, "certified_compatible",
                                          ifelse(comp$minimum_coordinate_ci_upper < 0, "rejected", "indeterminate"))
  pd$bootstrap_median <- apply(dmax_draw, 2, stats::median, na.rm = TRUE)
  dints <- t(vapply(seq_len(DG), function(i) basic_interval(pd$delta_max[i], dmax_draw[, i], cfg$confidence_level), numeric(2)))
  pd$ci_lower <- dints[, 1]; pd$ci_upper <- dints[, 2]
  pg$design_id <- design$id; comp$design_id <- design$id; pd$design_id <- design$id
  grid_rows_all[[design$id]] <- pg; compat_rows_all[[design$id]] <- comp; delta_rows_all[[design$id]] <- pd
}
summary_table <- do.call(rbind, summary_rows); sharp_table <- do.call(rbind, grid_rows_all)
compat_table <- do.call(rbind, compat_rows_all); delta_table <- do.call(rbind, delta_rows_all)
selected_values <- c(0, 0.0025, 0.005, 0.01)
select_diagonal <- function(sharp, comp) {
  keep <- sharp$alpha == sharp$eta & sharp$eta == sharp$delta & sharp$alpha %in% selected_values
  x <- sharp[keep, c("design_id", "alpha", "eta", "delta", "compatible", "observable_witness_bits", "sharp_lower_bits", "sharp_upper_bits")]
  y <- comp[keep, c("minimum_coordinate_ci_lower", "minimum_coordinate_ci_upper", "compatibility_inference")]
  cbind(x, y)
}
canonical_sharp <- grid_rows(collection, cfg$sharp_id); canonical_sharp$design_id <- "canonical_C4_M4_T4"
canonical_comp <- canonical_sharp[, c("alpha", "eta", "delta", "compatible", "minimum_canonical_coordinate")]
canonical_comp$minimum_coordinate_ci_lower <- NA_real_; canonical_comp$minimum_coordinate_ci_upper <- NA_real_
canonical_comp$compatibility_inference <- ifelse(canonical_comp$compatible, "plug_in_compatible", "plug_in_incompatible")
selected <- rbind(select_diagonal(canonical_sharp, canonical_comp), select_diagonal(sharp_table, compat_table))
selected$common_floor <- selected$alpha
paper_key <- paste(
  c("C1_M2_T4", "C1_M2_T4", "age2_M2_T4", "C4_M2_T2", "C4_M2_T2"),
  c(0.005, 0.01, 0.005, 0.005, 0.01), sep = "::"
)
selected_key <- paste(selected$design_id, selected$common_floor, sep = "::")
paper_selected <- selected[match(paper_key, selected_key), , drop = FALSE]
paper_selected <- data.frame(
  representation = paper_selected$design_id,
  common_floor = paper_selected$common_floor,
  point_compatible = paper_selected$compatible,
  min_coordinate_ci_lower = paper_selected$minimum_coordinate_ci_lower,
  min_coordinate_ci_upper = paper_selected$minimum_coordinate_ci_upper,
  sharp_lower_bits = paper_selected$sharp_lower_bits,
  sharp_upper_bits = paper_selected$sharp_upper_bits,
  status = "post_canonical_exploratory",
  stringsAsFactors = FALSE
)
cycle_rows <- list(); cycle_index <- 1L
for (cycle_label in sort(unique(d$cycle))) for (design in designs) {
  z <- make_design_data(design$id, d[d$cycle == cycle_label, , drop = FALSE])
  coll <- make_collection(
    z$Y_primary + 1L, z$M_sensitivity, z$T_sensitivity, z$C_sensitivity, z$analysis_weight,
    dims = c(2L, design$m, design$t), strata_levels = sort(unique(z$C_sensitivity))
  )
  for (floor in selected_values) {
    metrics <- sharp_metrics(coll, floor, floor, floor, cfg$sharp_id$compatibility_tolerance)
    cycle_rows[[cycle_index]] <- data.frame(
      cycle = cycle_label, design_id = design$id, n = nrow(z), deaths = sum(z$Y_primary == 1L),
      common_floor = floor, compatible = metrics$compatible,
      minimum_canonical_coordinate = metrics$minimum_canonical_coordinate,
      observable_witness_bits = metrics$observable_witness_bits,
      sharp_lower_bits = metrics$sharp_lower_bits, sharp_upper_bits = metrics$sharp_upper_bits
    )
    cycle_index <- cycle_index + 1L
  }
}
utils::write.csv(summary_table, file.path(positive_dir, "representation_summary.csv"), row.names = FALSE)
utils::write.csv(sharp_table, file.path(positive_dir, "sharp_sensitivity.csv"), row.names = FALSE)
utils::write.csv(compat_table, file.path(positive_dir, "compatibility_bootstrap.csv"), row.names = FALSE)
utils::write.csv(delta_table, file.path(positive_dir, "delta_max.csv"), row.names = FALSE)
utils::write.csv(selected, file.path(positive_dir, "selected_diagonal_floor_table.csv"), row.names = FALSE)
utils::write.csv(paper_selected, file.path(positive_dir, "paper_selected_floor_rows.csv"), row.names = FALSE)
utils::write.csv(do.call(rbind, cycle_rows), file.path(positive_dir, "cycle_point_diagnostics.csv"), row.names = FALSE)
utils::write.csv(data.frame(
  protocol_version = pcfg$protocol_version, freeze_date = "2026-09-05",
  status = "post-canonical exploratory sensitivity analysis",
  boundary = paste(
    "These representations were specified after inspecting the canonical sparse-cell result.",
    "They diagnose representation sensitivity and do not replace the frozen 4M x 4T x 4C primary analysis.",
    "No pseudocount or probability smoothing is used."
  ), seed = pcfg$seed, bootstrap_replicates = pcfg$bootstrap_replicates
), file.path(positive_dir, "protocol_record.csv"), row.names = FALSE)
writeLines(c(
  paste0("r_version=", paste(R.version$major, R.version$minor, sep = ".")),
  "reproduction_timezone=UTC",
  "external_packages=none"
), file.path(out_root, "environment.txt"))
cat("NHANES_FLOOR_DIAGNOSTICS_STATUS=PASS\n")
