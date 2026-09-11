#include <R.h>
#include <Rinternals.h>
#include <R_ext/Rdynload.h>
#include <math.h>
#include <stdlib.h>

static double number_at(SEXP x, R_xlen_t i) {
  if (TYPEOF(x) == REALSXP) return REAL(x)[i];
  if (TYPEOF(x) == INTSXP) return INTEGER(x)[i] == NA_INTEGER ? NA_REAL : (double) INTEGER(x)[i];
  error("Expected numeric or integer vector");
  return NA_REAL;
}

static int count_at(SEXP x, R_xlen_t i, int *missing) {
  double value = number_at(x, i);
  if (!R_FINITE(value)) {
    *missing = 1;
    return 0;
  }
  return (int) llround(value);
}

static void correct_artifacts(int *counts, R_xlen_t n, int threshold) {
  int *class_values = (int *) malloc((size_t) n * sizeof(int));
  if (class_values == NULL) error("Unable to allocate artifact buffer");
  for (R_xlen_t i = 0; i < n; ++i) class_values[i] = counts[i];
  for (R_xlen_t i = 0; i < n; ++i) {
    if (class_values[i] < threshold) continue;
    int before = -1;
    int after = -1;
    for (R_xlen_t j = i; j > 0; ) {
      --j;
      if (class_values[j] < threshold) { before = counts[j]; break; }
    }
    for (R_xlen_t j = i + 1; j < n; ++j) {
      if (class_values[j] < threshold) { after = counts[j]; break; }
    }
    if (before >= 0 && after >= 0) {
      int total = before + after;
      counts[i] = (total % 2 == 0) ? total / 2 : (total + 1) / 2;
    } else if (before < 0 && after >= 0) {
      counts[i] = after;
    } else if (after < 0 && before >= 0) {
      counts[i] = before;
    }
  }
  free(class_values);
}

static void nci_weartime_days_distinct(const int *counts, int *wear, R_xlen_t n,
                                       int window, int tolerance, int upper) {
  for (R_xlen_t i = 0; i < n; ++i) wear[i] = 1;
  int zeros = 0;
  int tolcount = 0;
  int flag = 0;
  for (R_xlen_t b = 0; b < n; ++b) {
    int value = counts[b];
    if (zeros == 0 && value != 0) {
      if ((b + 1) % 1440 == 0) { zeros = 0; tolcount = 0; flag = 0; }
      continue;
    }
    if (value == 0) {
      zeros += 1;
      tolcount = 0;
    } else if (value > 0 && value <= upper) {
      zeros += 1;
      tolcount += 1;
    } else {
      zeros += 1;
      tolcount += 1;
      flag = 1;
    }
    if (tolcount > tolerance || flag == 1 || b == n - 1 || (b + 1) % 1440 == 0) {
      if (zeros - tolcount >= window) {
        R_xlen_t first = b - zeros + 1;
        R_xlen_t last_exclusive = b - tolcount + 1;
        for (R_xlen_t c = first; c < last_exclusive; ++c) wear[c] = 0;
      }
      zeros = 0;
      tolcount = 0;
      flag = 0;
    }
  }
}

