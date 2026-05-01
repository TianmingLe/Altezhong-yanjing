import importlib
import json
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "omi" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def _install_fake_google_modules(monkeypatch):
    calls = {"client": []}

    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    firestore = types.ModuleType("google.cloud.firestore")

    class AnonymousCredentials:
        pass

    def Client(*args, **kwargs):
        calls["client"].append({"args": args, "kwargs": kwargs})
        return {"fake_db": True, "args": args, "kwargs": kwargs}

    firestore.Client = Client
    cloud.firestore = firestore
    google.cloud = cloud

    auth = types.ModuleType("google.auth")
    credentials = types.ModuleType("google.auth.credentials")
    credentials.AnonymousCredentials = AnonymousCredentials
    auth.credentials = credentials
    google.auth = auth

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", firestore)
    monkeypatch.setitem(sys.modules, "google.auth", auth)
    monkeypatch.setitem(sys.modules, "google.auth.credentials", credentials)

    return calls, AnonymousCredentials


def _reload_client_module(monkeypatch):
    mod_name = "database._client"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    if "database" in sys.modules:
        del sys.modules["database"]
    return importlib.import_module(mod_name)


def test_emulator_path_uses_anonymous_credentials(tmp_path, monkeypatch):
    calls, AnonymousCredentials = _install_fake_google_modules(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIRESTORE_PROJECT_ID", "demo-project")
    monkeypatch.delenv("OMI_DEMO", raising=False)

    mod = _reload_client_module(monkeypatch)
    assert calls["client"]
    kwargs = calls["client"][0]["kwargs"]
    assert kwargs.get("project") == "demo-project"
    assert isinstance(kwargs.get("credentials"), AnonymousCredentials)
    assert not (tmp_path / "google-credentials.json").exists()
    assert mod.db["fake_db"] is True


def test_demo_path_returns_mock_firestore(tmp_path, monkeypatch):
    _install_fake_google_modules(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.setenv("OMI_DEMO", "1")

    mod = _reload_client_module(monkeypatch)
    assert hasattr(mod.db, "collection")
    assert mod.get_users_uid() == []
    assert not (tmp_path / "google-credentials.json").exists()


def test_prod_path_keeps_service_account_write(tmp_path, monkeypatch):
    calls, _ = _install_fake_google_modules(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("OMI_DEMO", raising=False)
    monkeypatch.setenv("SERVICE_ACCOUNT_JSON", json.dumps({"type": "service_account"}))

    mod = _reload_client_module(monkeypatch)
    assert (tmp_path / "google-credentials.json").exists()
    assert calls["client"]
    assert mod.db["fake_db"] is True

