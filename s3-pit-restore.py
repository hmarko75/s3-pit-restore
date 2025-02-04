#!/usr/bin/env python3
#
# MIT License
#
# s3-pit-restore, a point in time restore tool for Amazon S3
#
# Copyright (c) [2020] [Angelo Compagnucci]
#
# Author: Angelo Compagnucci <angelo.compagnucci@gmail.com>
#
# This software is forked from a unmaintained version of s3-pit-restore
# released with MIT license from Madisoft S.p.a.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import shutup;shutup.please()
import os, sys, time, signal, argparse, boto3, botocore, \
        unittest, concurrent.futures, shutil, uuid, time
from datetime import datetime, timezone
from dateutil.parser import parse
from s3transfer.manager import TransferConfig

args = None
executor = None
transfer = None
futures = {}
client = None

class TestS3PitRestore(unittest.TestCase):

    def generate_tree(self, path, contents):
        for i, content in enumerate(contents):
            folder_path = os.path.join(path, "folder%d" % i)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, "file%d" % i)

            with open(file_path, 'w') as outfile:
                outfile.write(content)
            print(file_path, content)

    def download_restored_file(self, path):
        base_path = os.path.basename(os.path.normpath(path))
        if args.dest_prefix:
            base_path = os.path.join(args.dest_prefix, base_path)

        s3 = boto3.resource('s3', endpoint_url=args.endpoint_url, verify=False)

        paginator = s3.meta.client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=args.dest_bucket, Prefix=base_path)
        with concurrent.futures.ThreadPoolExecutor(args.max_workers) as e:
            for page in page_iterator:
               for obj in page.get('Contents', []):
                  key_path = os.path.dirname(obj["Key"])
                  if key_path and not os.path.exists(key_path):
                      os.makedirs(key_path)
                  e.submit(s3.Bucket(args.dest_bucket).download_file(obj["Key"], obj["Key"]))

    def check_tree(self, path, contents):
        if args.dest_bucket is not None:
            self.download_restored_file(path)
            path = os.path.basename(os.path.normpath(path))
            if args.dest_prefix:
               path = os.path.join(args.dest_prefix, path)
        for i, content in enumerate(contents):
            folder_path = os.path.join(path, "folder%d" % i)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, "file%d" % i)
            in_content=""
            try:
               with open(file_path, 'r') as infile:
                  in_content = infile.read()
                  print(file_path, content, "==", in_content)
                  if in_content != content:
                      return False
            except:
               return False
        return True

    def upload_directory(self, resource, path, bucketname):
        with concurrent.futures.ThreadPoolExecutor(args.max_workers) as e:
            for root,dirs,files in os.walk(path):
               for f in files:
                  base_path = os.path.basename(os.path.normpath(path))
                  local_path = os.path.join(root, f)
                  relative_path = os.path.relpath(local_path, path)
                  s3_path = os.path.join(base_path, relative_path)
                  e.submit(resource.meta.client.upload_file, local_path, bucketname, s3_path)

    def delete_directory(self, resource, path):
        base_path = os.path.basename(os.path.normpath(path))
        paginator = resource.meta.client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=args.bucket, Prefix=base_path)
        with concurrent.futures.ThreadPoolExecutor(args.max_workers) as e:
            for page in page_iterator:
               delete_keys = {'Objects' : []}
               delete_keys['Objects'] = [{'Key' : k} for k in [obj['Key'] for obj in page.get('Contents', [])]]
               e.submit(resource.meta.client.delete_objects(Bucket=args.bucket, Delete=delete_keys))

    def remove_tree(self, path):
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)

    def check_versioning(self, s3):
        bucket_versioning = s3.BucketVersioning(args.bucket)
        bucket_versioning.load()

        print("Checking bucket versioning ... ", end='', flush=True)
        self.assertNotEqual(bucket_versioning.status, None)
        print("enabled!")

    def test_restore(self):
        contents_before = [ str(uuid.uuid4()) for n in range(2048) ]
        contents_after =  [ str(uuid.uuid4()) for n in range(2048) ]
        path = os.path.join(os.path.abspath(args.dest), "test-s3-pit-restore")
        s3 = boto3.resource('s3', endpoint_url=args.endpoint_url, verify=False)
        self.check_versioning(s3)

        print("Before ...")
        self.remove_tree(path)
        time.sleep(1)
        time_before = datetime.now(timezone.utc)
        time.sleep(1)
        self.generate_tree(path, contents_before)
        self.upload_directory(s3, path, args.bucket)
        self.remove_tree(path)

        print("Upload and owerwriting ...")
        time.sleep(1)
        time_after = datetime.now(timezone.utc)
        time.sleep(1)
        self.generate_tree(path, contents_after)
        self.upload_directory(s3, path, args.bucket)
        self.remove_tree(path)

        args.from_timestamp = str(time_before)
        args.timestamp = str(time_after)
        args.prefix = os.path.basename(os.path.normpath(path))
        do_restore()
        print("Restoring and checking ...")
        self.assertTrue(self.check_tree(path, contents_before))

    def test_dmarker_restore(self):
        content = [ str(uuid.uuid4()) for n in range(1) ]
        path = os.path.join(os.path.abspath(args.dest), "test-s3-pit-dmarker-restore")
        s3 = boto3.resource('s3', endpoint_url=args.endpoint_url, verify=False)
        self.check_versioning(s3)

        print("Before starting dmarker_restore test...")
        self.remove_tree(path)

        self.generate_tree(path, content)
        self.upload_directory(s3, path, args.bucket)
        self.remove_tree(path)

        time.sleep(1)
        time_before = datetime.now(timezone.utc)

        print("deleting ...")
        self.delete_directory(s3, path)
        args.timestamp = str(time_before)
        args.prefix = os.path.basename(os.path.normpath(path))
        do_restore()
        print("Restoring and checking for dmarker_restore test")
        self.assertTrue(self.check_tree(path, content))

