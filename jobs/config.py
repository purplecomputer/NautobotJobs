#2022 - Opti9Technologies
#By: Angelo Poggi angelo.poggi@opti9tech.com
import os
from dotenv import load_dotenv,find_dotenv
from pathlib import Path

try:
    env_file = find_dotenv()
    load_dotenv(env_file)
except:
    raise ("Could not open .env file; please make sure it exsists!")

#Nautobot Junk
nautobot_url = os.environ['NAUTOBOT_URL']
nautobot_token = os.environ['NAUTOBOT_TOKEN']

#NETOPS
netops_url = os.environ['NAUTOBOT_URL']

#Device Info
device_username = os.environ['device_username']
device_password = os.environ['device_password']


device_platform_connection = {
    "cisco_nxos": {"os": "nxos"},
    "cisco_iosxe": {"os": "ios"},
    "cisco_ios" : {"os": "ios"},
    "cisco_xr" : {"os": "iosxr"}
}
