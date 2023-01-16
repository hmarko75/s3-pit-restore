FROM python:3.11.1-alpine3.16

#install pandas and numpy
RUN apk add --update --no-cache openssh
#install git
RUN apk add --update --no-cache git
#install aws cli, boto3, shutup
RUN pip3 --no-cache-dir install boto3 botocore awscli shutup 

#clone the repo 
RUN git clone https://github.com/hmarko75/s3-pit-restore.git

RUN mkdir -p /restore

ENTRYPOINT [ "./s3-pit-restore/s3-pit-restore" ]
CMD [ "-h" ]
