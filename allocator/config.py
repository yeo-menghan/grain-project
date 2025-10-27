# allocator/config.py
"""Configuration settings for the allocator"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-4.1"
OPENAI_TEMPERATURE = 0.3
MAX_TOKENS = 16000  # Maximum tokens for response

# File paths
DATA_DIR = './data'
ATTEMPTS_DIR = os.path.join(DATA_DIR, 'attempts')
DRIVERS_FILE = os.path.join(DATA_DIR, 'drivers.json')
ORDERS_FILE = os.path.join(DATA_DIR, 'orders.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'allocation_results.json')
TOKEN_USAGE_FILE = os.path.join(DATA_DIR, 'token_usage.json')

# Allocation settings
MAX_RETRIES = 5

# Scoring weights
SCORE_WEIGHTS = {
    'time_conflicts': 10000,
    'capability_mismatches': 5000,
    'capacity_violations': 500,
    'resource_waste': 100,
    'region_mismatches': 10,
    'other': 50
}

# Capability tags
WEDDING_CAPABILITIES = {'vip', 'wedding', 'large_events'}
CORPORATE_CAPABILITIES = {'corporate', 'seminars'}

# Token usage tracking
TRACK_TOKEN_USAGE = True

# Pricing
# GPT-4 Turbo pricing per 1M tokens
PRICE_PER_1M_INPUT_TOKENS = 2.00
PRICE_PER_1M_OUTPUT_TOKENS = 8.00