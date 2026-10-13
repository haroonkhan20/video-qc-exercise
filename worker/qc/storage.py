"""Explicit service credentials from pod environment; never logged or written."""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import psycopg
from psycopg.types.json import Jsonb
from qc.model import canonical, run_prefix, validate_digest, version

RAW_BUCKET="qc-raw"
DERIVED_BUCKET="qc-derived"
CACHE=Path(os.environ.get("QC_CACHE","/cache"))
_LOCKS={}
_LOCKS_GUARD=threading.Lock()

def config():
    return json.loads(Path(os.environ.get("QC_CONFIG","/app/config/qc.json")).read_text())

def code_version():
    return os.environ.get("QC_CODE_VERSION","development")

def s3():
    return boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT","http://minio:9000"),
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],region_name="us-east-1",
        config=Config(signature_version="s3v4", retries={"max_attempts":5,"mode":"standard"}))

from functools import lru_cache
from psycopg_pool import ConnectionPool
@lru_cache(maxsize=1)
def pg_pool():
    return ConnectionPool(conninfo="",kwargs={
        "host":"postgres","dbname":"postgres","user":"postgres",
        "password":os.environ["POSTGRES_PASSWORD"],"connect_timeout":10,
        "options":"-c statement_timeout=30000"},
        min_size=1,max_size=2,num_workers=1,timeout=30)
@contextmanager
def pg():
    with pg_pool().connection() as connection:
        yield connection

def ch(sql, data=b"", token=None):
    query={"query":sql}
    if token:
        query.update({"insert_deduplicate":"1","insert_deduplication_token":token})
    url="http://clickhouse:8123/?"+urlencode(query)
    credentials=base64.b64encode(("default:"+os.environ["CLICKHOUSE_PASSWORD"]).encode()).decode()
    request=Request(url,data=data,headers={"Authorization":"Basic "+credentials},method="POST")
    with urlopen(request,timeout=120) as response:
        return response.read()

def setup():
    client=s3()
    for bucket, locked in [(RAW_BUCKET,True),(DERIVED_BUCKET,False)]:
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            if exc.response["ResponseMetadata"]["HTTPStatusCode"]!=404:raise
            client.create_bucket(Bucket=bucket,**({"ObjectLockEnabledForBucket":True} if locked else {}))
    client.put_object_lock_configuration(Bucket=RAW_BUCKET,ObjectLockConfiguration={
        "ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"COMPLIANCE","Days":36500}}})
    with pg() as db:
        db.execute(Path("/app/sql/postgres.sql").read_text())
    ch(Path("/app/sql/clickhouse.sql").read_text())
    return {"raw_bucket":RAW_BUCKET,"derived_bucket":DERIVED_BUCKET}

def put_json(key, value):
    s3().put_object(Bucket=DERIVED_BUCKET,Key=key,Body=canonical(value),ContentType="application/json")
    return key
def get_json(key):
    return json.loads(s3().get_object(Bucket=DERIVED_BUCKET,Key=key)["Body"].read())
def upload_derived(path,key,content_type="application/octet-stream"):
    with Path(path).open("rb") as stream:
        s3().put_object(Bucket=DERIVED_BUCKET,Key=key,Body=stream,ContentType=content_type)
    return key
def heartbeat(details):
    from temporalio import activity
    if activity.in_activity():activity.heartbeat(details)

def raw_path(ref):
    digest=validate_digest(ref["digest"])
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/(digest+".mcap")
    with _LOCKS_GUARD:lock=_LOCKS.setdefault(digest,threading.Lock())
    with lock:
        if path.exists():return path
        partial=CACHE/(digest+".download")
        response=s3().get_object(Bucket=RAW_BUCKET,Key="raw/"+digest+".mcap")
        checksum=hashlib.sha256();last=0
        with partial.open("wb") as output:
            while True:
                block=response["Body"].read(1024*1024)
                if not block:break
                checksum.update(block);output.write(block)
                if time.monotonic()-last>2:
                    heartbeat({"stage":"download","digest":digest});last=time.monotonic()
        if checksum.hexdigest()!=digest:raise ValueError("Raw digest mismatch")
        partial.replace(path)
        return path

def ingest(stream, digest, filename):
    validate_digest(digest);CACHE.mkdir(parents=True,exist_ok=True)
    import uuid
    target=CACHE/(digest+".ingest-"+uuid.uuid4().hex)
    checksum=hashlib.sha256();size=0
    with target.open("wb") as output:
        while True:
            block=stream.read(1024*1024)
            if not block:break
            checksum.update(block);size+=len(block);output.write(block)
    if checksum.hexdigest()!=digest:raise ValueError("Upload bytes do not match requested digest")
    client=s3();key="raw/"+digest+".mcap"
    try:
        with target.open("rb") as body:
            client.put_object(Bucket=RAW_BUCKET,Key=key,Body=body,IfNoneMatch="*",
                              Metadata={"sha256":digest},ContentType="application/octet-stream")
        created=True
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] not in (409,412):raise
        existing=client.head_object(Bucket=RAW_BUCKET,Key=key)
        if existing["ContentLength"]!=size or existing.get("Metadata",{}).get("sha256")!=digest:
            raise ValueError("Existing raw object metadata mismatch")
        created=False
    with pg() as db:
        db.execute("INSERT INTO qc_episodes(digest,byte_size,raw_key) VALUES(%s,%s,%s) ON CONFLICT(digest) DO NOTHING",(digest,size,key))
        db.execute("INSERT INTO qc_aliases(digest,filename) VALUES(%s,%s) ON CONFLICT DO NOTHING",(digest,filename))
    target.replace(CACHE/(digest+".mcap"))
    return {"digest":digest,"bytes":size,"raw_key":key,"uploaded":created}

def ref_for(digest):
    cfg=config()
    ref={"digest":validate_digest(digest),"config_version":version(cfg),"code_version":code_version()}
    with pg() as db:
        db.execute("INSERT INTO qc_runs(digest,config_version,code_version,config) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                   (digest,ref["config_version"],ref["code_version"],Jsonb(cfg)))
    return ref
def run_config(ref):
    with pg() as db:
        row=db.execute("SELECT config FROM qc_runs WHERE digest=%s AND config_version=%s AND code_version=%s",
                       (ref["digest"],ref["config_version"],ref["code_version"])).fetchone()
    if not row:raise ValueError("Missing run/config")
    return row[0]
