import psycopg2
import os

def get_connection(): return psycopg2.connect( host=os.environ.get("SUPABASE_HOST"), dbname=os.environ.get("SUPABASE_DBNAME"), user=os.environ.get("SUPABASE_USER"), password=os.environ.get("SUPABASE_PASSWORD"), port=os.environ.get("SUPABASE_PORT", 5432) )

