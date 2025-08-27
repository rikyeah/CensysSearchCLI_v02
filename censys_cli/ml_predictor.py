#!/usr/bin/env python3
"""
Machine‑learning predictor for CAPTCHA bypass method selection.

This module uses a Random Forest classifier to recommend whether the Censys
CLI should attempt a Proof‑of‑Work (``pow``) or 2Captcha (``2captcha``)
bypass based on historical CAPTCHA metrics stored in SQLite.  It gracefully
handles missing dependencies (pandas or scikit‑learn) by falling back to a
deterministic choice.
"""
from __future__ import annotations

import sqlite3
from typing import Optional, Tuple

try:
    import pandas as pd  # type: ignore
except ImportError:
    pd = None  # type: ignore
try:
    from sklearn.ensemble import RandomForestClassifier  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore
    from sklearn.metrics import accuracy_score  # type: ignore
except ImportError:
    RandomForestClassifier = None  # type: ignore
    train_test_split = None  # type: ignore
    accuracy_score = None  # type: ignore

class MLPredictor:
    """Predict the optimal CAPTCHA bypass method using a simple ML model."""

    def __init__(self, db_path: str = "./analytics.sqlite") -> None:
        self.db_path = db_path
        self.model: Optional[RandomForestClassifier] = None
        self.trained: bool = False

    def load_data(self):
        """Load historical CAPTCHA metrics from the SQLite database.

        Returns a pandas DataFrame with columns ``method``, ``success``,
        ``response_time`` and ``error_message``.  Returns an empty
        DataFrame if pandas is unavailable or the table does not exist.
        """
        if pd is None:
            return None
        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql_query(
                "SELECT method, success, response_time, error_message FROM captcha_metrics",
                conn
            )
            return df
        except Exception:
            # Table may not exist yet
            return pd.DataFrame()
        finally:
            conn.close()

    def preprocess(self, df) -> Tuple[object, object]:
        """Preprocess the historical data for training.

        * Encodes the error type from ``error_message`` (the prefix before a colon)
          and fills missing ``response_time`` with the mean.
        * One‑hot encodes the ``method`` and ``error_type`` categorical features.

        Returns ``(X, y)`` where ``X`` is a DataFrame of features and ``y``
        is a Series of target labels.
        """
        # Extract error_type from error_message
        df = df.copy()
        df['error_type'] = df['error_message'].apply(
            lambda x: 'none' if x is None or (pd.isna(x) if pd is not None else True) else str(x).split(':')[0]
        )
        # Impute missing response_time values with the mean
        mean_time = df['response_time'].mean() if not df['response_time'].empty else 0
        df['response_time'] = df['response_time'].fillna(mean_time)
        # One‑hot encode categorical columns
        features = pd.get_dummies(df[['method', 'error_type']], columns=['method', 'error_type'])
        features['response_time'] = df['response_time']
        target = df['success']
        return features, target

    def train(self) -> bool:
        """Train the Random Forest model using available data.

        Returns True if training succeeds, otherwise False (e.g. if there
        is insufficient data or dependencies are missing).
        """
        # Ensure dependencies are present
        if pd is None or RandomForestClassifier is None or train_test_split is None:
            return False
        df = self.load_data()
        if df is None or df.empty:
            return False
        X, y = self.preprocess(df)
        # If there are no positive or no negative samples, training is not meaningful
        if y.nunique() < 2:
            return False
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model = RandomForestClassifier(n_estimators=50, random_state=42)
        self.model.fit(X_train, y_train)
        # Evaluate for informational purposes
        if accuracy_score is not None:
            accuracy = accuracy_score(y_test, self.model.predict(X_test))
            print(f"[INFO] ML model accuracy: {accuracy:.3f}")
        self.trained = True
        return True

    def recommend(self) -> str:
        """Recommend the optimal CAPTCHA bypass method.

        If the model has not been trained or dependencies are unavailable,
        defaults to ``pow``.  Otherwise, it constructs synthetic feature
        vectors for ``pow`` and ``2captcha`` using average metrics from
        historical data and returns the method with the higher predicted
        probability of success.
        """
        # Default recommendation if model cannot be trained
        if not self.trained or self.model is None or pd is None:
            return 'pow'
        df = self.load_data()
        if df is None or df.empty:
            return 'pow'
        # Build feature vectors for each method with average response_time
        mean_time = df['response_time'].fillna(df['response_time'].mean()).mean()
        methods = ['pow', '2captcha']
        candidates = []
        for m in methods:
            row = {'response_time': mean_time}
            # One‑hot encode method
            for method_name in methods:
                row[f'method_{method_name}'] = 1 if method_name == m else 0
            # Assume no error type
            row['error_type_none'] = 1
            candidates.append(row)
        X_candidate = pd.DataFrame(candidates).reindex(columns=self.model.feature_names_in_, fill_value=0)
        probs = self.model.predict_proba(X_candidate)[:, 1]  # Probability of success
        return methods[int(probs.argmax())]