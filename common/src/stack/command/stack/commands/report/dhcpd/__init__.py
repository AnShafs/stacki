# @copyright@
# Copyright (c) 2006 - 2017 Teradata
# All rights reserved. Stacki(r) v5.x stacki.com
# https://github.com/Teradata/stacki/blob/master/LICENSE.txt
# @copyright@
#
# @rocks@
# Copyright (c) 2000 - 2010 The Regents of the University of California
# All rights reserved. Rocks(r) v5.4 www.rocksclusters.org
# https://github.com/Teradata/stacki/blob/master/LICENSE-ROCKS.txt
# @rocks@

import stack
import ipaddress
import stack.commands
import stack.text

header = """
ddns-update-style none;

option space PXE;
option PXE.mtftp-ip    code 1 = ip-address;
option PXE.mtftp-cport code 2 = unsigned integer 16;
option PXE.mtftp-sport code 3 = unsigned integer 16;
option PXE.mtftp-tmout code 4 = unsigned integer 8;
option PXE.mtftp-delay code 5 = unsigned integer 8;

option client-arch code 93 = unsigned integer 16;
"""

filename = """	if option client-arch = 00:07 {
		filename "uefi/shim.efi";
	} else {
		filename "pxelinux.0";
	}"""


class Command(stack.commands.HostArgumentProcessor,
	stack.commands.report.command):
	"""
	Output the DHCP server configuration file.
	"""


	def writeDhcpDotConf(self):
		self.addOutput('', '<stack:file stack:name="/etc/dhcp/dhcpd.conf">')

		self.addOutput('', stack.text.DoNotEdit())
		self.addOutput('', '%s' % header)

		# Build a dictionary of DHCPD server addresses
		# for each subnet that serves PXE (DHCP).

		servers = {}
		for row in self.db.select("""
			s.name, n.ip from
			nodes nd, subnets s, networks n where 
			s.id       = n.subnet and 
			s.pxe      = TRUE     and 
			n.node     = nd.id    and 
			nd.name    = '%s'
			""" % self.db.getHostname()):
			servers[row[0]]    = row[1]
			servers['default'] = row[1]
		if len(servers) > 2:
			del servers['default']

		for (netname, network, netmask, gateway, zone) in self.db.select("""
			name, address, mask, gateway, zone from 
			subnets where
			pxe = TRUE
			"""):

			self.addOutput('', '\nsubnet %s netmask %s {'
				% (network, netmask))

			self.addOutput('', '\tdefault-lease-time\t\t1200;')
			self.addOutput('', '\tmax-lease-time\t\t\t1200;')

			ipnetwork = ipaddress.IPv4Network(network + '/' + netmask)
			self.addOutput('', '\toption routers\t\t\t%s;' % gateway)
			self.addOutput('', '\toption subnet-mask\t\t%s;' % netmask)
			self.addOutput('', '\toption broadcast-address\t%s;' %
				ipnetwork.broadcast_address)
			self.addOutput('', '}\n')

		data = { }
		for row in self.db.select("name from nodes order by rack, rank"):
			data[row[0]] = []
			
		for row in self.db.select("""
			nodes.name, n.mac, n.ip, n.device
			from networks n, nodes where
			n.node = nodes.id and
			n.mac is not NULL
			"""):
			data[row[0]].append(row[1:])

		kickstartable = { }
		for row in self.call('list.host.attr', [ 'attr=kickstartable' ]):
			kickstartable[row['host']] = self.str2bool(row['attr'])

		for name in data.keys():
			mac = None
			ip  = None
			dev = None
			
			#
			# look for a physical private interface that has an
			# IP address assigned to it.
			#
			for (mac, ip, dev) in data[name]:
				if not ip:
					ip = self.resolve_ip(name, dev)
				netname = None
				if ip:
					r = self.db.select("""
					s.name from subnets s, networks nt,
					nodes n where nt.node=n.id and
					n.name='%s' and nt.subnet=s.id and
					s.pxe = TRUE and nt.ip = '%s'""" % (name, ip))
					if r:
						(netname, ) = r[0]
				if ip and mac and dev and netname:
					self.addOutput('', '\nhost %s.%s.%s {' %
						(name, netname, dev))
					self.addOutput('', '\toption host-name\t"%s";' % name)

					self.addOutput('', '\thardware ethernet\t%s;' % mac)
					self.addOutput('', '\tfixed-address\t\t%s;' % ip)

					if kickstartable[name]:

						self.addOutput('', filename)
						server = servers.get(netname)
						if not server:
							server = servers.get('default')

						self.addOutput('','\tserver-name\t\t"%s";'
							% server)
						self.addOutput('','\tnext-server\t\t%s;'
							% server)
				
					self.addOutput('', '}')

		self.addOutput('', '</stack:file>')

	def resolve_ip(self, host, device):
		(ip, channel), = self.db.select("""nt.ip,
			nt.channel from networks nt, nodes n
			where n.name='%s' and nt.device='%s' and
			nt.node=n.id""" % (host, device))
		if channel:
			return self.resolve_ip(host, channel)
		return ip


	def writeDhcpSysconfig(self):
		self.addOutput('', '<stack:file stack:name="/etc/sysconfig/dhcpd">')
		self.addOutput('', stack.text.DoNotEdit())

		devices = ''
		for device, in self.db.select("""
			device from
			networks n, subnets s
			where n.node = (select id from nodes where name = '%s') and
			s.pxe = TRUE and
			n.subnet = s.id and
			n.ip is not NULL
			""" % self.db.getHostname()):
			devices += '%s ' % device

		if self.os == 'redhat':
			self.addOutput('', 'DHCPDARGS="%s"' % devices.strip())
		if self.os == 'sles':
			self.addOutput('', 'DHCPD_INTERFACE="%s"' % devices.strip())

		self.addOutput('', '</stack:file>')
		

	def run(self, params, args):
		self.beginOutput()
		self.writeDhcpDotConf()
		self.writeDhcpSysconfig()
		self.endOutput(padChar='')

