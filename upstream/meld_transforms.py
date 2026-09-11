"Train-only transforms used in the frozen MELD input construction."
from __future__ import annotations
import csv
import hashlib
from pathlib import Path
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


MAJOR_SPEAKERS = {"Rachel", "Ross", "Joey", "Monica", "Chandler", "Phoebe"}
SENTIMENT_INDEX = {"negative": 0, "neutral": 1, "positive": 2}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_sentiment_map(path: Path) -> dict[str, str]:
    result = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = f"{int(row['Dialogue_ID'])}_{int(row['Utterance_ID'])}"
            sentiment = row.get("Sentiment", "").strip().lower()
            if sentiment not in SENTIMENT_INDEX:
                raise ValueError(f"Unexpected Sentiment={sentiment!r} for {key}")
            result[key] = sentiment
    return result


def fit_clusterers(train: dict[str, np.ndarray], seed: int, text_k: int, proxy_k: int,
                   text_svd: int, audio_pca: int, visual_pca: int):
    text_pipe = make_pipeline(
        TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), min_df=2,
            max_features=20_000, sublinear_tf=True,
        ),
        TruncatedSVD(n_components=text_svd, random_state=seed),
        StandardScaler(),
    )
    text_repr = text_pipe.fit_transform(train["transcript"].tolist())
    text_kmeans = MiniBatchKMeans(
        n_clusters=text_k, random_state=seed, n_init=20, batch_size=1024
    ).fit(text_repr)

    audio_pipe = make_pipeline(
        StandardScaler(),
        PCA(n_components=audio_pca, random_state=seed),
        StandardScaler(),
    )
    visual_pipe = make_pipeline(
        StandardScaler(),
        PCA(
            n_components=visual_pca, svd_solver="randomized",
            random_state=seed,
        ),
        StandardScaler(),
    )
    audio_repr = audio_pipe.fit_transform(train["audio"])
    visual_repr = visual_pipe.fit_transform(train["visual"])

    audio_kmeans = MiniBatchKMeans(
        n_clusters=proxy_k, random_state=seed + 1, n_init=20, batch_size=1024
    ).fit(audio_repr)
    visual_kmeans = MiniBatchKMeans(
        n_clusters=proxy_k, random_state=seed + 2, n_init=20, batch_size=1024
    ).fit(visual_repr)
    fused_kmeans = MiniBatchKMeans(
        n_clusters=proxy_k, random_state=seed + 3, n_init=20, batch_size=1024
    ).fit(np.concatenate([audio_repr, visual_repr], axis=1))

    return {
        "text_pipe": text_pipe, "text_kmeans": text_kmeans,
        "audio_pipe": audio_pipe, "audio_kmeans": audio_kmeans,
        "visual_pipe": visual_pipe, "visual_kmeans": visual_kmeans,
        "fused_kmeans": fused_kmeans,
    }


def transform_test(test: dict[str, np.ndarray], fitted):
    text_repr = fitted["text_pipe"].transform(test["transcript"].tolist())
    audio_repr = fitted["audio_pipe"].transform(test["audio"])
    visual_repr = fitted["visual_pipe"].transform(test["visual"])
    return {
        "text": fitted["text_kmeans"].predict(text_repr).astype(np.int16),
        "audio": fitted["audio_kmeans"].predict(audio_repr).astype(np.int16),
        "visual": fitted["visual_kmeans"].predict(visual_repr).astype(np.int16),
        "fused": fitted["fused_kmeans"].predict(
            np.concatenate([audio_repr, visual_repr], axis=1)
        ).astype(np.int16),
    }


def fit_and_transform(
    train: dict[str, np.ndarray], test: dict[str, np.ndarray], seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    text_pipe = make_pipeline(
        TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=2,
            max_features=20_000,
            sublinear_tf=True,
        ),
        TruncatedSVD(n_components=32, random_state=seed),
        StandardScaler(),
    )
    audio_pipe = make_pipeline(
        StandardScaler(),
        PCA(n_components=16, random_state=seed),
        StandardScaler(),
    )
    visual_pipe = make_pipeline(
        StandardScaler(),
        PCA(n_components=32, svd_solver="randomized", random_state=seed),
        StandardScaler(),
    )
    text_pipe.fit(train["transcript"].tolist())
    audio_pipe.fit(train["audio"])
    visual_pipe.fit(train["visual"])
    return (
        text_pipe.transform(test["transcript"].tolist()).astype(np.float32),
        audio_pipe.transform(test["audio"]).astype(np.float32),
        visual_pipe.transform(test["visual"]).astype(np.float32),
    )
