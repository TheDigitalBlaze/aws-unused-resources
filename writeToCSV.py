import csv
import os
def write_to_csv(file_path, *args):
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(['Account', 'Region', 'ResourceId', 'currentType', 'currentCost', 'newType', 'newCost'])  # Replace with your desired header
        writer.writerow(args)
