# Reconstruct analysis inputs from frozen public source data.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L) stop("Usage: Rscript upstream/build_empirical_inputs.R <source-dir> <work-dir> <output-dir> <dataset>")
script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
package <- normalizePath(file.path(dirname(script), ".."))
source(file.path(package, "upstream", "processing_config.R"))
source_dir <- normalizePath(args[[1]], mustWork = TRUE)
work_dir <- args[[2]]; out_dir <- args[[3]]; dataset <- args[[4]]
stopifnot(dataset %in% c("nhanes", "crosscheck", "all"))
dir.create(work_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
options(digits = 17)
weighted_quantile <- function(x, w, probs) {
  keep <- is.finite(x) & is.finite(w) & w > 0
  x <- x[keep]; w <- w[keep]
  ord <- order(x); x <- x[ord]; w <- w[ord]
  target <- probs * sum(w)
  cum <- cumsum(w)
  vapply(target, function(z) x[which(cum >= z)[1]], numeric(1))
}

apply_cutpoints <- function(x, cuts) {
  as.integer(cut(x, breaks = c(-Inf, cuts, Inf), labels = FALSE, right = TRUE))
}

safe_z <- function(x) {
  x <- as.numeric(x); s <- stats::sd(x, na.rm = TRUE)
  if (!is.finite(s) || s == 0) return(rep(NA_real_, length(x)))
  (x - mean(x, na.rm = TRUE)) / s
}

parse_mortality <- function(path) {
  utils::read.fwf(
    path, widths = c(6, 8, 1, 1, 3, 1, 1, 21, 3, 3),
    col.names = c("SEQN", "skip", "ELIGSTAT", "MORTSTAT", "UCOD_LEADING", "DIABETES", "HYPERTEN", "skip2", "PERMTH_INT", "PERMTH_EXM"),
    colClasses = c("integer", "NULL", "integer", "integer", "character", "integer", "integer", "NULL", "numeric", "numeric"),
    na.strings = c("", ".")
  )
}

run_formal_nhanes <- function(source_dir, compact_dir, output_dir, config) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  cycles <- list(
    list(label = "2003-2004", suffix = "C", compact = "pax_nci_2003_2004.csv", mort = "NHANES_2003_2004_MORT_2019_PUBLIC.dat"),
    list(label = "2005-2006", suffix = "D", compact = "pax_nci_2005_2006.csv", mort = "NHANES_2005_2006_MORT_2019_PUBLIC.dat")
  )
  joined <- list(); flow <- list()
  for (cy in cycles) {
    base <- file.path(source_dir, "nhanes", cy$label)
    demo <- foreign::read.xport(file.path(base, paste0("DEMO_", cy$suffix, ".xpt")))
    paq <- foreign::read.xport(file.path(base, paste0("PAQ_", cy$suffix, ".xpt")))
    mort <- parse_mortality(file.path(base, cy$mort))
    pax <- utils::read.csv(file.path(compact_dir, cy$compact), stringsAsFactors = FALSE)
    d <- merge(demo, paq[, c("SEQN", "PAQ180", "PAD200", "PAD320")], by = "SEQN", all.x = TRUE, sort = FALSE)
    d <- merge(d, mort, by = "SEQN", all.x = TRUE, sort = FALSE)
    d <- merge(d, pax, by = "SEQN", all.x = TRUE, sort = FALSE)
    d$cycle <- cy$label
    d$analysis_weight <- d$WTMEC2YR / 2
    d$survey_stratum <- paste(cy$label, d$SDMVSTRA, sep = ":")
    d$survey_psu <- paste(cy$label, d$SDMVSTRA, d$SDMVPSU, sep = ":")
    d$C <- paste0(ifelse(d$RIAGENDR == 1, "male", "female"), "_", ifelse(d$RIDAGEYR >= 60, "age60plus", "age18to59"))
    d$T <- ifelse(d$PAQ180 %in% config$nhanes$report_levels, d$PAQ180, NA_integer_)
    for (nm in names(config$nhanes$outcome_months)) {
      h <- config$nhanes$outcome_months[[nm]]
      d[[paste0("Y_", nm)]] <- ifelse(d$MORTSTAT == 1 & d$PERMTH_EXM <= h, 1L,
                                       ifelse(d$PERMTH_EXM >= h, 0L, NA_integer_))
    }
    flow[[cy$label]] <- data.frame(
      cycle = cy$label, demo_rows = nrow(demo), pax_participants = nrow(pax),
      adult_rows = sum(d$RIDAGEYR >= config$nhanes$adult_min_age, na.rm = TRUE),
      valid_accelerometer = sum(d$include == 1, na.rm = TRUE),
      valid_report = sum(!is.na(d$T)),
      primary_complete = sum(d$RIDAGEYR >= config$nhanes$adult_min_age & d$ELIGSTAT == 1 & d$include == 1 &
                               !is.na(d$T) & !is.na(d$Y_primary) & is.finite(d$cpm) & is.finite(d$analysis_weight) & d$analysis_weight > 0,
                             na.rm = TRUE)
    )
    joined[[cy$label]] <- d
  }
  all_names <- Reduce(union, lapply(joined, names))
  joined <- lapply(joined, function(d) {
    missing <- setdiff(all_names, names(d))
    for (nm in missing) d[[nm]] <- NA
    d[, all_names, drop = FALSE]
  })
  all <- do.call(rbind, joined)
  base_keep <- with(all, RIDAGEYR >= config$nhanes$adult_min_age & ELIGSTAT == 1 & include == 1 & !is.na(T) &
                          !is.na(Y_primary) & is.finite(cpm) & is.finite(analysis_weight) & analysis_weight > 0)
  primary_base <- all[which(base_keep), , drop = FALSE]
  cut_rows <- list()
  for (k in config$nhanes$proxy_bins) {
    cuts <- weighted_quantile(primary_base$cpm, primary_base$analysis_weight, seq_len(k - 1) / k)
    primary_base[[paste0("M", k)]] <- apply_cutpoints(primary_base$cpm, cuts)
    cut_rows[[as.character(k)]] <- data.frame(proxy_bins = k, cut_index = seq_along(cuts), cpm_cutpoint = cuts)
  }
  cut_table <- do.call(rbind, cut_rows)
  utils::write.csv(cut_table, file.path(output_dir, "proxy_cutpoints.csv"), row.names = FALSE)
  utils::write.csv(do.call(rbind, flow), file.path(output_dir, "sample_flow.csv"), row.names = FALSE)

  keep_cols <- c("SEQN", "cycle", "RIDAGEYR", "RIAGENDR", "SDMVSTRA", "SDMVPSU", "PAQ180", "T", "C",
                 "valid_days", "valid_min", "counts", "cpm", "Y_primary", "Y_robustness", "analysis_weight",
                 "survey_stratum", "survey_psu", paste0("M", config$nhanes$proxy_bins))
  utils::write.csv(primary_base[, keep_cols], file.path(output_dir, "nhanes_analysis_table.csv"), row.names = FALSE)

  nhanes <- utils::read.csv(file.path(output_dir, "nhanes_analysis_table.csv"), stringsAsFactors = FALSE)
  result <- data.frame(row_id = seq_len(nrow(nhanes)), cycle = nhanes$cycle,
    age60plus = as.integer(nhanes$RIDAGEYR >= 60), T = nhanes$T, C = nhanes$C,
    Y_primary = nhanes$Y_primary, Y_robustness = nhanes$Y_robustness,
    analysis_weight = nhanes$analysis_weight, survey_stratum = nhanes$survey_stratum,
    survey_psu = nhanes$survey_psu, M2 = nhanes$M2, M3 = nhanes$M3, M4 = nhanes$M4)
  stopifnot(nrow(result) == 6565L, sum(result$Y_primary == 1L) == 903L)
  result
}
run_formal_crosscheck <- function(source_dir, output_dir, config) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  path <- file.path(source_dir, "crosscheck", "crosscheck_daily_data_cleaned_w_sameday.csv")
  raw <- utils::read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
  raw$date <- as.Date(raw$date); raw <- raw[order(raw$study_id, raw$date), , drop = FALSE]
  sensors <- as.data.frame(lapply(raw[config$crosscheck$sensor_fields], safe_z))
  observed <- rowSums(is.finite(as.matrix(sensors)))
  sensor_score <- rowMeans(sensors, na.rm = TRUE); sensor_score[observed < config$crosscheck$min_sensor_fields] <- NA_real_
  quality <- rowMeans(raw[c("quality_activity", "quality_audio", "quality_loc")], na.rm = TRUE)
  people <- split(seq_len(nrow(raw)), raw$study_id)
  pairs <- do.call(rbind, lapply(people, function(idx) {
    if (length(idx) < 2) return(NULL)
    data.frame(study_id = raw$study_id[idx[-length(idx)]], date = raw$date[idx[-length(idx)]],
               gap_days = as.integer(raw$date[idx[-1]] - raw$date[idx[-length(idx)]]),
               current_ema = raw$ema_neg_score[idx[-length(idx)]], next_ema = raw$ema_neg_score[idx[-1]],
               sensor_score = sensor_score[idx[-length(idx)]], quality_score = quality[idx[-length(idx)]])
  }))
  keep <- with(pairs, gap_days >= 1 & gap_days <= config$crosscheck$max_gap_days &
                       complete.cases(current_ema, next_ema, sensor_score, quality_score))
  pairs <- pairs[keep, , drop = FALSE]
  counts <- table(pairs$study_id); pairs$analysis_weight <- 1 / as.numeric(counts[match(pairs$study_id, names(counts))])
  t_cuts <- weighted_quantile(pairs$current_ema, pairs$analysis_weight, c(1/3, 2/3))
  m_cuts <- weighted_quantile(pairs$sensor_score, pairs$analysis_weight, c(1/3, 2/3))
  q_cut <- weighted_quantile(pairs$quality_score, pairs$analysis_weight, 0.5)
  pairs$T <- apply_cutpoints(pairs$current_ema, t_cuts)
  pairs$Y <- apply_cutpoints(pairs$next_ema, t_cuts)
  pairs$M <- apply_cutpoints(pairs$sensor_score, m_cuts)
  pairs$C <- ifelse(pairs$quality_score <= q_cut, "quality_low", "quality_high")
  utils::write.csv(pairs, file.path(output_dir, "crosscheck_analysis_pairs.csv"), row.names = FALSE)
  utils::write.csv(data.frame(variable = c("current_and_next_ema", "sensor_score", "quality_score"),
                              cutpoints = c(paste(t_cuts, collapse = ";"), paste(m_cuts, collapse = ";"), q_cut)),
                   file.path(output_dir, "cutpoints.csv"), row.names = FALSE)
  pairs <- utils::read.csv(file.path(output_dir, "crosscheck_analysis_pairs.csv"), stringsAsFactors = FALSE)
  ids <- unique(pairs$study_id)
  # Labels are arbitrary; row order and cluster membership define the bootstrap.
  labels <- replicate(length(ids), paste(sample(c(letters[1:6], 0:9), 24, replace = TRUE), collapse = ""))
  stopifnot(!anyDuplicated(labels))
  result <- data.frame(row_id = seq_len(nrow(pairs)),
    participant_id = paste0("cluster_", labels[match(pairs$study_id, ids)]),
    analysis_weight = pairs$analysis_weight, T = pairs$T, Y = pairs$Y, M = pairs$M, C = pairs$C)
  stopifnot(nrow(result) == 5607L, length(unique(result$participant_id)) == 60L)
  result
}

