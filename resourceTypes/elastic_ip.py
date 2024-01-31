import boto3
eip_rate = 0.005 * 24 * 30

class ElasticIP:
    def __init__(self, allocationId, ec2Client):
        self.ec2 = ec2Client
        self.allocationID = allocationId

    def inUse(self):
        eips = self.ec2.describe_addresses(AllocationIds=[self.allocationID])
        for eip in eips["Addresses"]:
            if eip.get("AssociationId") == None:
                return False
            else:
                return True
        
    def getSavings(self):
        if self.inUse():
            return {
                'currentType': 'EIP',
                'currentPrice': eip_rate,
                'newType': 'EIP',
                'newPrice': eip_rate
            }
        else:
            return {
                'currentType': 'EIP',
                'currentPrice': eip_rate,
                'newType': 'None',
                'newPrice': 0
            }