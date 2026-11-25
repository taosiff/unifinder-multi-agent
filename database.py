"""
database.py - Persistent Dual-Mode Database (PostgreSQL for Render/Cloud & SQLite for Local)
Supports Render Postgres, Neon, Supabase, or local SQLite seamlessly.
"""

import os
import json
import sqlite3
from typing import List, Dict, Any, Optional

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unifinder.db")


def is_postgres():
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))


def get_pg_connection():
    import psycopg
    from psycopg.rows import dict_row

    db_url = DATABASE_URL
    # Ensure sslmode for cloud postgres (Render, Neon, Supabase)
    if "sslmode=" not in db_url:
        separator = "&" if "?" in db_url else "?"
        db_url = f"{db_url}{separator}sslmode=require"

    return psycopg.connect(db_url, autocommit=True, row_factory=dict_row)


def get_sqlite_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_connection():
    if is_postgres():
        return get_pg_connection()
    return get_sqlite_connection()


def init_db():
    """
    Initializes tables for either PostgreSQL or SQLite.
    """
    if is_postgres():
        init_postgres_db()
    else:
        init_sqlite_db()


def init_sqlite_db():
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS universities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        country TEXT NOT NULL,
        city TEXT NOT NULL,
        degree_levels TEXT NOT NULL,
        subjects TEXT NOT NULL,
        world_ranking INTEGER,
        tuition_fee_annual_usd INTEGER,
        living_cost_annual_usd INTEGER,
        min_gpa REAL,
        min_ielts REAL,
        acceptance_rate_percent REAL,
        post_study_work_permit_years REAL,
        pr_pathway_rating TEXT,
        scholarships_available TEXT,
        student_satisfaction_rating REAL,
        alumni_reviews TEXT,
        top_hiring_companies TEXT,
        official_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_shortlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        university_id INTEGER NOT NULL,
        program_name TEXT NOT NULL,
        degree_level TEXT NOT NULL,
        country TEXT NOT NULL,
        tuition_usd INTEGER,
        pr_status TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (university_id) REFERENCES universities (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        degree_level TEXT,
        subject TEXT,
        country TEXT,
        message_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        doc_name TEXT NOT NULL,
        chunks_json TEXT NOT NULL,
        profile_hints_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM universities")
    if cursor.fetchone()[0] == 0:
        seed_sqlite_universities(conn)

    conn.close()


def init_postgres_db():
    conn = get_pg_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS universities (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        country TEXT NOT NULL,
        city TEXT NOT NULL,
        degree_levels TEXT NOT NULL,
        subjects TEXT NOT NULL,
        world_ranking INTEGER,
        tuition_fee_annual_usd INTEGER,
        living_cost_annual_usd INTEGER,
        min_gpa REAL,
        min_ielts REAL,
        acceptance_rate_percent REAL,
        post_study_work_permit_years REAL,
        pr_pathway_rating TEXT,
        scholarships_available TEXT,
        student_satisfaction_rating REAL,
        alumni_reviews TEXT,
        top_hiring_companies TEXT,
        official_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_shortlists (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        university_id INTEGER NOT NULL,
        program_name TEXT NOT NULL,
        degree_level TEXT NOT NULL,
        country TEXT NOT NULL,
        tuition_usd INTEGER,
        pr_status TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (university_id) REFERENCES universities (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_threads (
        id SERIAL PRIMARY KEY,
        thread_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        degree_level TEXT,
        subject TEXT,
        country TEXT,
        message_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_documents (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        doc_name TEXT NOT NULL,
        chunks_json TEXT NOT NULL,
        profile_hints_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        thread_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("SELECT COUNT(*) as count FROM universities")
    row = cursor.fetchone()
    count = row["count"] if isinstance(row, dict) else row[0]
    if count == 0:
        seed_postgres_universities(cursor)

    conn.close()


RAW_SEED_UNIVERSITIES = [
    (
        "Technical University of Munich (TUM)", "Germany", "Munich",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Artificial Intelligence", "Data Engineering", "Mechanical Engineering", "Biotechnology"]),
        28, 4000, 14000, 3.4, 6.5, 8.0, 1.5, "High",
        "DAAD Scholarships, Deutschlandstipendium, TUM Merit Grants",
        4.8, "World-class engineering labs, strong industrial ties with BMW and Siemens.",
        json.dumps(["BMW", "Siemens", "Google Munich", "Allianz", "Infineon"]),
        "https://www.tum.de"
    ),
    (
        "RWTH Aachen University", "Germany", "Aachen",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Mechanical Engineering", "Computer Science", "Electrical Engineering", "Robotics"]),
        106, 700, 12000, 3.2, 6.5, 12.0, 1.5, "High",
        "DAAD Graduate Grants, RWTH Education Fund",
        4.6, "The MIT of Germany for engineering. Rigorous coursework, affordable living.",
        json.dumps(["Bosch", "Porsche", "Airbus", "Daimler", "Continental"]),
        "https://www.rwth-aachen.de"
    ),
    (
        "Heidelberg University", "Germany", "Heidelberg",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Medicine", "Biomedical Sciences", "Molecular Biotechnology", "Physics", "Computer Science"]),
        87, 3200, 13000, 3.5, 6.5, 15.0, 1.5, "High",
        "German Research Foundation (DFG), Baden-Württemberg Fellowship",
        4.7, "Germany's oldest university. Renowned life sciences research.",
        json.dumps(["Roche", "Bayer", "Merck KGaA", "EMBL", "Max Planck"]),
        "https://www.uni-heidelberg.de"
    ),
    (
        "Free University of Berlin (FU Berlin)", "Germany", "Berlin",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Data Science", "International Relations", "Economics", "Psychology", "Environmental Studies"]),
        98, 650, 14500, 3.3, 6.5, 16.0, 1.5, "High",
        "Berlin Graduate School Fellowships, DAAD",
        4.5, "Multicultural capital city, thriving startup ecosystem.",
        json.dumps(["Zalando", "Delivery Hero", "N26", "SoundCloud"]),
        "https://www.fu-berlin.de"
    ),
    (
        "University of Oxford", "United Kingdom", "Oxford",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Artificial Intelligence", "Economics", "Law", "Medicine"]),
        3, 42000, 19000, 3.85, 7.5, 14.0, 2.0, "Moderate",
        "Clarendon Fund, Rhodes Scholarship, Oxford-Weidenfeld",
        4.9, "Tutorial system provides unrivaled academic rigor.",
        json.dumps(["DeepMind", "Goldman Sachs", "McKinsey", "Microsoft Research"]),
        "https://www.ox.ac.uk"
    ),
    (
        "University of Cambridge", "United Kingdom", "Cambridge",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Engineering", "Mathematics", "Biotechnology", "Business/MBA"]),
        2, 45000, 18500, 3.9, 7.5, 12.0, 2.0, "Moderate",
        "Gates Cambridge, Cambridge Trust, Commonwealth Scholarships",
        4.9, "Silicon Fen technology cluster surrounds Cambridge.",
        json.dumps(["ARM", "Amazon Cambridge", "AstraZeneca", "Google DeepMind"]),
        "https://www.cam.ac.uk"
    ),
    (
        "Imperial College London", "United Kingdom", "London",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Data Science", "Artificial Intelligence", "Finance", "Mechanical Engineering"]),
        6, 44000, 22000, 3.75, 7.0, 11.0, 2.0, "Moderate",
        "President's PhD Scholarships, Chevening, Imperial STEM Grants",
        4.7, "Pure focus on STEM and business in South Kensington.",
        json.dumps(["Google", "Meta", "Barclays", "JPMorgan", "Bloomberg"]),
        "https://www.imperial.ac.uk"
    ),
    (
        "Massachusetts Institute of Technology (MIT)", "United States", "Cambridge, MA",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Artificial Intelligence", "Electrical Engineering", "Physics", "Finance"]),
        1, 60000, 24000, 3.95, 7.5, 4.0, 3.0, "Moderate",
        "Full PhD funding packages (tuition + stipend)",
        5.0, "Global pinnacle of technology, innovation, and startup culture.",
        json.dumps(["Google", "Apple", "OpenAI", "NVIDIA", "Jane Street"]),
        "https://www.mit.edu"
    ),
    (
        "Stanford University", "United States", "Stanford, CA",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Business Administration", "Data Science", "Bioengineering"]),
        5, 62000, 26000, 3.92, 7.5, 3.9, 3.0, "Moderate",
        "Knight-Hennessy Scholars, Stanford Graduate Fellowships",
        4.9, "Heart of Silicon Valley. Tremendous venture capital access.",
        json.dumps(["Google", "Meta", "Tesla", "Stripe", "Anthropic"]),
        "https://www.stanford.edu"
    ),
    (
        "University of Toronto", "Canada", "Toronto, ON",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Artificial Intelligence", "Data Science", "Management"]),
        21, 46000, 18000, 3.6, 7.0, 38.0, 3.0, "High",
        "Lester B. Pearson Scholarship, Ontario Graduate Scholarship (OGS)",
        4.7, "Leading AI institution worldwide (Vector Institute). 3-yr PGWP.",
        json.dumps(["Vector Institute", "Shopify", "RBC", "TD Bank", "Amazon"]),
        "https://www.utoronto.ca"
    ),
    (
        "University of British Columbia (UBC)", "Canada", "Vancouver, BC",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Data Science", "Computer Science", "Forestry", "Business Administration"]),
        34, 41000, 19000, 3.5, 6.5, 42.0, 3.0, "High",
        "International Major Entrance Scholarship, 4YF Fellowships",
        4.6, "Beautiful Pacific campus, straightforward BC PNP PR stream.",
        json.dumps(["Microsoft Vancouver", "EA Games", "Amazon Vancouver"]),
        "https://www.ubc.ca"
    ),
    (
        "University of Melbourne", "Australia", "Melbourne, VIC",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Information Systems", "Civil Engineering", "Biomedicine"]),
        13, 35000, 19000, 3.4, 6.5, 55.0, 3.0, "High",
        "Melbourne International Undergraduate Scholarship, RTP",
        4.7, "Australia's #1 ranked university. Melbourne is one of the world's most liveable cities.",
        json.dumps(["Atlassian", "ANZ", "BHP", "Telstra", "Canva"]),
        "https://www.unimelb.edu.au"
    ),
    (
        "Delft University of Technology (TU Delft)", "Netherlands", "Delft",
        json.dumps(["BSc", "MSc", "PhD"]),
        json.dumps(["Computer Science", "Aerospace Engineering", "Civil Engineering", "Data Science"]),
        47, 18500, 13500, 3.4, 6.5, 40.0, 1.0, "High",
        "Justus & Louise van Effen Excellence Scholarship",
        4.8, "Top European technical university. 100% English-taught master's degrees.",
        json.dumps(["ASML", "Philips", "Booking.com", "Shell"]),
        "https://www.tudelft.nl"
    )
]


def seed_sqlite_universities(conn):
    cursor = conn.cursor()
    cursor.executemany("""
    INSERT INTO universities (
        name, country, city, degree_levels, subjects,
        world_ranking, tuition_fee_annual_usd, living_cost_annual_usd,
        min_gpa, min_ielts, acceptance_rate_percent,
        post_study_work_permit_years, pr_pathway_rating,
        scholarships_available, student_satisfaction_rating,
        alumni_reviews, top_hiring_companies, official_url
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, RAW_SEED_UNIVERSITIES)
    conn.commit()


def seed_postgres_universities(cursor):
    cursor.executemany("""
    INSERT INTO universities (
        name, country, city, degree_levels, subjects,
        world_ranking, tuition_fee_annual_usd, living_cost_annual_usd,
        min_gpa, min_ielts, acceptance_rate_percent,
        post_study_work_permit_years, pr_pathway_rating,
        scholarships_available, student_satisfaction_rating,
        alumni_reviews, top_hiring_companies, official_url
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, RAW_SEED_UNIVERSITIES)


def search_universities(
    degree_level: Optional[str] = None,
    subject: Optional[str] = None,
    country: Optional[str] = None,
    max_tuition: Optional[int] = None,
    user_gpa: Optional[float] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"

    query = "SELECT * FROM universities WHERE 1=1"
    params = []

    if degree_level and degree_level.upper() in ["BSC", "MSC", "PHD"]:
        if is_postgres():
            query += f" AND degree_levels ILIKE {ph}"
        else:
            query += f" AND degree_levels LIKE {ph}"
        params.append(f'%"{degree_level}"%')

    if country and country.strip():
        query += f" AND country ILIKE {ph}" if is_postgres() else f" AND country LIKE {ph}"
        params.append(f"%{country.strip()}%")

    if max_tuition and max_tuition > 0:
        query += f" AND tuition_fee_annual_usd <= {ph}"
        params.append(max_tuition)

    if user_gpa and user_gpa > 0:
        query += f" AND min_gpa <= {ph}"
        params.append(user_gpa + 0.3)

    query += f" ORDER BY world_ranking ASC LIMIT {ph}"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        if "created_at" in item and item["created_at"] is not None:
            item["created_at"] = str(item["created_at"])
        try:
            if isinstance(item["degree_levels"], str):
                item["degree_levels"] = json.loads(item["degree_levels"])
            if isinstance(item["subjects"], str):
                item["subjects"] = json.loads(item["subjects"])
            if isinstance(item["top_hiring_companies"], str):
                item["top_hiring_companies"] = json.loads(item["top_hiring_companies"])
        except Exception:
            pass
        results.append(item)

    conn.close()

    if subject and subject.strip():
        subj_lower = subject.lower().strip()
        filtered = []
        for u in results:
            subjects_list = [s.lower() for s in u.get("subjects", [])]
            if any(subj_lower in s or s in subj_lower for s in subjects_list):
                filtered.append(u)
        if filtered:
            return filtered

    return results


def add_to_shortlist(
    session_id: str,
    university_id: int,
    program_name: str,
    degree_level: str,
    notes: str = ""
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"

    cursor.execute(f"SELECT * FROM universities WHERE id = {ph}", (university_id,))
    uni = cursor.fetchone()
    if not uni:
        conn.close()
        return {"success": False, "error": "University not found"}

    uni_dict = dict(uni)

    if is_postgres():
        cursor.execute("""
        INSERT INTO user_shortlists (
            session_id, university_id, program_name, degree_level,
            country, tuition_usd, pr_status, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (
            session_id, university_id, program_name, degree_level,
            uni_dict["country"], uni_dict["tuition_fee_annual_usd"],
            uni_dict["pr_pathway_rating"], notes
        ))
        row = cursor.fetchone()
        shortlist_id = row["id"] if isinstance(row, dict) else row[0]
    else:
        cursor.execute("""
        INSERT INTO user_shortlists (
            session_id, university_id, program_name, degree_level,
            country, tuition_usd, pr_status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, university_id, program_name, degree_level,
            uni_dict["country"], uni_dict["tuition_fee_annual_usd"],
            uni_dict["pr_pathway_rating"], notes
        ))
        shortlist_id = cursor.lastrowid
        conn.commit()

    conn.close()
    return {"success": True, "shortlist_id": shortlist_id, "university_name": uni_dict["name"]}


def get_shortlist(session_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"

    cursor.execute(f"""
    SELECT s.*, u.name as university_name, u.city, u.world_ranking,
           u.living_cost_annual_usd, u.post_study_work_permit_years,
           u.student_satisfaction_rating, u.official_url
    FROM user_shortlists s
    JOIN universities u ON s.university_id = u.id
    WHERE s.session_id = {ph}
    ORDER BY s.created_at DESC
    """, (session_id,))

    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results


def remove_from_shortlist(session_id: str, shortlist_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"

    cursor.execute(f"DELETE FROM user_shortlists WHERE id = {ph} AND session_id = {ph}", (shortlist_id, session_id))
    affected = cursor.rowcount
    if not is_postgres():
        conn.commit()
    conn.close()
    return affected > 0


def get_or_create_thread(thread_id: str, title: str = "New Counseling Chat", degree: str = "MSc", subject: str = "Computer Science", country: str = "") -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"

    cursor.execute(f"SELECT * FROM chat_threads WHERE thread_id = {ph}", (thread_id,))
    row = cursor.fetchone()

    if row:
        cursor.execute(f"UPDATE chat_threads SET message_count = message_count + 1, updated_at = CURRENT_TIMESTAMP WHERE thread_id = {ph}", (thread_id,))
        if not is_postgres():
            conn.commit()
        item = dict(row)
        conn.close()
        return item

    if is_postgres():
        cursor.execute("""
        INSERT INTO chat_threads (thread_id, title, degree_level, subject, country, message_count)
        VALUES (%s, %s, %s, %s, %s, 1) RETURNING *
        """, (thread_id, title, degree, subject, country))
        new_row = dict(cursor.fetchone())
    else:
        cursor.execute("""
        INSERT INTO chat_threads (thread_id, title, degree_level, subject, country, message_count)
        VALUES (?, ?, ?, ?, ?, 1)
        """, (thread_id, title, degree, subject, country))
        conn.commit()
        cursor.execute("SELECT * FROM chat_threads WHERE thread_id = ?", (thread_id,))
        new_row = dict(cursor.fetchone())

    conn.close()
    return new_row


def list_chat_threads(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"
    cursor.execute(f"SELECT * FROM chat_threads ORDER BY updated_at DESC LIMIT {ph}", (limit,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def delete_chat_thread(thread_id: str) -> bool:
    res = purge_session_data(thread_id=thread_id, session_id=thread_id)
    return res.get("deleted_threads", 0) > 0 or res.get("total_deleted", 0) > 0


def purge_session_data(thread_id: str, session_id: Optional[str] = None) -> Dict[str, int]:
    """
    Completely removes all personal & session data (chat thread, uploaded CVs/documents,
    shortlists, and LangGraph checkpoint memory) from the online PostgreSQL / local SQLite DB.
    """
    sid = session_id or thread_id
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"

    counts = {
        "deleted_threads": 0,
        "deleted_documents": 0,
        "deleted_shortlists": 0,
        "deleted_checkpoints": 0
    }

    try:
        cursor.execute(f"DELETE FROM chat_threads WHERE thread_id = {ph}", (thread_id,))
        counts["deleted_threads"] = cursor.rowcount or 0

        cursor.execute(f"DELETE FROM chat_messages WHERE thread_id = {ph}", (thread_id,))
        counts["deleted_messages"] = cursor.rowcount or 0

        cursor.execute(f"DELETE FROM session_documents WHERE session_id = {ph} OR session_id = {ph}", (sid, thread_id))
        counts["deleted_documents"] = cursor.rowcount or 0

        cursor.execute(f"DELETE FROM user_shortlists WHERE session_id = {ph} OR session_id = {ph}", (sid, thread_id))
        counts["deleted_shortlists"] = cursor.rowcount or 0

        # Purge LangGraph checkpointer tables for this thread_id
        lg_tables = ["checkpoint_writes", "checkpoint_blobs", "checkpoints"] if is_postgres() else ["writes", "checkpoints"]
        for tbl in lg_tables:
            try:
                cursor.execute(f"DELETE FROM {tbl} WHERE thread_id = {ph}", (thread_id,))
                counts["deleted_checkpoints"] += (cursor.rowcount or 0)
            except Exception:
                pass

        if not is_postgres():
            conn.commit()
    finally:
        conn.close()

    counts["total_deleted"] = sum(counts.values())
    return counts


def save_session_document(session_id: str, doc_name: str, chunks: List[Dict[str, Any]], profile_hints: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"
    cursor.execute(
        f"INSERT INTO session_documents (session_id, doc_name, chunks_json, profile_hints_json) VALUES ({ph}, {ph}, {ph}, {ph})",
        (session_id, doc_name, json.dumps(chunks), json.dumps(profile_hints))
    )
    if not is_postgres():
        conn.commit()
    conn.close()
    return True


def get_session_document_records(session_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"
    cursor.execute(
        f"SELECT doc_name, chunks_json, profile_hints_json FROM session_documents WHERE session_id = {ph} ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        item = dict(row)
        try:
            item["chunks"] = json.loads(item.get("chunks_json") or "[]")
            item["profile_hints"] = json.loads(item.get("profile_hints_json") or "{}")
        except Exception:
            item["chunks"] = []
            item["profile_hints"] = {}
        results.append(item)
    return results


def save_chat_message(thread_id: str, role: str, content: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"
    cursor.execute(
        f"INSERT INTO chat_messages (thread_id, role, content) VALUES ({ph}, {ph}, {ph})",
        (thread_id, role, content)
    )
    if not is_postgres():
        conn.commit()
    conn.close()
    return True


def get_chat_messages(thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if is_postgres() else "?"
    cursor.execute(
        f"SELECT role, content, created_at FROM chat_messages WHERE thread_id = {ph} ORDER BY id ASC LIMIT {ph}",
        (thread_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        if item.get("created_at") is not None:
            item["created_at"] = str(item["created_at"])
        results.append(item)
    return results


init_db()
