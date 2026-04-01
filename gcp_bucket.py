import os
from google.cloud import storage

client = storage.Client.from_service_account_json("service-account.json")
bucket = client.bucket("invoice-exception-usecase")

files = [
    "./documents/HR_Dress_Code_Policy.pdf",
    "./documents/HR_Leave_Policy.pdf",
    "./documents/HR_Security_Policy.pdf"
]

folder_path = "amal_gopi/rag_app_hr_policy/"

for file in files:
    filename = os.path.basename(file)  # extract only file name
    blob = bucket.blob(folder_path + filename)
    blob.upload_from_filename(file)
    print(f"{filename} uploaded!")

print("Done 🚀")