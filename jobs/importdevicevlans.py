#Angelo.Poggi

from nautobot.extras.jobs import Job, ChoiceVar, StringVar
import napalm

class ImportDeviceVlans(Job):
    '''Class to Import VLANs from a device into a specific Group for Legacy Webair Infra'''
    class Meta:
        name = "Import Device Vlans",
        description = "Imports Vlans from a specified Device",
        field_order = ['device', 'vlan_groups']

        vlan_groups = ChoiceVar(
            description="Group you want to import the device VLANS into",
            label="VLAN Group",
            choices=(
                ("ds120", "DS120"),
                ("ds121", "DS121"),
                ("ds180", "DS180")
            )
        )
        device = StringVar(
            description="Switch or Router you want to pull VLANs from",
            label="Device",
            required=True,
        )
    def __init__(self,device):
        '''Inherits init from Jobs and creates a connection to nautobot and device during instantiation of class'''
        super().__init__()
        self.device_platform_connection = {
            "cisco_nxos":  {"os": "nxos_ssh"},
            "cisco_iosxe": {"os": "ios"},
            "cisco_ios":   {"os": "ios"},
            "cisco_xr":    {"os": "iosxr"}
        }
        #self.pynb = pynautobot.api(nautobot_url, token=nautobot_token)
        try:
            #self.device = self.pynb.dcim.devices.get(name=str(device))
            #Native DJango unchained ORM
            self.device = Device.objects.get(name=str(device))
            #get username and password
            self.username = Secret.objects.get(name='device-username')
            self.username = self.username.parameters['variable']
            self.password = Secret.objcets.get(name='device-password')
            self.password = self.password.parameters['variable']
        except Exception as e:
            raise Exception(e)
        #grab the platform to find the driver
        self.device_os = self.device_platform_connection[str(self.device.platform)]['os']
        self.driver = napalm.get_network_driver(self.device_os)
        self.device_init = self.driver(
            hostname=str(self.device.name),
            username=str(self.username),
            password=str(self.password),
            optional_args={
                'secret': str(self.password)
            }
        )

    def _getvlans(self):
        '''Queries device info and grabs VLAN'''
        #give me that data
        self.device_init.open()
        return self.device_init.get_vlans()

    def _formatnapalmvlandict(self, group,vlans):
        '''Lil function that just reverses the dict that napalm gives you back.
        If the interface is a trunk it will return a list of vlans, if the interface was
        access, it just give you back that vlan.
        All Vlans are converted to their proper nautobot id
        It is also created if it does not exsist
        '''
        newdict = {}
        #find the group cause you'll need it later
        # Check that group exsists & create it if it dont
        #vlangroup = self.pynb.ipam.vlan_groups.get(name=str(group))
        vlangroup = VLANGroup.objects.get(name=str(group))
        if vlangroup is None:
            vlangroup = VLANGroup(
                name=str(group),
                site=self.device.site
            )
            vlangroup.validated_save()
        if not isinstance(vlans, dict):
            raise Exception("vlan arg must be a dictionary")
        for k, v in vlans.items():
            vlanid = VLAN.objects.get(
                vid=str(k),
                vlan_group=vlangroup.id
            )
            if vlanid is None:
                vlanid = VLAN(
                    name=str(k),
                    vid=k,
                    group=str(vlangroup.id),
                    site=self.device.site.id,
                    status='active',
                    description=j['name']
                )
                vlanid.validated_save()
            for j in v['interfaces']:
                if j in newdict:
                    #if the key is already there add the vlan
                    newdict[j].append(vlanid.id)
                else:
                    newdict[j] = [vlanid.id]
        return(newdict)

    def _linkSVItoImportVlan(self, group):
        '''Iterates through the interfaces and tries to link SVI to nautobot VLAN object'''
        device_interfaces = Interface.objects.filter(device_id=self.device.id)
        for interface in device_interfaces:
            if 'Vlan' in interface.name:
                interface_name_strip = interface.name.strip('Vlan')
                vidQuery = VLAN.objects.get(name=str(interface_name_strip), group=group)
                if vidQuery is not None:
                    interface(
                        mode='tagged',
                        tagged_vlans=[vidQuery.id]
                    )
                    interface.validated_save()

    def nautobotvlanimport(self, group):
        '''dumps them vlans into them groups and links it to the SVI created'''
        vlans = self._getvlans()
        # convert the Dict to something thats easier to use here
        vlans_converted = self._formatnapalmvlandict(group, vlans)

        for interface, vlan in vlans_converted.items():
            '''query interface object'''
            interfaceQuery = Interface.objects.get(
                name=str(interface),
                device_id=self.device.id
            )
            if interfaceQuery is None:
                print(f'Interface: {interface} does not match SOT list - Skipping!')
                continue
            if len(vlan) == 1:
                if interfaceQuery.mode == None:
                    '''if the interface exsist but has no vlans or mode set
                    update and link curent vlan to vlan we are
                    set the interface as access'''
                    print('setting int as untagged')
                    interfaceQuery(
                        mode='access',
                        untagged_vlan=vlan[0]
                    )
                    interfaceQuery.validated_save()
            else:
                '''If vlan dict value list is longer than 1'''
                interfaceQuery(
                    mode='tagged',
                    tagged_vlans=vlan
                )
                interfaceQuery.validated_save()
        '''Once VLANs are imported - Link SVIs using original dict from Napalm'''
        self._linkSVItoImportVlan(group)

    def run(self, data, commit):
        if commit == True:
            nbjob = ImportDeviceVlans(data['device'])
            nbjob.nautobotvlanimport(data['vlan_groups'])
        else:
            pass

