args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) stop("Usage: Rscript upstream/test_pax_kernel.R <work-dir>")
script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
build <- normalizePath(args[1], mustWork = FALSE)
dir.create(build, recursive = TRUE, showWarnings = FALSE)
file.copy(file.path(dirname(script), "pax_nci_aggregate.c"), build, overwrite = TRUE)
setwd(build)
status <- system2(file.path(R.home("bin"), "R"), c("CMD", "SHLIB", "pax_nci_aggregate.c"))
stopifnot(status == 0)
dyn.load(paste0("pax_nci_aggregate", .Platform$dynlib.ext))
artifact_reference <- function(x, threshold = 32767L) {
  original <- x
  for (i in seq_along(x)) if (original[i] >= threshold) {
    before <- if (i > 1L) tail(x[seq_len(i - 1L)][original[seq_len(i - 1L)] < threshold], 1L) else integer()
    after <- if (i < length(x)) head(x[(i + 1L):length(x)][original[(i + 1L):length(x)] < threshold], 1L) else integer()
    if (length(before) && length(after)) x[i] <- ceiling((before + after) / 2)
    else if (length(before)) x[i] <- before
    else if (length(after)) x[i] <- after
  }
  x
}

wear_reference <- function(x, window = 60L, tol = 2L, upper = 100L) {
  out <- rep.int(1L, length(x)); zeros <- 0L; tolcount <- 0L; flag <- 0L
  for (b in seq_along(x)) {
    value <- x[b]
    if (zeros == 0L && value != 0L) next
    if (value == 0L) { zeros <- zeros + 1L; tolcount <- 0L
    } else if (value <= upper) { zeros <- zeros + 1L; tolcount <- tolcount + 1L
    } else { zeros <- zeros + 1L; tolcount <- tolcount + 1L; flag <- 1L }
    if (tolcount > tol || flag == 1L || b == length(x) || b %% 1440L == 0L) {
      if (zeros - tolcount >= window) {
        first <- b - zeros + 1L; last <- b - tolcount
        if (last >= first) out[first:last] <- 0L
      }
      zeros <- 0L; tolcount <- 0L; flag <- 0L
    }
  }
  out
}

set.seed(104729)
counts <- sample(c(rep(0L, 7), 1:300), 2880L, replace = TRUE)
counts[101:170] <- 0L
counts[c(130, 150)] <- 50L
counts[500] <- 40000L
counts[1600:1670] <- 0L
corrected <- artifact_reference(counts)
wear <- wear_reference(corrected)
expected_wear <- c(sum(wear[1:1440]), sum(wear[1441:2880]))
expected_counts <- c(sum(corrected[1:1440] * wear[1:1440]), sum(corrected[1441:2880] * wear[1441:2880]))

res <- .Call(
  "aggregate_pax_nci",
  rep(1, length(counts)), rep(1, length(counts)), rep(1, length(counts)),
  c(rep(2, 1440), rep(3, 1440)), counts,
  as.integer(c(1, 60, 2, 100, 600, 32767))
)
print(res)
cat("EXPECTED_WEAR=", paste(expected_wear, collapse = ","), "\n", sep = "")
cat("EXPECTED_COUNTS=", paste(expected_counts, collapse = ","), "\n", sep = "")
stopifnot(res[1, "valid_days"] == 2)
stopifnot(isTRUE(all.equal(unname(res[1, "valid_min"]), mean(expected_wear))))
stopifnot(isTRUE(all.equal(unname(res[1, "counts"]), mean(expected_counts))))
stopifnot(isTRUE(all.equal(unname(res[1, "cpm"]), sum(expected_counts) / sum(expected_wear))))

cat("PAX_KERNEL_SYNTHETIC_SMOKE=PASS\n")
cat("VALID_DAYS=", res[1, "valid_days"], "\n", sep = "")
cat("CPM=", format(res[1, "cpm"], digits = 15), "\n", sep = "")
