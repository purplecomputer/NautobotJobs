#Angelo.Poggi

from nautobot.extras.jobs import Job, ChoiceVar, ObjectVar
from nautobot.dcim.models import Device, Interface
from nautobot.ipam.models import VLAN, VLANGroup
from nautobot.extras.models import Secret


import napalm

class ImportDeviceVlans(Job):
    '''Class to Import VLANs from a device into a specific Group for Legacy Webair Infra'''
    # class Meta:
    #     name = "Import Device Vlans",
    #     description = "Imports Vlans from a specified Device",
    #     field_order = ['device', 'vlan_groups']

    vlan_groups = ChoiceVar(
        description="Group you want to import the device VLANS into",
        label="VLAN Group",
        choices=(
            ("ds120", "DS120"),
            ("ds121", "DS121"),
            ("ds180", "DS180")
        )
    )
    selected_device = ObjectVar(
        model=Device,
        query_params={
            'status':'active'
        }
    )
    def __init__(self):
        '''Inherits init from Jobs and creates a connection to nautobot and device during instantiation of class'''
        super().__init__()
        self.device_platform_connection = {
            "cisco_nxos":  {"os": "nxos_ssh"},
            "cisco_iosxe": {"os": "ios"},
            "cisco_ios":   {"os": "ios"},
            "cisco_xr":    {"os": "iosxr"}
        }
        self.active_status = '1f272eaa-a624-4078-9359-8966e56c16cf'
    def _connecttodevice(self,selected_device):
        device = Device.objects.get(name=selected_device)
        # get username and password
        username = Secret.objects.get(name='RANCID_USERNAME').get_value()
        password = Secret.objects.get(name='RANCID_PASSWORD').get_value()
        device_os = self.device_platform_connection[str(device.platform)]['os']
        driver = napalm.get_network_driver(device_os)
        device_init = driver(
            hostname=str(device.name),
            username=str(username),
            password=str(password),
            optional_args={
                'secret': str(password)
            }
        )
        return device_init
         
    def _getvlans(self,device):
        '''Queries device info and grabs VLAN'''
        #give me that data
        device_init = self._connecttodevice(selected_device=device)
        device_init.open()
        return device_init.get_vlans()

    def _formatnapalmvlandict(self, device,group,vlans):
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
        device = Device.objects.get(name=device)
        try:
            vlangroup = VLANGroup.objects.get(name=str(group))
        except:
                vlangroup = VLANGroup(
                    name=str(group),
                    site_id=device.site.id
                )
                vlangroup.validated_save()
        if not isinstance(vlans, dict):
            raise Exception("vlan arg must be a dictionary")
        for k, v in vlans.items():
            try:
                vlanid = VLAN.objects.get(
                    vid=str(k),
                    group_id=vlangroup.id
                )
            except:
                vlanid = VLAN(
                    name=str(k),
                    vid=k,
                    group_id=str(vlangroup.id),
                    site_id=device.site.id,
                    status_id=self.active_status,
                    #description=j.get(['name'], k)
                )
                vlanid.validated_save()
            for j in v['interfaces']:
                if j in newdict:
                    #if the key is already there add the vlan
                    newdict[j].append(vlanid.id)
                else:
                    newdict[j] = [vlanid.id]
        return(newdict)

    def _linkSVItoImportVlan(self, device,group):
        '''Iterates through the interfaces and tries to link SVI to nautobot VLAN object'''
        device = Device.objects.get(name=device)
        device_interfaces = Interface.objects.filter(device_id=device.id)
        vlan_group = VLANGroup.objects.get(name=str(group))
        for interface in device_interfaces:
            if 'Vlan' in interface.name:
                interface_name_strip = interface.name.strip('Vlan')
                vidQuery = VLAN.objects.get(name=str(interface_name_strip), group_id=vlan_group.id)
                if vidQuery is not None:
                    interface(
                        mode='tagged',
                        tagged_vlans=[vidQuery.id]
                    )
                    interface.validated_save()

    def nautobotvlanimport(self, device, group):
        '''dumps them vlans into them groups and links it to the SVI created'''
        vlans = self._getvlans(device)
        # convert the Dict to something thats easier to use here
        vlans_converted = self._formatnapalmvlandict(device,group, vlans)

        for interface, vlan in vlans_converted.items():
            '''query interface object'''
            try:
                interfaceQuery = Interface.objects.get(
                    name=str(interface),
                    device_id=self.device.id
                )
            except:
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
        self._linkSVItoImportVlan(device,group)

    def run(self, data, commit):
        if commit == True:
            nbjob = ImportDeviceVlans()
            nbjob.nautobotvlanimport(data['selected_device'], data['vlan_groups'])
        else:
            pass

