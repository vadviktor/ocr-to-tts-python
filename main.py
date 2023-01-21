import argparse
import os
from sys import argv
from time import sleep
from typing import Optional

import boto3


def list_existing(bucket, prefix) -> list:
    keys = []
    for obj in bucket.objects.filter(Delimiter="/", Prefix=f"{prefix}/"):
        keys.append(obj.key)

    return keys


def delete_existing(bucket, prefix):
    keys_to_delete = list_existing(bucket, prefix)

    if len(keys_to_delete) > 0:
        bucket.delete_objects(Delete={"Objects": [{"Key": k} for k in keys_to_delete]})


def upload_pages(client, local_path, bucket, prefix):
    s3_waiter = client.get_waiter("object_exists")
    with os.scandir(local_path) as page_files:
        page_file: os.DirEntry
        for page_file in page_files:
            if not page_file.is_file() or page_file.name == ".gitignore":
                continue

            print(f"uploading {page_file.name}")

            data = open(page_file.path, "rb")
            key = f"{prefix}/{page_file.name}"
            bucket.put_object(Key=key, Body=data)
            s3_waiter.wait(Bucket=bucket.name, Key=key)


def extract_text(session, bucket, prefix) -> Optional[str]:
    s3_client = session.client("s3")
    textract_client = session.client("textract")
    pages_to_read = list_existing(bucket, prefix)

    if len(pages_to_read) == 0:
        return

    all_lines = []
    for key in pages_to_read:
        lines = []
        response = textract_client.detect_document_text(
            Document={"S3Object": {"Bucket": bucket.name, "Name": key}}
        )

        for item in response["Blocks"]:
            if item["BlockType"] == "LINE":
                lines.append(item["Text"])

        store_text_in_s3(
            client=s3_client,
            bucket=s3_bucket,
            key=f"{key}.txt",
            text=" ".join(lines),
        )
        all_lines.extend(lines)

    return " ".join(all_lines)


def store_text_in_s3(client, bucket, key, text: str):
    print(f"storing {key} in s3")
    bucket.put_object(Key=key, Body=text.encode("utf-8"))
    s3_waiter = client.get_waiter("object_exists")
    s3_waiter.wait(Bucket=bucket.name, Key=key)


def synthesize_text(client, bucket, prefix, text):
    response = client.start_speech_synthesis_task(
        Engine="neural",
        LanguageCode="en-GB",
        OutputFormat="ogg_vorbis",
        OutputS3BucketName=bucket.name,
        OutputS3KeyPrefix=prefix,
        Text=text,
        TextType="text",
        VoiceId="Amy",
    )

    task_id = response.get("SynthesisTask", {}).get("TaskId")
    status = "scheduled"
    while status not in ["completed", "failed"]:
        status = (
            client.get_speech_synthesis_task(TaskId=task_id)
            .get("SynthesisTask", {})
            .get("TaskStatus")
        )
        print(status)
        sleep(3)

    print(
        client.get_speech_synthesis_task(TaskId=task_id)
        .get("SynthesisTask", {})
        .get("TaskStatusReason")
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("bucket")
    parser.add_argument("prefix")
    parser.add_argument("directory")

    print(parser)

    if len(argv) != 5:
        parser.print_help()
        exit(1)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    AWS_PROFILE = args.profile
    AWS_BUCKET = args.bucket
    AWS_PREFIX_KEY = args.prefix
    PAGES_DIR = args.directory

    session = boto3.Session(profile_name=AWS_PROFILE)
    s3 = session.resource("s3")
    s3_bucket = s3.Bucket(AWS_BUCKET)

    print("deleting old images")
    delete_existing(s3_bucket, AWS_PREFIX_KEY)

    print("uploading new images")
    upload_pages(
        client=session.client("s3"),
        local_path=PAGES_DIR,
        bucket=s3_bucket,
        prefix=AWS_PREFIX_KEY,
    )

    print("extracting text")
    extracted_text = extract_text(
        session=session, bucket=s3_bucket, prefix=AWS_PREFIX_KEY
    )

    print("creating audio file")
    synthesize_text(
        client=session.client("polly"),
        bucket=s3_bucket,
        prefix=AWS_PREFIX_KEY,
        text=extracted_text,
    )

    print("finished")
