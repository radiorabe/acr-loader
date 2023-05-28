"""
Stores daily data from ACRCloud's broadcast monitoring service in ownCloud.
"""
import json
import os
from datetime import datetime, timedelta
from functools import cache
from io import BytesIO
from logging import getLogger

import urllib3
from acrclient import Client as ACRClient
from acrclient.models import GetBmCsProjectsResultsParams
from configargparse import ArgParser  # type: ignore
from minio import Minio  # type: ignore
from minio.error import S3Error  # type: ignore
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


def oc_check(oc: OwnCloudClient, oc_path: str) -> list[datetime]:
    """
    Checks ownCloud for missing files.
    """
    missing = []
    start = datetime.now() - timedelta(7)
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


def mc_check(mc: Minio, bucket: str) -> list[datetime]:
    """
    Checks MinIO for missing files.
    """
    missing = []
    start = datetime.now() - timedelta(7)
    for requested in tqdm(daterange(start, datetime.now()), desc="Checking MinIO"):
        try:
            mc.stat_object(bucket, requested.strftime("%Y-%m-%d.json"))
        except S3Error as ex:
            if ex.code == "NoSuchKey":
                missing.append(requested)
    return missing


@cache
def fetch_one(
    acr: ACRClient,
    acr_project_id: str,
    acr_stream_id: str,
    requested: str,
):
    return acr.get_bm_cs_projects_results(
        project_id=int(acr_project_id),
        stream_id=acr_stream_id,
        params=GetBmCsProjectsResultsParams(
            type="day",
            date=requested,
            min_duration=0,
            max_duration=3600,
            isrc_country="",
        ),
    )


def oc_fetch(
    missing: list[datetime],
    acr: ACRClient,
    oc: OwnCloudClient,
    acr_project_id: str,
    acr_stream_id: str,
    oc_path: str,
):
    """Fetches missing data from ACRCloud and stores it in ownCloud."""
    for requested in tqdm(missing, desc="Loading into ownCloud from ACRCloud"):
        target = os.path.join(
            oc_path,
            str(requested.year),
            str(requested.month),
            requested.strftime("%Y-%m-%d.json"),
        )
        oc.put_file_contents(
            target,
            json.dumps(
                fetch_one(
                    acr=acr,
                    acr_project_id=acr_project_id,
                    acr_stream_id=acr_stream_id,
                    requested=requested.strftime("%Y%m%d"),
                )
            ),
        )


def mc_fetch(
    missing: list[datetime],
    acr: ACRClient,
    mc: Minio,
    acr_project_id: str,
    acr_stream_id: str,
    bucket: str,
):
    """Fetches missing data from ACRCloud and stores it in MinIO."""
    for requested in tqdm(missing, desc="Loading into MinIO from ACRCloud"):
        _as_bytes = json.dumps(
            fetch_one(
                acr=acr,
                acr_project_id=acr_project_id,
                acr_stream_id=acr_stream_id,
                requested=requested.strftime("%Y%m%d"),
            )
        ).encode("utf-8")
        mc.put_object(
            bucket,
            requested.strftime("%Y-%m-%d.json"),
            BytesIO(_as_bytes),
            length=len(_as_bytes),
            content_type="application/json",
        )


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
        "--oc",
        default=False,
        action="store_true",
        env_var="OC_ENABLE",
        help="Enable ownCloud",
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
    p.add(
        "--minio",
        default=False,
        action="store_true",
        env_var="MINIO_ENABLE",
        help="Enable MinIO",
    )
    p.add(
        "--minio-url",
        default="minio.service.int.rabe.ch:9000",
        env_var="MINIO_HOST",
        help="MinIO Hostname",
    )
    p.add(
        "--minio-secure",
        default=True,
        env_var="MINIO_SECURE",
        help="MinIO Secure param",
    )
    p.add(
        "--minio-cert-reqs",
        default="CERT_REQUIRED",
        env_var="MINIO_CERT_REQS",
        help="cert_reqs for urlib3.PoolManager used by MinIO",
    )
    p.add(
        "--minio-ca-certs",
        default="/etc/pki/ca-trust/extracted/openssl/ca-bundle.trust.crt",
        env_var="MINIO_CA_CERTS",
        help="ca_certs for urlib3.PoolManager used by MinIO",
    )
    p.add(
        "--minio-bucket",
        default="acrcloud.raw",
        env_var="MINIO_BUCKET",
        help="MinIO Bucket Name",
    )
    p.add(
        "--minio-access-key",
        default=None,
        env_var="MINIO_ACCESS_KEY",
        help="MinIO Access Key",
    )
    p.add(
        "--minio-secret-key",
        default=None,
        env_var="MINIO_SECRET_KEY",
        help="MinIO Secret Key",
    )
    options = p.parse_args()
    acr_client = ACRClient(
        bearer_token=options.acr_bearer_token,
    )

    if options.oc:
        # figure out what we are missing on ownCloud
        oc = OwnCloudClient(options.oc_url)
        oc.login(options.oc_user, options.oc_pass)
        missing = oc_check(oc=oc, oc_path=options.oc_path)

        if missing:
            # fetch and store missing data
            oc_fetch(
                missing,
                acr=acr_client,
                oc=oc,
                acr_project_id=options.acr_project_id,
                acr_stream_id=options.acr_stream_id,
                oc_path=options.oc_path,
            )

    if options.minio:
        mc = Minio(
            options.minio_url,
            options.minio_access_key,
            options.minio_secret_key,
            secure=options.minio_secure,
            http_client=urllib3.PoolManager(
                cert_reqs=options.minio_cert_reqs, ca_certs=options.minio_ca_certs
            ),
        )
        if not mc.bucket_exists(options.minio_bucket):
            mc.make_bucket(options.minio_bucket)
        missing = mc_check(mc=mc, bucket=options.minio_bucket)

        if missing:
            # fetch and store missing data
            mc_fetch(
                missing,
                acr=acr_client,
                mc=mc,
                acr_project_id=options.acr_project_id,
                acr_stream_id=options.acr_stream_id,
                bucket=options.minio_bucket,
            )


if __name__ == "__main__":  # pragma: no cover
    main()
