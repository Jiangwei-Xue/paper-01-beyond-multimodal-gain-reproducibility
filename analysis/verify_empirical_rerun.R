args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L) stop("Usage: Rscript analysis/verify_empirical_rerun.R <reference-dir> <candidate-dir>")
reference <- normalizePath(args[[1]], mustWork = TRUE)
candidate <- normalizePath(args[[2]], mustWork = TRUE)

relative_csv <- function(root) {
  paths <- list.files(root, pattern = "\\.csv$", recursive = TRUE, full.names = TRUE)
  rel <- substring(normalizePath(paths, mustWork = TRUE), nchar(root) + 2L)
  sort(rel[basename(rel) != "REPRODUCIBILITY_CHECK.csv"])
}

sha256 <- function(path) {
  line <- system2("shasum", c("-a", "256", shQuote(path)), stdout = TRUE)
  unname(strsplit(line, "  ", fixed = TRUE)[[1]][1])
}

reference_files <- relative_csv(reference)
candidate_files <- relative_csv(candidate)
if (!identical(reference_files, candidate_files)) stop("CSV inventory mismatch")
rows <- lapply(reference_files, function(rel) {
  h1 <- sha256(file.path(reference, rel)); h2 <- sha256(file.path(candidate, rel))
  data.frame(file = rel, reference_sha256 = h1, candidate_sha256 = h2,
             identical = identical(h1, h2), stringsAsFactors = FALSE)
})
report <- do.call(rbind, rows)
utils::write.csv(report, file.path(candidate, "REPRODUCIBILITY_CHECK.csv"), row.names = FALSE)
if (!all(report$identical)) stop("Empirical reproduction hash comparison failed")
cat("EMPIRICAL_REPROCHECK_FILES=", nrow(report), "\n", sep = "")
cat("EMPIRICAL_REPROCHECK_IDENTICAL=PASS\n")
