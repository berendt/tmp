import logging
from neutronclient.neutron import client
import paramiko

USERNAME='admin'
TENANTNAME='admin'
PASSWORD='password'
AUTHURL='http://localhost:5000/v2.0'

def get_links(host, network, ssh):
    ssh.connect(agent_host, username='root')
    stdin, stdout, stderr = ssh.exec_command("ip netns exec qdhcp-%s ip link show" % network['id'])
    for line in stdout.readlines():
        print line
    ssh.close()

logging.basicConfig(level=logging.INFO)
neutron = client.Client('2.0', password=PASSWORD, username=USERNAME, tenant_name=TENANTNAME, auth_url=AUTHURL)
neutron.format = 'json'

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()

result = neutron.list_agents()

dhcp_agents = {}

for agent in result['agents']:
    if agent['binary'] == 'neutron-dhcp-agent':
        dhcp_agents[agent['id']] = agent['host']

for agent_id, agent_host in dhcp_agents.iteritems():
        result = neutron.list_networks_on_dhcp_agent(agent_id)
        for network in result['networks']:
            print get_links(agent_host, network, ssh)
