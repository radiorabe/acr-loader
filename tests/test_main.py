from datetime import datetime
from unittest.mock import ANY, call, patch

import pytest
from minio.error import S3Error  # type: ignore[import-untyped]
from owncloud.owncloud import HTTPResponseError  # type: ignore[import-untyped]

import main


@pytest.mark.freeze_time("2023-01-08")
@patch("owncloud.Client")
def test_oc_check_files_exist(oc_client):
    oc = oc_client()
    missing = main.oc_check(oc=oc, oc_path="/tmp/test")
    assert oc_client.called
    mkdir_calls = [
        call("/tmp/test"),
        call("/tmp/test/2023"),
        call("/tmp/test/2023/1"),
    ]
    oc.mkdir.assert_has_calls(mkdir_calls)

    oc.file_info.assert_has_calls(
        [call(f"/tmp/test/2023/1/2023-01-0{x}.json") for x in range(1, 8)],
    )
    assert missing == []


@pytest.mark.freeze_time("2023-01-08")
@patch("owncloud.Client")
def test_oc_check_files_missing(oc_client):
    oc = oc_client()
    oc.file_info.side_effect = HTTPResponseError(
        type("", (object,), {"status_code": 404})(),
    )
    missing = main.oc_check(oc=oc, oc_path="/tmp/test")
    oc.file_info.assert_has_calls(
        [call(f"/tmp/test/2023/1/2023-01-0{x}.json") for x in range(1, 8)],
    )
    assert len(missing) == 7  # noqa: PLR2004


@pytest.mark.freeze_time("2023-01-08")
@patch("acrclient.Client")
@patch("owncloud.Client")
def test_oc_fetch(oc_client, acr_client):
    oc = oc_client()
    acr = acr_client()

    acr.get_bm_cs_projects_results.return_value = "JSON"

    main.oc_fetch(
        [datetime(2023, 1, 1)],
        acr=acr,
        oc=oc,
        acr_project_id=1,
        acr_stream_id="asdf",
        oc_path="/tmp/test",
    )
    oc.put_file_contents.assert_called_with(
        "/tmp/test/2023/1/2023-01-01.json",
        '"JSON"',
    )


@pytest.mark.freeze_time("2023-01-08")
@patch("minio.Minio")
def test_mc_check_files_exist(mc_client):
    mc = mc_client()
    missing = main.mc_check(mc=mc, bucket="acrcloud.raw")
    assert mc_client.called
    mc.stat_object.assert_has_calls(
        [call("acrcloud.raw", f"2023-01-0{x}.json") for x in range(1, 8)],
    )
    assert missing == []


@pytest.mark.freeze_time("2023-01-08")
@patch("minio.Minio")
def test_mc_check_files_missing(mc_client):
    mc = mc_client()
    mc.stat_object.side_effect = S3Error(
        code="NoSuchKey",
        message="",
        resource=None,
        request_id=None,
        host_id=None,
        response=None,
    )
    missing = main.mc_check(mc=mc, bucket="acrcloud.raw")
    assert mc_client.called
    mc.stat_object.assert_has_calls(
        [call("acrcloud.raw", f"2023-01-0{x}.json") for x in range(1, 8)],
    )
    assert len(missing) == 7  # noqa: PLR2004


@pytest.mark.freeze_time("2023-01-08")
@patch("acrclient.Client")
@patch("minio.Minio")
def test_mc_fetch(mc_client, acr_client):
    mc = mc_client()
    acr = acr_client()

    acr.get_bm_cs_projects_results.return_value = "JSON"

    main.mc_fetch(
        [datetime(2023, 1, 1)],
        acr=acr,
        mc=mc,
        acr_project_id=1,
        acr_stream_id="asdf",
        bucket="acrcloud.raw",
    )
    mc.put_object.assert_called_with(
        "acrcloud.raw",
        "2023-01-01.json",
        ANY,
        length=6,
        content_type="application/json",
    )
