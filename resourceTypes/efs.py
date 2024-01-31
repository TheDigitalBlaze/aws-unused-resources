import datetime
import boto3
import numpy as np

EFSStandardRate = 0.33
EFSIARate = 0.025

class EFSFileSystem:
    def __init__(self, fsId, efsClient, cw):
        self.efs = efsClient
        self.fsId = fsId
        self.efs = efsClient
        self.cw = cw
    
    def getSize(self):
        fs = self.efs.describe_file_systems(
            FileSystemId=self.fsId
        )
        for efs in fs['FileSystems']:
            self.standardSize = efs['SizeInBytes']['ValueInStandard']
            self.IASize = efs['SizeInBytes']['ValueInIA']

    def calculateEFSCost(self):
        self.getSize()
        return (self.standardSize * EFSStandardRate / 1024 / 1024 / 1024) + (self.IASize * EFSIARate / 1024 / 1024 / 1024)

    def isUsed(self):
        # Max ReadOps
        conn = self.cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "dbi",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EFS",
                            "MetricName": "ClientConnections",
                            "Dimensions": [
                                {"Name": "FileSystemId", "Value": self.fsId}
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
        if len(conn) == 0:
            return False
        return True

    def getSavings(self):
        currentPrice = self.calculateEFSCost()
        # if volume is unused
        if self.isUsed():
            return {
                "currentType": "EFS",
                "currentPrice": currentPrice,
                "newType": "EFS",
                "newPrice": currentPrice
            }
        return {
            "currentType": "EFS",
            "currentPrice": currentPrice,
            "newType": "None",
            "newPrice": 0
        }