def signal_handler(signal, frame):
    executor.shutdown(wait=False)
    for future in list(futures.keys()):
        if not future.running():
            future.cancel()
            futures.pop(future, None)
    print("Gracefully exiting ...")

def print_obj(obj, optional_message=""):
    if args.verbose:
        print('"%s" %s %s %s %s %s' % (obj["LastModified"], obj["VersionId"], obj["Size"], obj["StorageClass"], obj["Key"], optional_message))
    else:
        print(obj["Key"])

def handled_by_glacier(obj):
    if (obj["StorageClass"] == "DEEP_ARCHIVE" or obj["StorageClass"] == "GLACIER") and not args.enable_glacier:
        print_obj(obj, optional_message='needs restore')
        return True
    elif (obj["StorageClass"] == "DEEP_ARCHIVE" or obj["StorageClass"] == "GLACIER") and args.enable_glacier:
        s3 = boto3.resource('s3', endpoint_url=args.endpoint_url, verify=False)
        s3_obj = s3.Object(args.bucket, obj["Key"])
        if s3_obj.restore is None:
            print_obj(obj, optional_message='requesting')
            if not args.dry_run:
                try:
                    s3_obj.restore_object(VersionId=obj["VersionId"], RestoreRequest={'Days': 3},)
                except botocore.exceptions.ClientError as ex:
                    # sometimes s3_obj.restore returns None also if restore is in progress
                    pass
            return True
        # Print out objects whose restoration is on-going
        elif 'ongoing-request="true"' in s3_obj.restore:
            print_obj(obj, optional_message='in-progress')
            return True
        # Print out objects whose restoration is complete
        elif 'ongoing-request="false"' in s3_obj.restore:
            return False
    else:
        return False

def handled_by_standard(obj):
    if args.dry_run:
        print_obj(obj)
    else:
        if obj["Key"].endswith("/"):
            if not os.path.exists(obj["Key"]):
                os.makedirs(obj["Key"])
            return True
        key_path = os.path.dirname(obj["Key"])
        if key_path and not os.path.exists(key_path):
                os.makedirs(key_path)
        try:
            future = executor.submit(download_file, obj)
            global futures
            futures[future] = obj
        except RuntimeError:
            return False
    return True

