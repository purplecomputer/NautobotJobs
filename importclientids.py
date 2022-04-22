from nautobot.ipam.models import IPAddress
from nautobot.extras.jobs import Job
import requests

class ImportClientIDs(Job):
    def __init__(self):
        super().__init__()
    def _fetchscpid(self,ip):
        if "/" in ip:
            ip = ip.split("/")[0]
        else:
            pass
        clientID = requests.get(f'http://admin.webair.com/cgi-bin/clientbyip.cgi?ip={ip}')
        if clientID.status_code != 200:
            return None
            exit(1)
        else:
            return clientID.json()['cid']
    def clientIDPull(self):
        #grab all IPs in IPAM
        all_ips = IPAddress.objects.all()
        for ips in all_ips:
            iplookup = self._fetchscpid(ips)
            if iplookup is not None:
                ips._custom_field_data['clientid'] = iplookup
                ips.validated_save()
            else:
                ips._custom_field_data['clientid'] = "Client-Unknown"
                ips.validated_save()

    def run(self):
        nbjob = ImportClientIDs()
        nbjob.clientIDPull()



