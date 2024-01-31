import datetime
import boto3
import numpy as np
from .storage_volume import StorageVolume

class EBSVolume:
    def __init__(self, volumeId, ec2Client, cw):
        self.ec2 = ec2Client
        self.volumeId = volumeId
        self.cw = cw
        self.getVolumeInfo()
        self.volume = StorageVolume(self.type, self.size, self.iops, self.throughput)

    def getVolumeInfo(self):
        volume = self.ec2.describe_volumes(VolumeIds=[self.volumeId])["Volumes"][0]
        self.type = volume["VolumeType"]
        self.size = volume["Size"]
        self.iops = volume.get("Iops")
        self.throughput = volume.get("Throughput")

    def getThroughput(self):
        # Max ReadOps
        readIO = self.cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "dbi",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EBS",
                            "MetricName": "VolumeReadBytes",
                            "Dimensions": [
                                {"Name": "VolumeId", "Value": self.volumeId}
                            ],
                        },
                        "Period": 60,
                        "Stat": "Maximum",
                    },
                },
            ],
            StartTime=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=14),
            EndTime=datetime.datetime.now(datetime.timezone.utc),
            ScanBy='TimestampAscending'
        )['MetricDataResults'][0]['Values']
        if len(readIO[14:]) == 0:
            readThroughput = 0.0
        else:
            readThroughput = np.percentile(np.array(readIO[14:]), 99.9)/60
        # Max WriteOps
        writeIO = self.cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "dbi",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EBS",
                            "MetricName": "VolumeWriteBytes",
                            "Dimensions": [
                                {"Name": "VolumeId", "Value": self.volumeId}
                            ],
                        },
                        "Period": 60,
                        "Stat": "Maximum",
                    },
                },
            ],
            StartTime=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=14),
            EndTime=datetime.datetime.now(datetime.timezone.utc),
            ScanBy='TimestampAscending'
        )['MetricDataResults'][0]['Values']
        if len(writeIO[14:]) == 0:
            writeThroughput = 0.0
        else:
            writeThroughput = np.percentile(np.array(writeIO[14:]), 99.9)/60
        return readThroughput + writeThroughput

    def inUse(self):
        self.throughput = self.getThroughput()
        if self.throughput > 0:
            return True
        else:
            return False

    def getSavings(self):
        return {
            "currentType": self.type,
            "currentPrice": self.volume.calculateStorageCost(self.type, self.size, self.iops, self.throughput),
            "newType": "None",
            "newPrice": 0
        }