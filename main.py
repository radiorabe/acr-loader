"""
Stores daily data from ACRCloud's broadcast monitoring service in ownCloud.
"""
from datetime import datetime, timedelta
from logging import getLogger
from functools import cache
import os
import json

from acrclient import Client as ACRClient
from acrclient.models import GetBmCsProjectsResultsParams
from configargparse import ArgParser  # type: ignore
from owncloud import Client as OwnCloudClient  # type: ignore
from owncloud.owncloud import HTTPResponseError as OCResponseError  # type: ignore
from tqdm import tqdm


logger = getLogger(__name__)


def daterange(start_date, end_date) -> list[datetime]:
    dates = []
    for n in range(int((end_date - start_date).days)):
        dates.append(start_date + timedelta(n))
    return dates


@cache
def oc_mkdir(oc: OwnCloudClient, path: str) -> bool:
    print(path)
    try:
        return oc.mkdir(path)
    except OCResponseError as ex:  # pragma: no cover
        if str(ex) != "HTTP error: 405":
            logger.exception(ex)
        return True


@cache
def oc_file_exists(oc: OwnCloudClient, path: str):
    try:
        oc.file_info(path)
        return True
    except OCResponseError as ex:
        if str(ex) != "HTTP error: 404":  # pragma: no cover
            logger.exception(ex)
        return False


def check(oc: OwnCloudClient, oc_path: str) -> list[datetime]:
    """
    Checks ownCloud for missing files.
    """
    missing = []
    start = datetime(2023, 1, 1)
    for requested in tqdm(daterange(start, datetime.now()), desc="Checking ownCloud"):
        oc_mkdir(oc, oc_path)
        oc_mkdir(oc, os.path.join(oc_path, str(requested.year)))
        oc_mkdir(oc, os.path.join(oc_path, str(requested.year), str(requested.month)))
        status = oc_file_exists(
            oc,
            os.path.join(
                oc_path,
                str(requested.year),
                str(requested.month),
                requested.strftime("%Y-%m-%d.json"),
            ),
        )
        if not status:
            missing.append(requested)
    return missing


def fetch(
    missing: list[datetime],
    acr: ACRClient,
    oc: OwnCloudClient,
    acr_project_id: str,
    acr_stream_id: str,
    oc_path: str,
):
    """Fetches missing data from ACRCloud and stores it."""
    for requested in tqdm(missing, desc="Loading from ACRCloud"):
        target = os.path.join(
            oc_path,
            str(requested.year),
            str(requested.month),
            requested.strftime("%Y-%m-%d.json"),
        )
        data = acr.get_bm_cs_projects_results(
            project_id=int(acr_project_id),
            stream_id=acr_stream_id,
            params=GetBmCsProjectsResultsParams(
                type="day",
                date=requested.strftime("%Y%m%d"),
                min_duration=0,
                max_duration=3600,
                isrc_country="",
            ),
        )
        oc.put_file_contents(target, json.dumps(data))


def main():  # pragma: no cover
    p = ArgParser(
        description=__doc__,
        default_config_files=[
            "/etc/acrloader.conf",
            "~/.acrloader.conf",
            "acrloader.conf",
        ],
    )
    p.add(
        "-c",
        "--my-config",
        is_config_file=True,
        help="config file path",
    )
    p.add(
        "--acr-bearer-token",
        required=True,
        env_var="ACR_BEARER_TOKEN",
        help="ACRCloud bearer token",
    )
    p.add(
        "--acr-project-id",
        required=True,
        env_var="ACR_PROJECT_ID",
        help="ACRCloud project id",
    )
    p.add(
        "--acr-stream-id",
        required=True,
        env_var="ACR_STREAM_ID",
        help="ACRCloud stream id",
    )
    p.add(
        "--oc-url",
        default="https://share.rabe.ch",
        env_var="OC_URL",
        help="ownCloud URL",
    )
    p.add(
        "--oc-user",
        required=True,
        env_var="OC_USER",
        help="ownCloud user",
    )
    p.add(
        "--oc-pass",
        required=True,
        env_var="OC_PASS",
        help="ownCloud pass",
    )
    p.add(
        "--oc-path",
        default="IT/Share/ACRCloud Data",
        env_var="OC_PATH",
        help="ownCloud path",
    )
    options = p.parse_args()

    # figure out what we are missing on ownCloud
    oc = OwnCloudClient(options.oc_url)
    oc.login(options.oc_user, options.oc_pass)
    missing = check(oc=oc, start=datetime(2023, 1, 1), oc_path=options.oc_path)

    # return early if no files are missing
    if not missing:
        return

    # fetch and store missing data
    acr_client = ACRClient(
        bearer_token=options.acr_bearer_token,
    )
    fetch(
        missing,
        acr=acr_client,
        oc=oc,
        acr_project_id=options.acr_project_id,
        acr_stream_id=options.acr_stream_id,
        oc_path=options.oc_path,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
