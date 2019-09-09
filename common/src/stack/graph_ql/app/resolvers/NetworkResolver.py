# @copyright@
# Copyright (c) 2006 - 2019 Teradata
# All rights reserved. Stacki(r) v5.x stacki.com
# https://github.com/Teradata/stacki/blob/master/LICENSE.txt
# @copyright@

import ipaddress
from ariadne import ObjectType, QueryType, MutationType
import app.db as db
from app.resolvers.OSResolver import resolve_oses

query = QueryType()
mutation = MutationType()

@query.field("networks")
def resolve_networks(_, info, id=None, name=None):
    query_str = "SELECT id, name, address, mask, gateway, mtu, zone, dns, pxe FROM subnets  WHERE 1 = 1"
    if id:
        query_str = "%s AND id = %s" % (query_str, id)
    elif name:
        query_str = "%s AND name = \"%s\"" % (query_str, name)
    results, _ = db.run_sql(query_str)
    return results

@mutation.field("addNetwork")
def resolve_add_network(_, info, name, address, mask, gateway=None, zone="", mtu=None, dns=False, pxe=False):
    # TODO: get default os FROM frontend's os

    if name in [network["name"] for network in resolve_networks(None, None)]:
        raise Exception(f"network {name} exists")

    #validate ip-address
    try:
        ipaddress.IPv4Network(f'{address}/{mask}')
    except:
        msg = '%s/%s is not a valid network address and subnet mask combination'
        raise Exception(msg % (address, mask))

    # Insert network
    cmd = "INSERT INTO subnets (name, address, mask, gateway, zone, mtu, dns, pxe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    args = (name, address, mask, gateway, zone, mtu, dns, pxe)
    results, _ = db.run_sql(cmd, args)

    # Get the recently inserted value
    cmd = "SELECT id, name, os AS os_id FROM boxes WHERE name=%s"
    args = (name,)
    results, _ = db.run_sql(cmd, args, fetchone=True)
    return results

@mutation.field("deleteNetwork")
def resolve_delete_box(_, info, id):

    cmd = "DELETE FROM subnets WHERE id=%s"
    args = (id,)
    _, affected_rows = db.run_sql(cmd, args)

    if not affected_rows:
        return False

    return True


object_types = []