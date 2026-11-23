"""
test_app.py - End-to-End Verification Test for UniFinder AI
Tests database queries, web scrapers, subgraphs, RAG/C-RAG, opportunities, streaming, and HITL endpoints.
"""

from fastapi.testclient import TestClient
from app import app
import json
import io

client = TestClient(app)

def test_health():
    print("Testing /health endpoint...")
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    print("✅ /health PASSED:", data)

def test_home_page():
    print("Testing / (HTML home page)...")
    response = client.get("/")
    assert response.status_code == 200
    assert "UniFinder" in response.text
    print("✅ / (HTML Home) PASSED")

def test_opportunities_api():
    print("Testing /api/opportunities...")
    response = client.get("/api/opportunities?destination=Germany&degree=MSc")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["scholarships"]) > 0
    assert len(data["news"]) > 0
    print(f"✅ /api/opportunities PASSED: Found {len(data['scholarships'])} scholarships and {len(data['news'])} news items")

def test_threads_api():
    print("Testing chat threads CRUD...")
    # 1. Create thread
    res = client.post("/api/threads", json={"title": "Test AI Counseling", "degree_level": "MSc", "subject": "AI"})
    assert res.status_code == 200
    th = res.json()["thread"]
    thread_id = th["thread_id"]
    assert th["title"] == "Test AI Counseling"

    # 2. List threads
    list_res = client.get("/api/threads")
    assert list_res.status_code == 200
    threads = list_res.json()["threads"]
    assert any(t["thread_id"] == thread_id for t in threads)

    # 3. Delete thread
    del_res = client.delete(f"/api/threads/{thread_id}")
    assert del_res.status_code == 200
    print("✅ Chat threads CRUD PASSED")

def test_crag_upload_api():
    print("Testing /api/upload-doc (C-RAG Document Indexing)...")
    sample_content = (
        "OFFICIAL ACADEMIC TRANSCRIPT\n"
        "Student Name: John Doe\n"
        "Major: Computer Science\n"
        "Cumulative Grade Point Average (CGPA): 3.75 / 4.00\n"
        "Overall IELTS Band: 7.5\n"
        "Completed 140 credit hours in Algorithms, Data Structures, Operating Systems, Machine Learning.\n"
    )
    file_bytes = io.BytesIO(sample_content.encode("utf-8"))
    
    response = client.post(
        "/api/upload-doc",
        data={"session_id": "test_session_crag_99"},
        files={"file": ("transcript.txt", file_bytes, "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["profile_hints"]["detected_gpa"] == "3.75"
    assert data["profile_hints"]["detected_ielts"] == 7.5
    print("✅ /api/upload-doc C-RAG PASSED: Profile hints extracted successfully:", data["profile_hints"])

def test_hitl_action_api():
    print("Testing /api/hitl-action...")
    res = client.post("/api/hitl-action", json={
        "thread_id": "test_thread_hitl_1",
        "decision": "approved_include_safety",
        "notes": "Student approved adding backup safety options."
    })
    assert res.status_code == 200
    assert res.json()["success"] is True
    print("✅ /api/hitl-action PASSED")

def test_streaming_api():
    print("Testing /api/chat/stream SSE...")
    req = {
        "message": "Find tuition free MSc in Germany with PR and jobs",
        "thread_id": "stream_test_thread",
        "session_id": "stream_test_thread",
        "degree_level": "MSc",
        "subject": "Data Science",
        "country": "Germany",
        "user_gpa": 3.4,
        "user_ielts": 6.5,
        "budget_usd": 15000
    }
    with client.stream("POST", "/api/chat/stream", json=req) as response:
        assert response.status_code == 200
        event_count = 0
        for line in response.iter_lines():
            if line:
                event_count += 1
                if event_count > 5:
                    break
        assert event_count >= 5
    print(f"✅ /api/chat/stream PASSED (received {event_count} stream chunks)")

def test_full_agent_finder_api():
    print("Testing /api/find full pipeline...")
    req_body = {
        "message": "Find MSc Artificial Intelligence in Germany under $15000 budget with PR and job opportunities",
        "degree_level": "MSc",
        "subject": "Artificial Intelligence",
        "country": "Germany",
        "user_gpa": 3.5,
        "user_ielts": 7.0,
        "budget_usd": 15000
    }
    response = client.post("/api/find", json=req_body)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "dossier" in data and len(data["dossier"]) > 500
    print("✅ /api/find pipeline PASSED")

if __name__ == "__main__":
    print("\n================ STARTING FULL VERIFICATION ================\n")
    test_health()
    test_home_page()
    test_opportunities_api()
    test_threads_api()
    test_crag_upload_api()
    test_hitl_action_api()
    test_streaming_api()
    test_full_agent_finder_api()
    print("\n🎉 ALL ADVANCED SYSTEM TESTS PASSED SUCCESSFULLY!\n")
