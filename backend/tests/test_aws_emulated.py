"""AWS layer against LocalStack (skipped automatically when the emulator is down)."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import boto3
import pytest

from tests.conftest import requires_localstack

EP = "http://localhost:4566"
REGION = "ap-south-1"


def _c(svc):
    return boto3.client(svc, endpoint_url=EP, region_name=REGION, aws_access_key_id="test",
                        aws_secret_access_key="test")


@requires_localstack
def test_secret_roundtrip_via_vault(monkeypatch):
    _c("secretsmanager").put_secret_value(SecretId="repurpora/app",
                                          SecretString=json.dumps({"UNIT_TEST_SECRET": "s3cr3t-value-123"}))
    monkeypatch.setenv("AWS_ENDPOINT_URL", EP)
    from repurpora import vault
    from repurpora.settings import get_settings

    get_settings.cache_clear()
    vault._CACHE.update({"data": None, "at": 0})
    assert vault.get_secret("UNIT_TEST_SECRET") == "s3cr3t-value-123"
    # restore the bootstrap secret afterwards
    subprocess.run(["docker", "compose", "run", "--rm", "aws-bootstrap"], cwd=Path(__file__).parents[2],
                   capture_output=True, check=False)


@requires_localstack
def test_report_mirror_to_s3(monkeypatch):
    monkeypatch.setenv("AWS_ENDPOINT_URL", EP)
    from repurpora.report.archive import upload_s3
    from repurpora.settings import get_settings

    get_settings.cache_clear()
    assert upload_s3("reports/test/unit.pdf", b"%PDF-1.4 test", "application/pdf")
    body = _c("s3").get_object(Bucket="repurpora-reports", Key="reports/test/unit.pdf")["Body"].read()
    assert body.startswith(b"%PDF")


@requires_localstack
def test_cloudwatch_audit_event(monkeypatch):
    monkeypatch.setenv("AWS_ENDPOINT_URL", EP)
    from repurpora import observability
    from repurpora.settings import get_settings

    get_settings.cache_clear()
    observability._cloudwatch({"event": "unit_test", "detail": {"ok": True}})
    events = _c("logs").filter_log_events(logGroupName="/repurpora/audit", filterPattern="unit_test")["events"]
    assert events


@requires_localstack
@pytest.mark.skipif(not shutil.which("aws") or not shutil.which("bash"), reason="aws cli / bash missing")
def test_ec2_provisioning_script_against_emulator():
    root = Path(__file__).parents[2]
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if git_bash.exists() else "bash"  # avoid WSL bash (does not inherit env)
    env = dict(os.environ, AWS_ENDPOINT_URL=EP, AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test",
               AWS_DEFAULT_REGION=REGION, OLLAMA_PROXY_TOKEN="unit-test-token")
    out = subprocess.run([bash, "infra/aws/ec2_ollama.sh"], cwd=root, env=env, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
    assert "instance=i-" in out.stdout
