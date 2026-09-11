entropy_bits <- function(p) {
  p <- p[is.finite(p) & p > 0]
  if (!length(p)) return(0)
  -sum(p * log2(p))
}

make_collection <- function(y, m, t, strata, weights, dims, strata_levels = NULL) {
  keep <- complete.cases(y, m, t, strata, weights) & weights > 0
  y <- as.integer(y[keep]); m <- as.integer(m[keep]); t <- as.integer(t[keep])
  strata <- as.character(strata[keep]); weights <- as.numeric(weights[keep])
  if (is.null(strata_levels)) strata_levels <- sort(unique(strata))
  totals <- vapply(strata_levels, function(s) sum(weights[strata == s]), numeric(1))
  if (any(totals <= 0)) stop("A required context stratum has zero weight")
  tensors <- setNames(vector("list", length(strata_levels)), strata_levels)
  for (s in strata_levels) {
    idx <- which(strata == s)
    a <- array(0, dim = dims)
    for (i in idx) a[y[i], m[i], t[i]] <- a[y[i], m[i], t[i]] + weights[i]
    tensors[[s]] <- a / sum(a)
  }
  list(tensors = tensors, weights = totals / sum(totals), dims = dims, strata = strata_levels)
}

conditional_entropy_y_t <- function(p) {
  p_yt <- apply(p, c(1, 3), sum); p_t <- colSums(p_yt); out <- 0
  for (tt in seq_len(dim(p)[3])) if (p_t[tt] > 0) {
    out <- out + p_t[tt] * entropy_bits(p_yt[, tt] / p_t[tt])
  }
  out
}

cmi_one <- function(p) {
  out <- 0; p_t <- apply(p, 3, sum)
  for (tt in seq_len(dim(p)[3])) if (p_t[tt] > 0) {
    joint <- p[, , tt] / p_t[tt]; py <- rowSums(joint); pm <- colSums(joint)
    for (yy in seq_len(dim(p)[1])) for (mm in seq_len(dim(p)[2])) {
      q <- joint[yy, mm]
      if (q > 0 && py[yy] > 0 && pm[mm] > 0) {
        out <- out + p_t[tt] * q * log2(q / (py[yy] * pm[mm]))
      }
    }
  }
  max(0, out)
}

observable_witness <- function(collection) {
  sum(vapply(names(collection$tensors), function(s) {
    collection$weights[s] * cmi_one(collection$tensors[[s]])
  }, numeric(1)))
}

floor_entropy <- function(n, floor) {
  if (floor == 0) return(0)
  entropy_bits(c(1 - (n - 1) * floor, rep(floor, n - 1)))
}

canonical_tensor <- function(p, alpha, eta, delta) {
  d <- dim(p); L <- d[1]; J <- d[2]; G <- d[3]
  p_mt <- apply(p, c(2, 3), sum); p_yt <- apply(p, c(1, 3), sum)
  p_ym <- apply(p, c(1, 2), sum); p_t <- apply(p, 3, sum)
  p_m <- apply(p, 2, sum); p_y <- apply(p, 1, sum)
  out <- array(0, dim = d)
  denom <- (1 - L * alpha) * (1 - J * eta) * (1 - G * delta)
  for (yy in seq_len(L)) for (mm in seq_len(J)) for (tt in seq_len(G)) {
    out[yy, mm, tt] <- (
      p[yy, mm, tt] - alpha * p_mt[mm, tt] - eta * p_yt[yy, tt] - delta * p_ym[yy, mm] +
        alpha * eta * p_t[tt] + alpha * delta * p_m[mm] + eta * delta * p_y[yy] -
        alpha * eta * delta
    ) / denom
  }
  out
}

lower_endpoint_one <- function(p, eta, delta, tolerance) {
  d <- dim(p); L <- d[1]; J <- d[2]; G <- d[3]
  p_yt <- apply(p, c(1, 3), sum); p_ym <- apply(p, c(1, 2), sum); p_y <- apply(p, 1, sum)
  z <- array(0, dim = d); denom <- (1 - J * eta) * (1 - G * delta)
  for (yy in seq_len(L)) for (mm in seq_len(J)) for (tt in seq_len(G)) {
    z[yy, mm, tt] <- (p[yy, mm, tt] - eta * p_yt[yy, tt] - delta * p_ym[yy, mm] + eta * delta * p_y[yy]) / denom
  }
  z[abs(z) <= tolerance] <- 0
  if (any(z < -tolerance)) return(NA_real_)
  z <- pmax(z, 0); cond <- 0
  for (mm in seq_len(J)) for (tt in seq_len(G)) {
    column <- z[, mm, tt]; mass <- sum(column)
    if (mass > tolerance) cond <- cond + mass * entropy_bits(column / mass)
  }
  conditional_entropy_y_t(p) - cond
}

