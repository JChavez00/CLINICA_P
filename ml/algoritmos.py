"""Las cinco familias para cada objetivo; escalado dentro del pipeline."""
from sklearn.ensemble import (RandomForestClassifier, RandomForestRegressor,
                              GradientBoostingClassifier, GradientBoostingRegressor)
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def candidatos():
    return {
        "clasificacion": {
            "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=4, class_weight="balanced", random_state=42, n_jobs=1),
            "Decision Tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=4, class_weight="balanced", random_state=42),
            "Gradient Boosting": GradientBoostingClassifier(n_estimators=100, max_depth=2, random_state=42),
            "KNN": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5)),
            "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
        },
        "regresion": {
            "Random Forest": RandomForestRegressor(n_estimators=200, max_depth=6, min_samples_leaf=4, random_state=42, n_jobs=1),
            "Decision Tree": DecisionTreeRegressor(max_depth=5, min_samples_leaf=4, random_state=42),
            "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, max_depth=2, random_state=42),
            "KNN": make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=5)),
            "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        },
    }
