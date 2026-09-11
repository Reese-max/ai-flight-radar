"""Fail-closed deployment configuration; no network or real cloud resources."""
import pytest
from deploy import start


@pytest.mark.parametrize('mode', ['publc', 'development', ''])
def test_unknown_mode_cannot_disable_auth(monkeypatch, mode):
    monkeypatch.setenv('DEPLOYMENT_MODE', mode)
    with pytest.raises(RuntimeError, match='DEPLOYMENT_MODE'):
        start.prepare()


@pytest.mark.parametrize('key', ['', 'short', ' '*64])
def test_public_requires_real_secret(monkeypatch, key):
    monkeypatch.setenv('DEPLOYMENT_MODE', 'public')
    monkeypatch.setenv('API_KEY', key)
    with pytest.raises(RuntimeError, match='API_KEY'):
        start.prepare()


def test_railway_requires_real_runtime_mount(monkeypatch, tmp_path):
    monkeypatch.setenv('DEPLOYMENT_MODE', 'public')
    monkeypatch.setenv('API_KEY', 'x'*40)
    monkeypatch.setenv('DB_PATH', str(tmp_path/'flights.db'))
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_ID', 'synthetic-test-environment')
    monkeypatch.delenv('RAILWAY_VOLUME_MOUNT_PATH', raising=False)
    with pytest.raises(RuntimeError, match='persistent Railway volume'):
        start.prepare()


def test_runtime_port_and_unprivileged_directory(monkeypatch, tmp_path):
    monkeypatch.setenv('DEPLOYMENT_MODE', 'public')
    monkeypatch.setenv('API_KEY', 'x'*40)
    monkeypatch.setenv('DB_PATH', str(tmp_path/'flights.db'))
    monkeypatch.setenv('PORT', '9090')
    monkeypatch.delenv('RAILWAY_ENVIRONMENT_ID', raising=False)
    monkeypatch.delenv('RAILWAY_VOLUME_MOUNT_PATH', raising=False)
    monkeypatch.setattr(start.os, 'geteuid', lambda: 10001)
    assert start.prepare() == 9090