sharp_metrics <- function(collection, alpha, eta, delta, tolerance = 1e-10) {
  d <- collection$dims; witness <- observable_witness(collection); hy <- 0; lower <- 0
  min_coord <- Inf; negatives <- 0L; compatible <- TRUE
  for (s in names(collection$tensors)) {
    p <- collection$tensors[[s]]; w <- collection$weights[s]
    can <- canonical_tensor(p, alpha, eta, delta)
    min_coord <- min(min_coord, min(can)); negatives <- negatives + sum(can < -tolerance)
    ok <- min(can) >= -tolerance; compatible <- compatible && ok
    hy <- hy + w * conditional_entropy_y_t(p)
    if (ok) lower <- lower + w * lower_endpoint_one(p, eta, delta, tolerance)
  }
  upper <- hy - floor_entropy(d[1], alpha)
  if (!compatible) { lower <- NA_real_; upper <- NA_real_ }
  data.frame(
    alpha = alpha, eta = eta, delta = delta, compatible = compatible,
    minimum_canonical_coordinate = min_coord, negative_coordinate_count = negatives,
    observable_witness_bits = witness, conditional_entropy_y_given_t_c_bits = hy,
    sharp_lower_bits = lower, sharp_upper_bits = upper,
    lower_minus_witness_bits = if (is.finite(lower)) lower - witness else NA_real_
  )
}

delta_max_one <- function(p, alpha, eta, tolerance = 1e-10) {
  d <- dim(p); G <- d[3]
  p_mt <- apply(p, c(2, 3), sum); p_yt <- apply(p, c(1, 3), sum)
  p_ym <- apply(p, c(1, 2), sum); p_t <- apply(p, 3, sum)
  p_m <- apply(p, 2, sum); p_y <- apply(p, 1, sum)
  cap <- 1 / G - .Machine$double.eps; base_ok <- TRUE
  for (yy in seq_len(d[1])) for (mm in seq_len(d[2])) for (tt in seq_len(G)) {
    intercept <- p[yy, mm, tt] - alpha * p_mt[mm, tt] - eta * p_yt[yy, tt] + alpha * eta * p_t[tt]
    slope <- -p_ym[yy, mm] + alpha * p_m[mm] + eta * p_y[yy] - alpha * eta
    if (intercept < -tolerance) base_ok <- FALSE
    if (slope < -tolerance) cap <- min(cap, intercept / (-slope))
  }
  c(delta_max = max(0, cap), base_compatible = base_ok)
}

delta_max_collection <- function(collection, alpha, eta, tolerance = 1e-10) {
  vals <- lapply(collection$tensors, delta_max_one, alpha = alpha, eta = eta, tolerance = tolerance)
  ok <- all(vapply(vals, function(x) as.logical(x["base_compatible"]), logical(1)))
  data.frame(alpha = alpha, eta = eta, compatible_at_delta_zero = ok,
             delta_max = if (ok) min(vapply(vals, function(x) x["delta_max"], numeric(1))) else NA_real_)
}

grid_rows <- function(collection, cfg) {
  grid <- expand.grid(alpha = cfg$alpha_values, eta = cfg$eta_values, delta = cfg$delta_values)
  do.call(rbind, lapply(seq_len(nrow(grid)), function(i) {
    sharp_metrics(collection, grid$alpha[i], grid$eta[i], grid$delta[i], cfg$compatibility_tolerance)
  }))
}

delta_grid_rows <- function(collection, cfg) {
  grid <- expand.grid(alpha = cfg$alpha_values, eta = cfg$eta_values)
  do.call(rbind, lapply(seq_len(nrow(grid)), function(i) {
    delta_max_collection(collection, grid$alpha[i], grid$eta[i], cfg$compatibility_tolerance)
  }))
}

basic_interval <- function(point, draws, level = 0.95) {
  draws <- draws[is.finite(draws)]
  if (!length(draws) || !is.finite(point)) return(c(lower = NA_real_, upper = NA_real_))
  a <- (1 - level) / 2
  q <- stats::quantile(draws, c(1 - a, a), names = FALSE, na.rm = TRUE)
  c(lower = 2 * point - q[1], upper = 2 * point - q[2])
}

conditional_permutation <- function(data, m_col, group_cols, statistic, reps, seed) {
  set.seed(seed); observed <- statistic(data)
  groups <- interaction(data[group_cols], drop = TRUE, lex.order = TRUE)
  draws <- numeric(reps)
  for (b in seq_len(reps)) {
    d <- data
    d[[m_col]] <- unsplit(lapply(split(data[[m_col]], groups), function(x) {
      if (length(x) > 1L) sample(x, length(x), replace = FALSE) else x
    }), groups)
    draws[b] <- statistic(d)
  }
  list(observed = observed, draws = draws, p_value = (1 + sum(draws >= observed)) / (reps + 1))
}

nhanes_boot_weights <- function(data) {
  multiplier <- numeric(nrow(data))
  for (s in unique(data$survey_stratum)) {
    idx <- which(data$survey_stratum == s); psus <- unique(data$survey_psu[idx])
    sampled <- sample(psus, length(psus), replace = TRUE); counts <- table(sampled)
    local <- as.numeric(counts[match(data$survey_psu[idx], names(counts))]); local[is.na(local)] <- 0
    multiplier[idx] <- local
  }
  data$analysis_weight * multiplier
}

participant_boot_weights <- function(data) {
  ids <- unique(data$study_id); sampled <- sample(ids, length(ids), replace = TRUE); mult <- table(sampled)
  data$analysis_weight * as.numeric(mult[match(data$study_id, names(mult))])
}
