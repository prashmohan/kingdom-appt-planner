import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'data/planner.db')

