import json, uuid, boto3
import mycredentials

class KinesisStream(object):

    def __init__(self, stream):
        self.stream = stream

    def _connected_client(self):
        """ Connect to Kinesis Streams """
        return boto3.client('kinesis',
                            region_name=mycredentials.amazonregion,
                            aws_access_key_id=mycredentials.amazonid,
                            aws_secret_access_key=mycredentials.amazonkey)

    def send_stream(self, data, partition_key=None):

        #we send list of records to kinesis

        client = self._connected_client()
        response = client.put_records(
            Records=data,
           StreamName=self.stream
        )

        return response
