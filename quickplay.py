# -*- coding: utf-8 -*-
# CC0 1.0 Universal

from steam import client as gs
import json

#change this to the number of servers you want to query
limit = 20

def TrueQuickplayServers():
    servers_info = []
    client = gs.SteamClient()
    client.anonymous_login()
    for server_addr in client.gameservers.get_server_list(r'\appid\440\gametype\truequickplay\secure\1', max_servers=limit):
        servers_info.append(server_addr)
    client.logout()
    return servers_info


json_data = json.dumps(TrueQuickplayServers(), indent=4, sort_keys=True)


# paste to file
with open('quickplay_servers.json', 'w') as f:
    f.write(json_data)