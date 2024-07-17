from sklearn.neural_network import MLPClassifier
import joblib
import numpy as np

class JobRecommender:
    def __init__(self):
        self.model = MLPClassifier(hidden_layer_sizes=(100,), max_iter=300, random_state=42)

    def train(self, user_features, job_features, positive_pairs):
        num_users = user_features.shape[0]
        num_jobs = job_features.shape[0]
        
        # Create training data by combining user and job features
        X = []
        y = []

        if not positive_pairs:
            for user_index in range(num_users):
                for job_index in range(num_jobs):
                    combined_features = user_features[user_index].toarray()[0].tolist() + job_features[job_index].toarray()[0].tolist()
                    X.append(combined_features)
                    y.append(1 if np.random.rand() > 0.5 else 0)  # Random positive/negative labels
        else:
            for user_index in range(num_users):
                for job_index in range(num_jobs):
                    combined_features = user_features[user_index].toarray()[0].tolist() + job_features[job_index].toarray()[0].tolist()
                    X.append(combined_features)
                    y.append(1 if (user_index, job_index) in positive_pairs else 0)

        X = np.array(X)
        y = np.array(y)

        self.model.fit(X, y)

    def recommend(self, user_feature, job_features, top_k=5):
        X = []

        for job_feature in job_features:
            combined_features = user_feature.toarray()[0].tolist() + job_feature.toarray()[0].tolist()
            X.append(combined_features)

        probabilities = self.model.predict_proba(X)[:, 1]
        job_indices = probabilities.argsort()[-top_k:][::-1]
        return job_indices

    def save_model(self, file_name):
        joblib.dump(self.model, file_name)

    @classmethod
    def load_model(cls, file_name):
        recommender = cls()
        recommender.model = joblib.load(file_name)
        return recommender

