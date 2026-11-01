import os
import mysql.connector
from dotenv import load_dotenv

# MUST be called BEFORE os.getenv!
load_dotenv()

# Fetch environment variables
db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME", "defaultdb")
db_port_raw = os.getenv("DB_PORT")

# Debug check: Print port to Render logs during startup
print(f"Attempting connection to {db_host} on port {db_port_raw}...")

if not db_port_raw:
    raise ValueError("DB_PORT is missing from Environment Variables!")

# Connect using the explicit integer port
db = mysql.connector.connect(
    host=db_host,
    port=int(db_port_raw),
    user=db_user,
    password=db_pass,
    database=db_name
)

print(f"Successfully connected to the database '{db_name}' on port {db_port_raw}.")
