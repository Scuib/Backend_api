from data_preprocessor import DataPreprocessor
from recommender import JobRecommender
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File paths
job_file = 'data/job_postings.csv'
user_file = 'data/user_profiles.csv'
model_file = 'models/job_recommendation_model.pkl'

try:
    # Data preprocessing
    preprocessor = DataPreprocessor(job_file, user_file)
    logger.info("Loading data...")
    preprocessor.load_data()
    
    logger.info("Preprocessing data...")
    filtered_user_profiles, job_postings = preprocessor.preprocess_data()
    
    logger.info("Vectorizing features...")
    user_features, job_features = preprocessor.vectorize_features()
    
    # Initialize and train recommender
    recommender = JobRecommender()
    logger.info("Training recommender...")
    
    # Generate positive pairs
    positive_pairs = []
    for user_index, user_row in filtered_user_profiles.iterrows():
        for job_index, job_row in job_postings.iterrows():
            if (user_row['expected_salary'] >= job_row['min_pay'] and
                user_row['expected_salary'] <= job_row['max_pay']):
                positive_pairs.append((user_index, job_index))

    # Train the recommender model
    recommender.train(user_features, job_features, positive_pairs)

    # Save the trained model
    logger.info("Saving model...")
    recommender.save_model(model_file)
    logger.info("Model saved successfully.")

except Exception as e:
    logger.error(f"An error occurred: {e}")
    raise