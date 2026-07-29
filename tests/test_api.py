from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_and_cases():
    assert client.get('/health').json()['status'] == 'ok'
    assert len(client.get('/api/cases').json()) == 4

def test_deterministic_run_has_evidence():
    response = client.post('/api/runs', json={'mode': 'demo'})
    body = response.json()
    assert response.status_code == 200
    assert body['pass_rate'] == 1
    assert {'latency_ms', 'review_status', 'output'} <= body['results'][0].keys()