def handled_by_copy(obj):
    if args.dry_run:
        print_obj(obj)
        return True
    future = executor.submit(s3_copy_object, obj)
    global futures
    futures[future] = obj
    return True

def download_file(obj):
    transfer.download_file(args.bucket, obj["Key"], obj["Key"], extra_args={"VersionId": obj["VersionId"]})
    unixtime = time.mktime(obj["LastModified"].timetuple())
    os.utime(obj["Key"],(unixtime, unixtime))

def get_key(obj):
    if not args.dest_prefix:
        return  obj["Key"]
    return os.path.join(args.dest_prefix, obj["Key"])

def s3_copy_object(obj):
    copy_source= {
        'Bucket': args.bucket,
        'Key': obj["Key"],
        'VersionId': obj["VersionId"]
    }

    extra_args = { }

    if args.sse is not None:
        extra_args['ServerSideEncryption'] = args.sse

    client.copy(Bucket=args.dest_bucket, CopySource=copy_source, Key=get_key(obj), ExtraArgs=extra_args)

def handled_by_delete(obj):
    if args.dry_run:
        print_obj(obj)
        return True
    future = executor.submit(s3_delete_object, obj)
    global futures
    futures[future] = obj
    return True

def s3_delete_object(obj):
    client.delete_object(Bucket=args.dest_bucket, Key=obj["Key"])

def do_restore():
    pit_start_date = (parse(args.from_timestamp) if args.from_timestamp else datetime.fromtimestamp(0, timezone.utc))
    pit_end_date = (parse(args.timestamp) if args.timestamp else datetime.now(timezone.utc))
    global client
    client = boto3.client('s3', endpoint_url=args.endpoint_url, verify=False)

    global transfer
    transfer = boto3.s3.transfer.S3Transfer(client)
    dest = args.dest
    last_obj = {}
    last_obj["Key"] = ""

    if args.debug: boto3.set_stream_logger('botocore')

    global executor
    executor = concurrent.futures.ThreadPoolExecutor(args.max_workers)

    # Only create directories when s3 destination bucket option is missing
    if args.dest_bucket is None and not args.dry_run:
        if not os.path.exists(dest):
            os.makedirs(dest)
        os.chdir(dest)

    paginator = client.get_paginator('list_object_versions')
    obj_needs_be_deleted = {}
    page_iterator = paginator.paginate(Bucket=args.bucket, Prefix=args.prefix)
    # Delete markers can get desynchronized with the versions markers in the pagination system below.
    # To avoid this, we will push from page to page the desynchronized markers until they fall on the
    # page they should (the one with the versioning markers for the same set of files)
    previous_deletemarkers = []
    for page in page_iterator:
        if not "Versions" in page:
            print("No versions matching criteria, exiting ...", file=sys.stderr)
            sys.exit(1)
        versions = page["Versions"]
        # Some deletemarkers may come from the previous page: add them now
        deletemarkers = previous_deletemarkers + page.get("DeleteMarkers", [])
        # And since they have been added, we remove them from the overflow list
        previous_deletemarkers = []
        dmarker = {"Key":""}
        for obj in versions:
            if last_obj["Key"] == obj["Key"]:
                # We've had a newer version or a delete of this key
                continue

            version_date = obj["LastModified"]

            if version_date > pit_end_date or version_date < pit_start_date:
                if pit_start_date == datetime.fromtimestamp(0, timezone.utc):
                    obj_needs_be_deleted[obj["Key"]] = obj
                continue

            # Dont go farther in the deletemarkers list than the current key, or else we risk consuming desync delete markers of the next page
            # (both versions and deletemarkers list are sorted in alphabetical order of the key, and then in reverse time order for each key)
            while deletemarkers and (dmarker["Key"] < obj["Key"] or (dmarker["Key"] == obj["Key"] and dmarker["LastModified"] > pit_end_date)):
                dmarker = deletemarkers.pop(0)

            #skip dmarker if it's latest than pit_end_date
            if dmarker["Key"] == obj["Key"] and dmarker["LastModified"] > obj["LastModified"] and dmarker["LastModified"] <= pit_end_date:
                # The most recent operation on this key was a delete
                last_obj = dmarker
                continue

            # This version needs to be restored..
            last_obj = obj

            if handled_by_glacier(obj):
                continue

            if args.dest_bucket is not None:
                obj_needs_be_deleted.pop(obj["Key"], None)
                handled_by_copy(obj)
                continue

            if not handled_by_standard(obj):
                return

        # The last dmarker may belong to the next version (if dmarker["Key"] != obj["Key"] ), keep it
        previous_deletemarkers.append(dmarker)
        # And all following may too, if any, so add them now.
        while deletemarkers:
            previous_deletemarkers.append(deletemarkers.pop(0))

        for future in concurrent.futures.as_completed(futures):
            if future in futures:
                try:
                    future.result()
                    print_obj(futures[future])
                except Exception as ex:
                    print('"%s" %s %s %s %s "ERROR: %s"' % (obj["LastModified"], obj["VersionId"], obj["Size"], obj["StorageClass"], obj["Key"], ex), file=sys.stderr)
                del(futures[future])
    # delete objects which came in existence after pit_end_date only if the destination bucket is same as source bucket and restoring to same object key
    if args.dest_bucket == args.bucket and not args.dest_prefix:
        for key in obj_needs_be_deleted:
            handled_by_delete(obj_needs_be_deleted[key])
        for future in concurrent.futures.as_completed(futures):
            if future in futures:
                try:
                    future.result()
                    print_obj(futures[future])
                except Exception as ex:
                    print('"%s" %s %s %s %s "ERROR: %s"' % (obj["LastModified"], obj["VersionId"], obj["Size"], obj["StorageClass"], obj["Key"], ex))
                del(futures[future])

