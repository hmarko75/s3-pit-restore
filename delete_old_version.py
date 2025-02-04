#!/usr/bin/env python3

import boto3 
import json
from datetime import datetime, timedelta, timezone
import argparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def delete_non_current_versions(endpoint:str, bucket_name:str, prefix:str='', days_threshold:int=30, simulate:bool=False):
   
    current_time = datetime.now(timezone.utc)
    skipped = list()

    s3client = boto3.client('s3', endpoint_url=endpoint, verify=False)
    paginator = s3client.get_paginator('list_object_versions')
    list_params = {
       'Bucket': bucket_name
    }
    for page in paginator.paginate(**list_params):
        versions = s3client.list_object_versions(Bucket=bucket_name)
        for version in page.get('Versions', []):
            key = version['Key']
            version_id = version['VersionId']
            is_latest = version['IsLatest']
            size = version['Size']
            last_modified = version['LastModified'].replace(tzinfo=timezone.utc)

            # Skip the current version as we only want to delete non-current versions
            if is_latest:
                continue
            if not key.startswith(prefix):
                continue

            age = current_time - last_modified
            if age > timedelta(days=days_threshold):
                try:
                        retention = s3client.get_object_retention(Bucket=bucket_name,Key=key,VersionId=version_id)
                        retention_period = retention['Retention']['RetainUntilDate']
                except:
                        retention_period = None

                if retention_period:
                        days_until_retnetion = current_time - retention_period
                        if days_until_retnetion.days < 0:
                            print(f"Skipping: s3://{bucket_name}/{key} (Version ID: {version['VersionId']}) Retention: {retention_period}")
                            skipped.append(key)
                            continue
                try:
                    if not simulate:
                        s3client.delete_object(Bucket=bucket_name, Key=key, VersionId=version_id)
                        print(f"Deleted: s3://{bucket_name}/{key} (Version ID: {version['VersionId']}) Size: {size} Modified Time: {last_modified} Delete Marker: False")
                    else:
                        print(f"SIMULATE Deleted: s3://{bucket_name}/{key} (Version ID: {version['VersionId']}) Size: {size} Modified Time: {last_modified} Delete Marker: False")
                except Exception as err:
                    print(f"Could Not Delete: s3://{bucket_name}/{key} (Version ID: {version['VersionId']}) Modified Time: {last_modified} Delete Marker: False Error: {err}")
    
    for page in paginator.paginate(**list_params):  
        for version in versions.get('DeleteMarkers', []):
            key = version['Key']
            version_id = version['VersionId']
            last_modified = version['LastModified'].replace(tzinfo=timezone.utc)
            age = current_time - last_modified

            if not key.startswith(prefix):
                continue
            
            if age > timedelta(days=days_threshold):
                try:
                    retention = s3client.get_object_retention(Bucket=bucket_name,Key=key,VersionId=version_id)
                    retention_period = retention['Retention']['RetainUntilDate']
                except:
                    retention_period = None
                
                if retention_period:
                    days_until_retnetion = current_time - retention_period
                    if days_until_retnetion.days < 0:
                        print(f"Skipping: s3://{bucket_name}/{key} (Version ID: {version['VersionId']}) Retention: {retention_period}")
                        continue
                
                if key in skipped:
                    continue
                try:
                    if not simulate:
                        s3client.delete_object(Bucket=bucket_name, Key=key, VersionId=version['VersionId'])
                        print(f"Deleted: s3://{bucket_name}/{key} (Version ID: {version_id}) Modified Time: {last_modified} Delete Marker: True")
                    else:
                        print(f"SIMULATE Deleted: s3://{bucket_name}/{key} (Version ID: {version_id}) Modified Time: {last_modified} Delete Marker: True")

                except Exception as err:
                    print(f"Failed to delete: s3://{bucket_name}/{key} (Version ID: {version_id}) Modified Time: {last_modified} Delete Marker: True Error: {err}")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', help='s3 bucket', required=True)
    parser.add_argument('-p', '--prefix', help='prefix', required=False, default='')
    parser.add_argument('-e', '--endpoint', help='s3 endpoint url', required=True)
    parser.add_argument('-d', '--days', help='delete objects version older than', required=True, type=int)
    parser.add_argument('-s', '--simulate', help='simulate only', required=False, default=False,action='store_true')
    args = parser.parse_args()
    
    bucket_name = args.bucket 
    days_threshold = args.days
    endpoint = args.endpoint
    prefix = args.prefix
    simulate = args.simulate

    try:
        delete_non_current_versions(endpoint=endpoint, bucket_name=bucket_name, prefix=prefix, days_threshold=days_threshold, simulate=simulate)
    except Exception as err:
        print(f"Error: {err}")    

if __name__ == "__main__":
    main()

