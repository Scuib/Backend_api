# from sklearn.neural_network import MLPClassifier
# import joblib
# import numpy as np
# import pandas as pd

# class JobRecommender:
#     def __init__(self):
#         self.model = MLPClassifier(hidden_layer_sizes=(100,), max_iter=300, random_state=42)

#     def train(self, preprocessor, positive_pairs=None):
#         user_features = preprocessor.user_tfidf_matrix
#         job_feature = preprocessor.job_tfidf_matrix
#         num_users = user_features.shape[0]
        
#         # Create training data by combining user and job features
#         X = []
#         y = []

#         for user_index in range(num_users):
#             combined_features = user_features[user_index].toarray()[0].tolist() + job_feature.toarray()[0].tolist()
#             X.append(combined_features)
            
#             # Determine the label based on the matching criteria
#             is_match = (
#                 preprocessor.user_profiles['exp_match'].iloc[user_index] and
#                 preprocessor.user_profiles['category_match'].iloc[user_index] and
#                 preprocessor.user_profiles['salary_match'].iloc[user_index]
#             )
#             y.append(1 if is_match else 0)

#         X = np.array(X)
#         y = np.array(y)

#         self.model.fit(X, y)

#     def recommend(self, preprocessor, top_k=5):
#         user_features = preprocessor.user_tfidf_matrix
#         job_feature = preprocessor.job_tfidf_matrix
#         X = []

#         for user_feature in user_features:
#             combined_features = user_feature.toarray()[0].tolist() + job_feature.toarray()[0].tolist()
#             X.append(combined_features)

#         probabilities = self.model.predict_proba(X)[:, 1]
        
#         # Create a DataFrame with user IDs and probabilities
#         results = pd.DataFrame({
#             'id': preprocessor.user_profiles['id'],
#             'probability': probabilities,
#             'exp_match': preprocessor.user_profiles['exp_match'],
#             'category_match': preprocessor.user_profiles['category_match'],
#             'salary_match': preprocessor.user_profiles['salary_match']
#         })
        
#         # Calculate total_match score
#         results['total_match'] = (
#             results['exp_match'].astype(int) +
#             results['category_match'].astype(int) +
#             results['salary_match'].astype(int)
#         )
        
#         # Sort by probability and total_match
#         results = results.sort_values(['probability', 'total_match'], ascending=[False, False])
        
#         # Return top_k results
#         return results[['id', 'probability', 'total_match']].head(top_k)

#     def save_model(self, file_name):
#         joblib.dump(self.model, file_name)

#     @classmethod
#     def load_model(cls, file_name):
#         recommender = cls()
#         recommender.model = joblib.load(file_name)
#         return recommender

from sklearn.neural_network import MLPClassifier
import joblib
import numpy as np
import pandas as pd
from ..models import RecommenderModel
import io

class JobRecommender:
    def __init__(self):
        self.model = MLPClassifier(hidden_layer_sizes=(100,), max_iter=300, random_state=42)

    def train(self, preprocessor, positive_pairs=None):
        user_features = preprocessor.user_tfidf_matrix
        job_feature = preprocessor.job_tfidf_matrix
        num_users = user_features.shape[0]
        
        # Create training data by combining user and job features
        X = []
        y = []

        for user_index in range(num_users):
            combined_features = user_features[user_index].toarray()[0].tolist() + job_feature.toarray()[0].tolist()
            X.append(combined_features)
            
            # Determine the label based on the matching criteria
            is_match = (
                preprocessor.user_profiles['exp_match'].iloc[user_index] and
                preprocessor.user_profiles['category_match'].iloc[user_index] and
                preprocessor.user_profiles['salary_match'].iloc[user_index]
            )
            y.append(1 if is_match else 0)

        X = np.array(X)
        y = np.array(y)

        self.model.fit(X, y)

    def recommend(self, preprocessor, top_k=5):
        user_features = preprocessor.user_tfidf_matrix
        job_feature = preprocessor.job_tfidf_matrix
        X = []

        for user_feature in user_features:
            combined_features = user_feature.toarray()[0].tolist() + job_feature.toarray()[0].tolist()
            X.append(combined_features)

        probabilities = self.model.predict_proba(X)[:, 1]
        
        # Create a DataFrame with user IDs and probabilities
        results = pd.DataFrame({
            'id': preprocessor.user_profiles['id'],
            'probability': probabilities,
            'exp_match': preprocessor.user_profiles['exp_match'],
            'category_match': preprocessor.user_profiles['category_match'],
            'salary_match': preprocessor.user_profiles['salary_match']
        })
        
        # Calculate total_match score
        results['total_match'] = (
            results['exp_match'].astype(int) +
            results['category_match'].astype(int) +
            results['salary_match'].astype(int)
        )
        
        # Sort by probability and total_match
        results = results.sort_values(['probability', 'total_match'], ascending=[False, False])
        
        # Return top_k results
        return results[['id', 'probability', 'total_match']].head(top_k)

    
    def save_model_to_db(self):
            # Serialize the model into a binary stream
            model_buffer = io.BytesIO()
            joblib.dump(self.model, model_buffer)
            model_binary_data = model_buffer.getvalue()

            # Create a new RecommenderModel entry
            recommender_model = RecommenderModel(name="Job Recommender", model_data=model_binary_data)
            recommender_model.save()
            print("Model saved to the database.")

    @classmethod
    def load_model_from_db(cls):
        # Fetch the latest saved model from the database
        try:
            recommender_model = RecommenderModel.objects.latest('created_at')  # Fetch most recent model
            model_binary_data = recommender_model.model_data

            # Deserialize the binary data back into a model
            model_buffer = io.BytesIO(model_binary_data)
            loaded_model = joblib.load(model_buffer)

            recommender = cls()
            recommender.model = loaded_model
            print("Model loaded from the database.")
            return recommender

        except RecommenderModel.DoesNotExist:
            print("No model found in the database. Training a new model...")
            return None
