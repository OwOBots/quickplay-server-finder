# -*- coding: utf-8 -*-
# CC0 1.0 Universal
import os
import subprocess
from steam import client as gs
import json

# change this to the number of servers you want to query
limit = 20


def load_blacklist():
    with open('blacklist.json', 'r') as f:
        return json.load(f)


def load_greylist():
    with open('greylist.json', 'r') as f:
        return json.load(f)


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


def main():
    # Give the user the server with the most players
    try:
        json_data = json.dumps(TrueQuickplayServers(), indent=4, sort_keys=True)
        
        # paste to file
        with open('quickplay_servers.json', 'w') as f:
            f.write(json_data)
        
        with open('quickplay_servers.json', 'r') as f:
            data = json.load(f)
            
            sorted_servers = sorted(data, key=lambda x: x['players'], reverse=True)
            
            selected_servers = None
            for server in sorted_servers:
                if server['players'] < server['max_players']:
                    selected_servers = server
                    break
            
            if selected_servers is None:
                print("No servers found")
            else:
                # Find the server with the most players
                max_players = max(data, key=lambda x: x['max_players'])
                most_players_server = max(data, key=lambda x: x['players'])
                player_count = most_players_server['players']
                ip = most_players_server['addr']
                server_name = most_players_server['name']
                print("Server with the most players:", server_name, "with", player_count, "players online", "at", ip)
                
                def server_connect():
                    server_connect_prompt = input("Would you like to connect to this server? (y/N): ")
                    if server_connect_prompt == 'y':
                        cmd = f"steam://connect/{ip}"
                        # if the user is on windows, use start
                        if os.name == 'nt':
                            subprocess.run(["cmd", "/c", "start", cmd], shell=False)
                        else:
                            subprocess.run(["xdg-open", cmd], shell=False)
                
                if server in load_greylist():
                    greylist_reason = server['Reason']
                    greylist_prompt = input(
                        f"{server_name} is grey-listed because of: {greylist_reason}, do you want to connect to it?"
                        )
                    if greylist_prompt == 'y':
                        server_connect()
                elif server in load_blacklist():
                    print(f"Server is blacklisted, skipping...")
                else:
                    server_connect()
    
    except IOError as e:
        print(f"An error occurred while reading the file: {e}")
    except (KeyError, ValueError) as e:
        print(f"An error occurred while processing the data: {e}")
    
    print("Done! Servers saved to quickplay_servers.json")


if __name__ == "__main__":
    main()
