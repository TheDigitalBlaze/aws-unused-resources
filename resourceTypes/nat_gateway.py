import datetime
import boto3
natgw_rate = 0.048 * 24 * 30

class NATGateway:
    def __init__(self, id, ec2Client, cwClient):
        self.ec2 = ec2Client
        self.cw = cwClient
        self.id = id

    def inUse(self):
        elbs = self.ec2.describe_nat_gateways(NatGatewayIds=[self.id])
        for natgw in self.ec2.describe_nat_gateways()['NatGateways']:
            if natgw['State'] == 'available':
                activeConnPerDay = self.cw.get_metric_data(
                    MetricDataQueries=[
                        {
                            "Id": "natgw",
                            "MetricStat": {
                                "Metric": {
                                    "Namespace": "AWS/NATGateway",
                                    "MetricName": "ActiveConnectionCount",
                                    "Dimensions": [
                                        {"Name": "NatGatewayId", "Value": natgw['NatGatewayId']}
                                    ],
                                },
                                "Period": 86400,
                                "Stat": "Sum",
                            },
                        },
                    ],
                    StartTime=datetime.datetime.now(datetime.timezone.utc)
                    - datetime.timedelta(days=14),
                    EndTime=datetime.datetime.now(datetime.timezone.utc),
                )['MetricDataResults'][0]['Values']
                activeConn = False
                for connDay in activeConnPerDay:
                    if connDay > 0:
                        return True
                    else:
                        return False
                
    def getSavings(self):
        if self.inUse():
            return {
                'currentType': 'NATGW',
                'currentPrice': natgw_rate,
                'newType': 'NATGW',
                'newPrice': natgw_rate
            }
        else:
            return {
                'currentType': 'NATGW',
                'currentPrice': natgw_rate,
                'newType': 'None',
                'newPrice': 0
            }