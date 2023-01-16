# S3 point in time restore

This is the repository for s3-pit-restore, a point in time restore tool
for Amazon S3 or compatible storage.

The typical scenario in which you may need this tool is when you have
enabled versioning on an S3 bucket and want to restore some or all of
the files to a certain point in time, to local file system, same s3 bucket or different s3 bucket.

Doing this with the web interface is time consuming: Amazon S3 web management
gui doesn't offer a simple way to do that on a massive scale.

With this tool you can easily restore a repository to a point in time
with a simple command like:

* To local file-system:
	```
	$ s3-pit-restore -b my-bucket -d restored-bucket-local -t "06-17-2016 23:59:50 +2"
	```
* To s3 bucket:-
	```
	$ s3-pit-restore -b my-bucket -B restored-bucket-s3 -t "06-17-2016 23:59:50 +2"
	```
* To s3 bucket on s3 compatible storage:-
	```
	$ s3-pit-restore -b my-bucket -B restored-bucket-s3 -t "06-17-2016 23:59:50 +2" -u https://s3.domain.com:10443
	```

Choosing the correct time and date to restore at is simply a matter of getting
that information clicking the *Versions: Show* button from the S3 web gui
and navigating through the, now appeared, versions timestamps.

## Installing

or clone the repository and launch ./s3-pit-restore. this will pull a docker image containing the tools and all requirements


## Requirements

  * docker
  * ability to pull the hmarko75/s3-pit-restore:latest
  * AWS credentials available in the environment defined as environment variables:
			* AWS_ACCESS_KEY_ID
			* AWS_SECRET_ACCESS_KEY
			* AWS_DEFAULT_REGION

## Usage

`s3-pit-restore` can do a lot of interesting things. The base one is restoring an entire bucket to a previous state:

### Restore to local file-system

* Restore to local file-system directory `restored-bucket-local`
	```
	$ s3-pit-restore -b my-bucket -d restore -t "06-17-2016 23:59:50 +2"
	```
	* `-b` gives the source bucket name to be restored from
	* `-d` gives the local folder to restore to (if it doesn't exist it will be created). 
	* 	for this docker envrironment the restore will be done to the restore folder undet the installation dir (will be autocreated)
	* `-t` gives the target date to restore to. Note: The timestamp must include the timezone offset. 

### Restore to s3 bucket

* Restore to same bucket:
	```
	$ s3-pit-restore -b my-bucket -B my-bucket -t "06-17-2016 23:59:50 +2"
	```
	* `-B` gives the destination bucket to restore to. Note: Use the same bucket name to restore back to the source bucket.

* Restore to different bucket:-
	```
	$ s3-pit-restore -b my-bucket -B restored-bucket-s3 -t "06-17-2016 23:59:50 +2"
	```

* Restore to s3 bucket with custom virtual prefix [restored object(src_obj) will have key as `new-restored-path/src_obj["Key"]`] (Using `-P` flag)
	```
	$ s3-pit-restore -b my-bucket -B restored-bucket-s3 -P new-restored-path -t "06-17-2016 23:59:50 +2"
	```

### Other common options for both the cases

* Another thing it can do is to restore a subfolder (*prefix*) of a bucket:
	```
	$ s3-pit-restore -b my-bucket -d my-restored-subfolder -p mysubfolder -t "06-17-2016 23:59:50 +2"
	```
	* `-p` gives a prefix to isolate when checking the _source_ bucket (`-P` is used when deal with the _destination_ bucket/folder)

* You can also speedup the download if you have bandwidth using more parallel workers (`--max-workers` flag):
	```
	$ s3-pit-restore -b my-bucket -d my-restored-subfolder -p mysubfolder -t "06-17-2016 23:59:50 +2" --max-workers 100
	```

* If want to restore a well defined time span, you can use a starting (`-f`) and ending (`-t`) timestamp (a month in this example):
	```
	$ s3-pit-restore -b my-bucket -d my-restored-subfolder -p mysubfolder -f "05-01-2016 00:00:00 +2" -t "06-01-2016 00:00:00 +2"
	```

## Command line options

```
usage: s3-pit-restore [-h] -b BUCKET [-B DEST_BUCKET] [-d DEST]
                      [-P DEST_PREFIX] [-p PREFIX] [-t TIMESTAMP]
                      [-f FROM_TIMESTAMP] [-e] [-v] [--dry-run] [--debug]
                      [--test] [--max-workers MAX_WORKERS]
                      [--sse {AES256,aws:kms}]

optional arguments:
  -h, --help            show this help message and exit
  -b BUCKET, --bucket BUCKET
                        s3 bucket to restore from
  -B DEST_BUCKET, --dest-bucket DEST_BUCKET
                        s3 bucket where recovering to
  -d DEST, --dest DEST  path where recovering to on local
  -p PREFIX, --prefix PREFIX
                        s3 path to restore from
  -P DEST_PREFIX, --dest-prefix DEST_PREFIX
                        s3 path to restore to
  -t TIMESTAMP, --timestamp TIMESTAMP
                        final point in time to restore at
  -f FROM_TIMESTAMP, --from-timestamp FROM_TIMESTAMP
                        starting point in time to restore from
  -e, --enable-glacier  enable recovering from glacier
  -v, --verbose         print verbose informations from s3 objects
  -u ENDPOINT_URL, --endpoint-url ENDPOINT_URL
                        use another endpoint URL for s3 service  
  --dry-run             execute query without transferring files
  --debug               enable debug output
  --test                s3 pit restore testing
  --max-workers MAX_WORKERS
                        max number of concurrent download requests
  --sse ALGORITHM
                        specify what SSE algorithm you would like to use for the copy
```

## Testing

s3-pit-restore comes with a testing suite. You can run it with:

### Restore to local file-system test cases:
	`$ ./s3-pit-restore -b my-bucket -d /tmp/ --test`

### Restore to s3 bucket test cases:
	`$ ./s3-pit-restore -b my-bucket -B restore-bucket-s3 -P restore-path --test` (make sure you have s3 bucket `restore-bucket-s3`)

### Run all the test cases:
	`$ ./s3-pit-restore -b my-bucket -B restore-bucket-s3 -d /tmp/ -P restore-path --test`
