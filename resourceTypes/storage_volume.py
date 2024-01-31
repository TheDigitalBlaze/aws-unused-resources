IopsThroughput = {
    "gp3": {
        "iops": 16000,
        "throughput": 1000
    },
    "io2": {
        "iops": 64000,
        "throughput": 1000
    },
    "st1": {
        "iops": 500,
        "throughput": 500
    },
    "sc1": {
        "iops": 250,
        "throughput": 250
    }
}

volumes_gp2_rate = 0.11
volumes_gp3_rate = 0.088
volumes_gp3_iops_rate = (
    0.0055  # 3,000 IOPS free and $0.0055/provisioned IOPS-month over 3,000
)
volumes_gp3_througput_rate = (
    0.044  # 125 MB/s free and $0.044/provisioned MB/s-month over 125
)
volumes_st1_rate = 0.05
volumes_sc1_rate = 0.0168
volumes_io1_storage_rate = 0.138
volumes_io1_iops_rate = 0.072
volumes_io2_storage_rate = 0.138
volumes_io2_iops_rate_1 = 0.072  # $0.072/provisioned IOPS-month up to 32,000 IOPS
volumes_io2_iops_rate_2 = (
    0.050  # $0.050/provisioned IOPS-month from 32,001 to 64,000 IOPS
)
volumes_io2_iops_rate_3 = (
    0.035  # $0.035/provisioned IOPS-month for greater than 64,000 IOPS
)

class StorageVolume:
    def __init__(self, type, size, iops=3000, throughput=125):
        self.type = type
        self.size = size
        self.iops = iops
        self.throughput = throughput

    def calculateStorageCost(self, type, size, iops, throughput):
        storageCost = 0
        if type == "gp2":
            storageCost = size * volumes_gp2_rate
        elif type == "gp3":
            storageCost = size * volumes_gp3_rate
            if iops > 3000:
                storageCost = storageCost + (iops - 3000) * volumes_gp3_iops_rate
            if throughput is not None:
                if throughput > 125:
                    storageCost = (
                        storageCost + (throughput - 125) * volumes_gp3_througput_rate
                    )
        elif type == "st1":
            storageCost = size * volumes_st1_rate
        elif type == "sc1":
            storageCost = size * volumes_sc1_rate
        elif type == "io1":
            storageCost = (size * volumes_io1_storage_rate)
            storageCost = storageCost + iops * volumes_io1_iops_rate
        elif type == "io2":
            storageCost = (size * volumes_io1_storage_rate)
            if iops < 32000:
                storageCost = storageCost + iops * volumes_io2_iops_rate_1
            elif iops > 64000:
                storageCost = storageCost + iops * volumes_io2_iops_rate_3
            else:
                storageCost = storageCost + iops * volumes_io2_iops_rate_2

        return storageCost
    
    def getSavings(self):
        print(self.iops, self.throughput)
        if self.iops < IopsThroughput["sc1"]["iops"] and self.throughput < IopsThroughput["sc1"]["throughput"] and self.size > 125:
            return {
                "currentType": self.type,
                "currentPrice": self.calculateStorageCost(self.type, self.size, self.iops, self.throughput),
                "newType": "sc1",
                "newPrice": self.calculateStorageCost("sc1", self.size, self.iops, self.throughput)
            }
        if self.iops < IopsThroughput["st1"]["iops"] and self.throughput < IopsThroughput["st1"]["throughput"] and self.size > 125:
            return {
                "currentType": self.type,
                "currentPrice": self.calculateStorageCost(self.type, self.size, self.iops, self.throughput),
                "newType": "st1",
                "newPrice": self.calculateStorageCost("st1", self.size, self.iops, self.throughput)
            }
        if self.iops < IopsThroughput["gp3"]["iops"]:
            return {
                "currentType": self.type,
                "currentPrice": self.calculateStorageCost(self.type, self.size, self.iops, self.throughput),
                "newType": "gp3",
                "newPrice": self.calculateStorageCost("gp3", self.size, self.iops, self.throughput)
            }
        return {
            "currentType": self.type,
            "currentPrice": self.calculateStorageCost(self.type, self.size, self.iops, self.throughput),
            "newType": "io2",
            "newPrice": self.calculateStorageCost("io2", self.size, self.iops, self.throughput)
        }