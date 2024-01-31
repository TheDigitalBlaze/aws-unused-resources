import datetime
import boto3
elb_rate = 0.0252 * 24 * 30

class ElasticLoadBalancer:
    def __init__(self, arn, elbClient, cwClient):
        self.elbv2 = elbClient
        self.cw = cwClient
        self.arn = arn

    def inUse(self):
        elbs = self.elbv2.describe_load_balancers(LoadBalancerArns=[self.arn])
        for elb in elbs["LoadBalancers"]:
            if elb["State"]["Code"] == "active":
                lbId = elb["LoadBalancerArn"].split('/',1)[1]
                if "net" in lbId:
                    LCUConsumed = self.cw.get_metric_data(
                        MetricDataQueries=[
                            {
                                "Id": "nlb",
                                "MetricStat": {
                                    "Metric": {
                                        "Namespace": "AWS/NetworkELB",
                                        "MetricName": "ProcessedBytes",
                                        "Dimensions": [
                                            {"Name": "LoadBalancer", "Value": lbId}
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
                else:
                    LCUConsumed = self.cw.get_metric_data(
                        MetricDataQueries=[
                            {
                                "Id": "alb",
                                "MetricStat": {
                                    "Metric": {
                                        "Namespace": "AWS/ApplicationELB",
                                        "MetricName": "ProcessedBytes",
                                        "Dimensions": [
                                            {"Name": "LoadBalancer", "Value": lbId}
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
                for lcu in LCUConsumed:
                    if lcu > 0:
                        return True
                    else:
                        return False
            else:
                return True
                
    def getSavings(self):
        if self.inUse():
            return {
                'currentType': 'ELB',
                'currentPrice': elb_rate,
                'newType': 'ELB',
                'newPrice': elb_rate
            }
        else:
            return {
                'currentType': 'ELB',
                'currentPrice': elb_rate,
                'newType': 'None',
                'newPrice': 0
            }