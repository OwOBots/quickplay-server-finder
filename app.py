import os
from flask import Flask, jsonify, request, render_template
from steam import client as gs
import json
from fuzzywuzzy import fuzz

app = Flask(__name__)


limit = 20

# 2 world regions are listed because the region code -1 and 225 is used
region_names = {
    -1: "World",
    0: "US - East",
    1: "US - West",
    2: "South America",
    3: "Europe",
    4: "Asia",
    5: "Australia",
    6: "Middle East",
    7: "Africa",
    255: "World"
    }


def load_blacklist():
    with open("blacklist.json", "r") as f:
        return json.load(f)


def load_greylist():
    with open("greylist.json", "r") as f:
        return json.load(f)


def TrueQuickplayServers():
    servers_info = []
    client = gs.SteamClient()
    client.anonymous_login()
    for server_addr in client.gameservers.get_server_list(
            r"\appid\440\gametype\truequickplay\secure\1", max_servers=limit
            ):
        server_addr["region"] = region_names.get(server_addr["region"])
        servers_info.append(server_addr)
    client.logout()
    return servers_info


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/servers", methods=["GET"])
def get_servers():
    try:
        servers = TrueQuickplayServers()
        sorted_servers = sorted(servers, key=lambda x: x["players"], reverse=True)
        blacklist = load_blacklist()
        greylist = load_greylist()
        
        selected_server = None
        for server in sorted_servers:
            server_name = server["name"]
            # Check if the server name contains any forbidden words
            if fuzz.partial_ratio(server_name, blacklist) > 80:
                # If the server name contains any forbidden words, skip it
                # and continue to the next server
                # we hide the server name to prevent the user from seeing it
                # and to prevent the user from connecting to it
                continue
            if fuzz.partial_ratio(server_name, greylist) > 80:
                selected_server = server
                # greylisted servers are not preferred but are still valid so we will return a warning message instead
                selected_server["greylisted"] = True
                break
            if server["players"] < server["max_players"]:
                selected_server = server
                selected_server["greylisted"] = False
                break
        
        if selected_server is None:
            return jsonify({"message": "No servers found"}), 404
        else:
            return jsonify(selected_server)
    
    
    except IOError as e:
        return jsonify({"error": f"An error occurred while reading the file: {e}"}), 500
    except (KeyError, ValueError) as e:
        return (
            jsonify({"error": f"An error occurred while processing the data: {e}"}),
            500,
            )


@app.route("/connect", methods=["POST"])
def connect_server():
    data = request.json
    ip = data.get("ip")
    if not ip:
        return jsonify({"error": "IP address is required"}), 400
    # This code is commented out because it's wont work in a web server
    # so we will just use the web browser built-in function to open the link
    
    cmd = f"steam://connect/{ip}"
    
    ''' cmd = f"steam://connect/{ip}"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "start", cmd], shell=False)
    else:
        subprocess.run(["xdg-open", cmd], shell=False) '''
    
    return jsonify({"url": cmd}), 200


@app.route("/rawjson")
def rawjson():
    try:
        json_data = json.dumps(TrueQuickplayServers(), indent=4, sort_keys=True)
        return json_data
    except IOError as e:
        return jsonify({"error": f"An error occurred while reading the file: {e}"}), 500
    except (KeyError, ValueError) as e:
        return (
            jsonify({"error": f"An error occurred while processing the data: {e}"}),
            500,
            )


@app.route("/xlists")
def xlists():
    try:
        greylist = load_greylist()
        return render_template("xlists.html", greylist=greylist)
    except IOError as e:
        return jsonify({"error": f"An error occurred while reading the file: {e}"}), 500
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"An error occurred while processing the data: {e}"}), 500


if __name__ == "__main__":
    app.run(debug=False)