if __name__=='__main__':
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bucket', help='s3 bucket to restore from', required=True)
    parser.add_argument('-B', '--dest-bucket', help='s3 bucket where recovering to', required=False)
    parser.add_argument('-d', '--dest', help='path where recovering to on local', default="")
    parser.add_argument('-p', '--prefix', help='s3 path to restore from', default="")
    parser.add_argument('-P', '--dest-prefix', help='s3 path to restore to', default="")
    parser.add_argument('-t', '--timestamp', help='final point in time to restore at')
    parser.add_argument('-f', '--from-timestamp', help='starting point in time to restore from')
    parser.add_argument('-e', '--enable-glacier', help='enable recovering from glacier', action='store_true')
    parser.add_argument('-v', '--verbose', help='print verbose informations from s3 objects', action='store_true')
    parser.add_argument('-u', '--endpoint-url', help='use another endpoint URL for s3 service')
    parser.add_argument('--dry-run', help='execute query without transferring files', action='store_true')
    parser.add_argument('--debug', help='enable debug output', action='store_true')
    parser.add_argument('--test', help='s3 pit restore testing', action='store_true')
    parser.add_argument('--max-workers', help='max number of concurrent download requests', default=10, type=int)
    parser.add_argument('--sse', choices=['AES256', 'aws:kms'], help='Specify server-side encryption')
    args = parser.parse_args()

    if args.dest_bucket is None and not args.dest:
        parser.error("Either provide destination bucket using (-B ) or provide destination for local restore (-d)")
        sys.exit(1)

    if not args.test:
        do_restore()
    else:
        runner = unittest.TextTestRunner()
        dest_bucket = args.dest_bucket
        dest_prefix = args.dest_prefix

        #To run the test cases for local restore, Later we restore this
        args.dest_bucket = None
        args.dest_prefix = None
        if args.dest:
            itersuite = unittest.TestLoader().loadTestsFromTestCase(TestS3PitRestore)
            runner.run(itersuite)

        # Restore back dest_bucket state
        args.dest_bucket = dest_bucket
        if args.dest_bucket is not None:
            itersuite = unittest.TestLoader().loadTestsFromTestCase(TestS3PitRestore)
            runner.run(itersuite)

            # Restore back dest_prefix state
            if dest_prefix:
                args.dest_prefix = dest_prefix
                itersuite = unittest.TestLoader().loadTestsFromTestCase(TestS3PitRestore)
                runner.run(itersuite)
    sys.exit(0)
