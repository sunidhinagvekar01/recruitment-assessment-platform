import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

sqlite_conn = sqlite3.connect("assessment.db")
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

pg_conn = psycopg2.connect(os.getenv("DATABASE_URL"))
pg_cur = pg_conn.cursor()

tables = [
    "users",
    "assessments",
    "questions",
    "question_bank",
    "responses",
    "scores"
]

for table in tables:

    sqlite_cur.execute(f"SELECT * FROM {table}")
    rows = sqlite_cur.fetchall()

    if not rows:
        print(f"{table}: No data")
        continue

    columns = rows[0].keys()

    col_string = ",".join(columns)
    placeholders = ",".join(["%s"] * len(columns))

    insert_query = f"""
        INSERT INTO {table}
        ({col_string})
        VALUES ({placeholders})
    """

    for row in rows:
        pg_cur.execute(insert_query, tuple(row))

    print(f"{table}: {len(rows)} rows migrated")

pg_conn.commit()

sqlite_conn.close()
pg_conn.close()

print("\nMigration completed successfully!")