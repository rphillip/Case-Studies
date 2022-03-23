docker build -t genzipfile .
docker create -ti --name tempforzip genzipfile
docker cp tempforzip:/function/linux-lambda.zip /Users/HomeFolder/mydatasets/datacourse_database-systems/miniprojects/lambdas/linux-lambda.zip
docker rm -f tempforzip
