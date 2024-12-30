import datetime
import json
import math
from pathlib import Path
import boto3
import numpy as np
from .storage_volume import StorageVolume

class RDSSnapshot:
    def __init__(self, snapshot_id, rds_client):
        self.snapshot_id = snapshot_id
        self.rds = rds_client
        self.get_snapshot_details()
    
    def get_snapshot_details(self):
        snapshot = self.rds.describe_db_snapshots(DBSnapshotIdentifier=self.snapshot_id)['DBSnapshots'][0]
        self.storage_size = snapshot['AllocatedStorage']
        self.engine = snapshot['Engine']
        self.creation_time = snapshot['SnapshotCreateTime']
        self.status = snapshot['Status']
        self.type = snapshot['SnapshotType']
        self.db_instance_id = snapshot['DBInstanceIdentifier']

    def is_unused(self, retention_days=30):
        # Check if snapshot is older than retention period
        age = datetime.datetime.now(datetime.timezone.utc) - self.creation_time
        if age.days > retention_days:
            # Check if this is the most recent snapshot for a deleted instance
            try:
                self.rds.describe_db_instances(DBInstanceIdentifier=self.db_instance_id)
                # Instance exists, so this is just an old snapshot
                return True
            except self.rds.exceptions.DBInstanceNotFoundFault:
                # Instance doesn't exist, check if this is the newest snapshot
                snapshots = self.rds.describe_db_snapshots(DBInstanceIdentifier=self.db_instance_id)['DBSnapshots']
                newest_snapshot = max(snapshots, key=lambda x: x['SnapshotCreateTime'])
                return self.snapshot_id != newest_snapshot['DBSnapshotIdentifier']
        return False

    def get_savings(self):
        # RDS snapshot pricing is typically $0.095 per GB-month for most regions
        # This is a simplified calculation and should be adjusted based on region and storage type
        snapshot_price = self.storage_size * 0.095
        return {
            "currentType": f"Snapshot-{self.type}",
            "currentPrice": snapshot_price,
            "newType": "None",
            "newPrice": 0
        }

