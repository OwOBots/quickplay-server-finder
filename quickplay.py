# -*- coding: utf-8 -*-
# CC0 1.0 Universal
import os
import subprocess


from steam import client as gs
import json

#change this to the number of servers you want to query
limit = 20


def TrueQuickplayServers():
    servers_info = []
    client = gs.SteamClient()
    client.anonymous_login()
    for server_addr in client.gameservers.get_server_list(
            r'\appid\440\gametype\truequickplay\secure\1', max_servers=limit
            ):
        servers_info.append(server_addr)
    client.logout()
    return servers_info


json_data = json.dumps(TrueQuickplayServers(), indent=4, sort_keys=True)

# paste to file
with open('quickplay_servers.json', 'w') as f:
    f.write(json_data)

# Give the user the server with the most players
try:
    with open('quickplay_servers.json', 'r') as f:
        data = json.load(f)
        # Find the server with the most players
        most_players_server = max(data, key=lambda x: x['players'])
        ip = most_players_server['addr']
        server_name = most_players_server['name']
        print("Server with the most players:", server_name, "at", ip)
        server_connect_prompt = input("Would you like to connect to this server? (y/n): ")
        if server_connect_prompt == 'y':
            cmd = f"steam://connect/{ip}"
            #if the user is on windows, use start
            if os.name == 'nt':
                subprocess.run(["cmd", "/c", "start", cmd], shell=False)
            else:
                subprocess.run(["xdg-open", cmd], shell=False)

except IOError as e:
    print(f"An error occurred while reading the file: {e}")
except (KeyError, ValueError) as e:
    print(f"An error occurred while processing the data: {e}")

print("Done! Servers saved to quickplay_servers.json")