SEXP aggregate_pax_nci(SEXP seqn, SEXP paxstat, SEXP paxcal, SEXP paxday,
                       SEXP intensity, SEXP config) {
  R_xlen_t n = XLENGTH(seqn);
  if (XLENGTH(paxstat) != n || XLENGTH(paxcal) != n || XLENGTH(paxday) != n || XLENGTH(intensity) != n)
    error("PAX vectors have unequal lengths");
  if (TYPEOF(config) != INTSXP || XLENGTH(config) < 6) error("Invalid integer configuration");
  int valid_days_required = INTEGER(config)[0];
  int window = INTEGER(config)[1];
  int tolerance = INTEGER(config)[2];
  int upper = INTEGER(config)[3];
  int wear_minimum = INTEGER(config)[4];
  int artifact_threshold = INTEGER(config)[5];
  if (n == 0) error("Empty PAX input");

  R_xlen_t people = 1;
  for (R_xlen_t i = 1; i < n; ++i) if (number_at(seqn, i) != number_at(seqn, i - 1)) people++;
  SEXP out = PROTECT(allocMatrix(REALSXP, people, 11));
  double *o = REAL(out);
  for (R_xlen_t i = 0; i < people * 11; ++i) o[i] = NA_REAL;

  R_xlen_t person = 0;
  R_xlen_t start = 0;
  while (start < n) {
    R_xlen_t end = start + 1;
    double id = number_at(seqn, start);
    while (end < n && number_at(seqn, end) == id) end++;
    R_xlen_t minutes = end - start;
    int missing = 0;
    int *counts = (int *) malloc((size_t) minutes * sizeof(int));
    int *wear = (int *) malloc((size_t) minutes * sizeof(int));
    if (counts == NULL || wear == NULL) error("Unable to allocate participant buffer");
    for (R_xlen_t i = 0; i < minutes; ++i) counts[i] = count_at(intensity, start + i, &missing);

    double status = number_at(paxstat, start);
    double calibration = number_at(paxcal, start);
    int reliable = R_FINITE(status) && R_FINITE(calibration) && status <= 1.0 && calibration <= 1.0 && !missing;
    int days = (int) (minutes / 1440);
    int n_valid = 0, n_wk = 0, n_we = 0;
    double total_wear = 0.0, total_counts = 0.0;
    if (reliable && days >= 1) {
      correct_artifacts(counts, minutes, artifact_threshold);
      nci_weartime_days_distinct(counts, wear, minutes, window, tolerance, upper);
      int first_day = (int) llround(number_at(paxday, start));
      for (int d = 0; d < days; ++d) {
        R_xlen_t a = (R_xlen_t) d * 1440;
        R_xlen_t z = a + 1440;
        int day_wear = 0;
        double day_counts = 0.0;
        for (R_xlen_t i = a; i < z; ++i) {
          if (wear[i]) { day_wear += 1; day_counts += counts[i]; }
        }
        if (day_wear >= wear_minimum && day_wear <= 1440) {
          int dow = ((first_day - 1 + d) % 7) + 1;
          n_valid++;
          if (dow == 1 || dow == 7) n_we++; else n_wk++;
          total_wear += day_wear;
          total_counts += day_counts;
        }
      }
    }
    int include = reliable && n_valid >= valid_days_required;
    o[person + people * 0] = id;
    o[person + people * 1] = (double) minutes;
    o[person + people * 2] = (double) n_valid;
    o[person + people * 3] = (double) n_wk;
    o[person + people * 4] = (double) n_we;
    o[person + people * 5] = (double) include;
    o[person + people * 6] = n_valid > 0 ? total_wear / n_valid : NA_REAL;
    o[person + people * 7] = n_valid > 0 ? total_counts / n_valid : NA_REAL;
    o[person + people * 8] = total_wear > 0 ? total_counts / total_wear : NA_REAL;
    o[person + people * 9] = (double) reliable;
    o[person + people * 10] = (double) missing;
    free(counts);
    free(wear);
    person++;
    start = end;
  }

  SEXP names = PROTECT(allocVector(STRSXP, 11));
  const char *labels[] = {"SEQN", "n_minutes", "valid_days", "valid_wk_days", "valid_we_days",
                          "include", "valid_min", "counts", "cpm", "reliable", "missing_intensity"};
  for (int i = 0; i < 11; ++i) SET_STRING_ELT(names, i, mkChar(labels[i]));
  SEXP dimnames = PROTECT(allocVector(VECSXP, 2));
  SET_VECTOR_ELT(dimnames, 1, names);
  setAttrib(out, R_DimNamesSymbol, dimnames);
  UNPROTECT(3);
  return out;
}

static const R_CallMethodDef call_methods[] = {
  {"aggregate_pax_nci", (DL_FUNC) &aggregate_pax_nci, 6},
  {NULL, NULL, 0}
};

void R_init_pax_nci_aggregate(DllInfo *dll) {
  R_registerRoutines(dll, NULL, call_methods, NULL, NULL);
  R_useDynamicSymbols(dll, FALSE);
}
