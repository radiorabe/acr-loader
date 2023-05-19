from datetime import datetime

from unittest.mock import patch, call
from pytest import mark

# from owncloud import Client as OwnCloudClient
from owncloud.owncloud import HTTPResponseError as OCResponseError  # type: ignore

import main


@mark.freeze_time("2023-01-08")
@patch("owncloud.Client")
def test_check_files_exist(oc_client):
    oc = oc_client()
    missing = main.check(oc=oc, oc_path="/tmp/test")
    assert oc_client.called
    mkdir_calls = [
        call("/tmp/test"),
        call("/tmp/test/2023"),
        call("/tmp/test/2023/1"),
    ]
    oc.mkdir.assert_has_calls(mkdir_calls)

    oc.file_info.assert_has_calls(
        [call(f"/tmp/test/2023/1/2023-01-0{x}.json") for x in range(1, 8)]
    )
    assert missing == []


@mark.freeze_time("2023-01-08")
@patch("owncloud.Client")
def test_check_files_missing(oc_client):
    oc = oc_client()
    oc.file_info.side_effect = OCResponseError(
        type("", (object,), {"status_code": 404})()
    )
    missing = main.check(oc=oc, oc_path="/tmp/test")
    oc.file_info.assert_has_calls(
        [call(f"/tmp/test/2023/1/2023-01-0{x}.json") for x in range(1, 8)]
    )
    assert len(missing) == 7


@mark.freeze_time("2023-01-08")
@patch("acrclient.Client")
@patch("owncloud.Client")
def test_fetch(oc_client, acr_client):
    oc = oc_client()
    acr = acr_client()

    acr.get_bm_cs_projects_results.return_value = "JSON"

    main.fetch(
        [datetime(2023, 1, 1)],
        acr=acr,
        oc=oc,
        acr_project_id=1,
        acr_stream_id="asdf",
        oc_path="/tmp/test",
    )
    oc.put_file_contents.assert_called_with(
        "/tmp/test/2023/1/2023-01-01.json", '"JSON"'
    )
