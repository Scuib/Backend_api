import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.metrics.pairwise import cosine_similarity
import joblib

class AssistRecommender:
    def __init__(self):
        self.model = MLPClassifier(hidden_layer_sizes=(100,), max_iter=300, random_state=42)

    def train(self, user_features, assist_features, positive_pairs):
        num_users = user_features.shape[0]
        num_assists = assist_features.shape[0]
        
        # Create training data by combining user and assist features
        X = []
        y = []

        for user_index in range(num_users):
            for assist_index in range(num_assists):
                combined_features = user_features[user_index].toarray()[0].tolist() + assist_features[assist_index].toarray()[0].tolist()
                X.append(combined_features)
                y.append(1 if (user_index, assist_index) in positive_pairs else 0)

        X = np.array(X)
        y = np.array(y)

        self.model.fit(X, y)

    def recommend(self, user_feature, assist_features, top_k=5):
        X = []

        for assist_feature in assist_features:
            combined_features = user_feature.toarray()[0].tolist() + assist_feature.toarray()[0].tolist()
            X.append(combined_features)

        probabilities = self.model.predict_proba(X)[:, 1]
        assist_indices = probabilities.argsort()[-top_k:][::-1]
        return assist_indices

    def save_model(self, file_name):
        joblib.dump(self.model, file_name)

    @classmethod
    def load_model(cls, file_name):
        recommender = cls()
        recommender.model = joblib.load(file_name)
        return recommender