class DatabaseInstance:
    def __init__(self, identifier, region, cwClient, rdsClient):
        self.identifier = identifier
        self.region = region["RegionName"]
        self.cw = cwClient
        self.rds = rdsClient
        self.getInstanceSpecs()
        self.getPerformanceMetrics()
        self.check_snapshots()
    
    # Fetch and set specifications of running datbabase instance
    def getInstanceSpecs(self):
        specs = self.rds.describe_db_instances(DBInstanceIdentifier=self.identifier)['DBInstances'][0]
        if "aurora" not in specs['Engine']:
            if "Iops" in specs:
                self.iops = specs['Iops']
            else:
                self.iops = 3000
            if "StorageThroughput" in specs:
                self.throughput = specs['StorageThroughput']
            else:
                self.throughput = 125
            self.aurora = False
        else:
            self.aurora = True
        self.instanceType = specs['DBInstanceClass']
        self.storageSize = specs['AllocatedStorage']
        self.storageType = specs['StorageType']
        self.multiAZ = specs['MultiAZ']
        self.engine = specs['Engine']
        self.status = specs['DBInstanceStatus']

    # Fetch and set maxConn --> max number of connections per day over past 3 days
    # Fetch and set cpu p99.9 --> p999 of maximum cpu usage in 1 min intervals over a max period of 14 days
    # Fetch and set memory p99.5 --> p995 of minimum available memory in 1 min intervals over a max period of 14 days
    def getPerformanceMetrics(self):
        # fetch and set connection count
        activeConnPerDay = self.cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "dbi",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/RDS",
                            "MetricName": "DatabaseConnections",
                            "Dimensions": [
                                {"Name": "DBInstanceIdentifier", "Value": self.identifier}
                            ],
                        },
                        "Period": 86400,
                        "Stat": "Sum",
                    },
                },
            ],
            StartTime=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=3),
            EndTime=datetime.datetime.now(datetime.timezone.utc),
        )['MetricDataResults'][0]['Values']
        self.maxConn = -1
        for connDay in activeConnPerDay:
            if connDay > self.maxConn:
                self.maxConn = connDay

        
    def calculateServerlessCost(self):
        avgACUs = self.cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "dbi",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/RDS",
                            "MetricName": "ServerlessDatabaseCapacity",
                            "Dimensions": [
                                {"Name": "DBInstanceIdentifier", "Value": self.identifier}
                            ],
                        },
                        "Period": 86400,
                        "Stat": "Average",
                    },
                },
            ],
            StartTime=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=30),
            EndTime=datetime.datetime.now(datetime.timezone.utc),
        )['MetricDataResults'][0]['Values']
        return np.mean(avgACUs) * 0.14 * 24 * 30
    # if old gen CPU, first, move up to current gen
    # if graviton == True, pick rightsized CPU and mem with graviton in it
    # if d (instance store), keep instance store same size --> just convert to graviton
    # if t (burstable instance), keep instance in t family --> burstable credits???
    # ...d (instance store) and x instances are not supported
    # don't take into account network usage because of lack of metrics
    def rightsizeCompute(self):
        if self.instanceType == "db.serverless":
            serverlessCost = self.calculateServerlessCost()
            if self.maxConn == 0:
                return {
                    "currentInstanceType": self.instanceType,
                    "currentInstancePrice": serverlessCost,
                    "newInstanceType": "None",
                    "newInstancePrice": 0
                }
            return {
                "currentInstanceType": self.instanceType,
                "currentInstancePrice": serverlessCost,
                "newInstanceType": self.instanceType,
                "newInstancePrice": serverlessCost
            }
        path = Path(__file__).parent / "../aws-data/dbiPricing.json"
        with path.open() as f:
            dbi_rate = json.load(f)
        
        path = Path(__file__).parent / "../aws-data/dbiPricing.json"
        with path.open() as f:
            aurora_rate = json.load(f)

        # check if DB is idle
        if self.maxConn == 0:
            if self.aurora:
                return {
                    "currentInstanceType": self.instanceType,
                    "currentInstancePrice": aurora_rate[self.region][self.instanceType]["instancePrice"]*24*30,
                    "newInstanceType": "None",
                    "newInstancePrice": 0
                }
            return {
                "currentInstanceType": self.instanceType,
                "currentInstancePrice": dbi_rate[self.region][self.instanceType]["instancePrice"]*24*30,
                "newInstanceType": "None",
                "newInstancePrice": 0
            }
        

    def rightsizeStorage(self):
        if not self.aurora:
            # check if DB is not idle
            volume = StorageVolume(self.storageType, self.storageSize, self.iops, self.throughput)
            if self.maxConn == 0:
                return {
                    "currentType": self.storageType,
                    "currentPrice": volume.calculateStorageCost(self.storageType, self.storageSize, self.iops, self.throughput),
                    "newType": "None",
                    "newPrice": 0
                }
            return volume.getSavings()
        else:
            return {
                "currentType": "Aurora",
                "currentPrice": 0,
                "newType": "Aurora",
                "newPrice": 0
            }
        
    def isIdle(self):
        if self.maxConn == 0:
            return True
        return False

    def check_snapshots(self):
        try:
            snapshots = self.rds.describe_db_snapshots(DBInstanceIdentifier=self.identifier)['DBSnapshots']
            self.unused_snapshots = []
            for snapshot in snapshots:
                snapshot_obj = RDSSnapshot(snapshot['DBSnapshotIdentifier'], self.rds)
                if snapshot_obj.is_unused():
                    self.unused_snapshots.append(snapshot_obj)
        except Exception as error:
            print(f"Error checking snapshots for {self.identifier}: {error}")
            self.unused_snapshots = []