import os
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

if not url or not key:
    print("Credentials not found!")
else:
    supabase = create_client(url, key)
    print("StudyMate connected to Supabase successfully!")
    