import os
import sqlite3
from app.utils.database import setup_database

def main():
    """
    Recreate the database with the correct schema.
    WARNING: This will delete all existing data!
    """
    # Define the db path
    db_dir = os.path.join(os.path.dirname(__file__), "app", "data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "geocoding.db")
    
    # Delete the existing database if it exists
    if os.path.exists(db_path):
        try:
            print(f"Deleting existing database at {db_path}")
            os.remove(db_path)
            print("Existing database deleted successfully")
        except Exception as e:
            print(f"Error deleting database: {e}")
            return
    
    # Create a new database with the correct schema
    print("Creating new database with updated schema...")
    setup_database()
    print("Database setup complete!")
    
    # Verify the table schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check the routes table schema
    cursor.execute("PRAGMA table_info(routes)")
    columns = [col[1] for col in cursor.fetchall()]
    print("\nRoutes table columns:")
    for col in columns:
        print(f"- {col}")
    
    conn.close()
    print("\nDatabase recreation completed successfully!")

if __name__ == "__main__":
    main()