if (dataset %in% c("nhanes", "all")) {
  build <- file.path(work_dir, "build")
  compact <- file.path(work_dir, "pax_compact")
  dir.create(build, recursive = TRUE, showWarnings = FALSE)
  dir.create(compact, recursive = TRUE, showWarnings = FALSE)
  file.copy(file.path(package, "upstream", "pax_nci_aggregate.c"), build, overwrite = TRUE)
  old <- setwd(build)
  status <- system2(file.path(R.home("bin"), "R"), c("CMD", "SHLIB", "pax_nci_aggregate.c"))
  setwd(old)
  if (status != 0L) stop("C kernel compilation failed")
  dyn.load(file.path(build, paste0("pax_nci_aggregate", .Platform$dynlib.ext)))
  cfg <- with(formal_config$processing, as.integer(c(valid_days, nonwear_window,
    nonwear_tol, nonwear_tol_upper, weartime_minimum, artifact_threshold)))
  for (cy in list(c("2003-2004", "C", "2003_2004"), c("2005-2006", "D", "2005_2006"))) {
    message("Processing minute records: ", cy[1])
    raw <- foreign::read.xport(file.path(source_dir, "nhanes", cy[1], paste0("PAXRAW_", cy[2], ".xpt")))
    stopifnot(all(c("SEQN", "PAXSTAT", "PAXCAL", "PAXDAY", "PAXINTEN") %in% names(raw)))
    table <- as.data.frame(.Call("aggregate_pax_nci", raw$SEQN, raw$PAXSTAT, raw$PAXCAL,
      raw$PAXDAY, raw$PAXINTEN, cfg))
    table$cycle <- cy[1]; table$processing_version <- formal_config$protocol_version
    utils::write.csv(table, file.path(compact, paste0("pax_nci_", cy[3], ".csv")), row.names = FALSE, na = "")
    rm(raw, table); invisible(gc())
  }
  result <- run_formal_nhanes(source_dir, compact, file.path(work_dir, "nhanes"), formal_config)
  utils::write.csv(result, file.path(out_dir, "nhanes_analysis_public.csv"), row.names = FALSE)
}
if (dataset %in% c("crosscheck", "all")) {
  result <- run_formal_crosscheck(source_dir, file.path(work_dir, "crosscheck"), formal_config)
  utils::write.csv(result, file.path(out_dir, "crosscheck_pairs_public.csv"), row.names = FALSE)
}
cat("UPSTREAM_EMPIRICAL_BUILD=PASS\n")
