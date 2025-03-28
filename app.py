import os
# flask
from flask import Flask, jsonify, request, render_template
from flask_caching import Cache
# steam
from steam import client as gs
from steam import game_servers as lgs
import a2s
import json
# fuzzywuzzy
from fuzzywuzzy import fuzz
import subprocess
# cache clear on exit
import atexit
# config
import configparser

cfg = configparser.ConfigParser()

cfg.read("config.ini")
# LEGACY: Set the cache directory
cache_dir = "cache/flask_cache"
app = Flask(__name__)

if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

if cfg.get("Cache", "type") == "FileSystemCache":
    cache = Cache(app, config={'CACHE_TYPE': 'FileSystemCache', 'CACHE_DIR': f'{cache_dir}'})
elif cfg.get("Cache", "type") == "MemcachedCache":
    cache = Cache(app, config={'CACHE_TYPE': "MemcachedCache"})
else:
    cache = Cache(app, config={'CACHE_TYPE': 'FileSystemCache', 'CACHE_DIR': f'{cache_dir}'})
# if the cache is FileSystemCache, we need to clear it on exit
# this is a workaround for the fact that FileSystemCache does not clear on exit
# if we use redis or memcached, we don't need to do this
#
if cfg.get("Cache", "type") == "FileSystemCache":
    atexit.register(cache.clear)

if cfg is None:
    limit = 50
else:
    limit = cfg.getint("Main", "limit")

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


async def asyncServerPing(server):
    # Calculate ping
    # steam has a way to get ping, but it's not very reliable
    # so we use a2s instead
    ip, port = server["addr"].split(":")
    port = int(port)
    ip_tuple = (ip, port)
    server_info = await a2s.ainfo(ip_tuple, timeout=20, encoding=None)
    server["ping"] = round(server_info.ping * 1000)


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
@cache.cached(timeout=60)
async def get_servers():
    try:
        servers = TrueQuickplayServers()
        sorted_servers = sorted(servers, key=lambda x: x["players"], reverse=True)
        blacklist = load_blacklist()
        greylist = load_greylist()
        
        selected_server = None
        
        for server in sorted_servers:
            server_name = server["name"]
            # Check if the server name contains any forbidden words
            if any(fuzz.partial_ratio(server_name, item) > 80 for item in blacklist):
                continue
                # If the server name contains any forbidden words, skip it
                # and continue to the next server
                # we hide the server name to prevent the user from seeing it
                # and to prevent the user from connecting to it
            greylisted_server = next(
                (item for item in greylist if fuzz.partial_ratio(server_name, item["Server"]) > 80), None
                )
            if greylisted_server:
                selected_server = server
                selected_server["greylisted"] = True
                selected_server["reason"] = greylisted_server["Reason"]
                break
            if server["players"] < server["max_players"]:
                selected_server = server
                selected_server["greylisted"] = False
                break
        
        if selected_server is None:
            app.logger.error("No servers found")
            return jsonify({"message": "No servers found"}), 404
        else:
            await asyncServerPing(selected_server)
            return jsonify(selected_server)
    
    except IOError as e:
        app.logger.error(f"An IOError occurred while reading the file: {e}")
        return jsonify({"error": "An error occurred while reading the file"}), 500
    except (KeyError, ValueError) as e:
        app.logger.error(f"An error occurred while processing the data: {e}")
        return (
            jsonify({"error": f"An error occurred while processing the data"}),
            500,
            )


@app.route("/connect", methods=["POST"])
def connect_server():
    data = request.json
    ip = data.get("ip")
    if not ip:
        return jsonify({"error": "IP address is required"}), 400
    cmd = f"steam://connect/{ip}"
    
    return jsonify({"url": cmd}), 200


@app.route("/server_list")
@cache.cached(timeout=60)
def server_list():
    try:
        servers = TrueQuickplayServers()
        blacklist = load_blacklist()
        greylist = load_greylist()
        for server in servers:
            server_name = server["name"]
            if any(fuzz.partial_ratio(server_name, item) > 80 for item in blacklist):
                server["blacklisted"] = True
            greylisted_server = next(
                (item for item in greylist if fuzz.partial_ratio(server_name, item["Server"]) > 80), None
                )
            if greylisted_server:
                server["greylisted"] = True
                server["reason"] = greylisted_server["Reason"]
        
        return render_template("server_list.html", servers=servers)
    except IOError as e:
        app.logger.error(f"An IOError occurred while reading the file: {e}")
        return jsonify({"error": f"An error occurred while reading the file"}), 500
    except (KeyError, ValueError) as e:
        app.logger.error(f"An error occurred while processing the data: {e}")
        return jsonify({"error": f"An error occurred while processing the data"}), 500


@app.route("/rawjson")
@cache.cached(timeout=60)
def rawjson():
    try:
        json_data = json.dumps(TrueQuickplayServers(), indent=4, sort_keys=True)
        return json_data
    except IOError as e:
        app.logger.error(f"An IOError occurred while reading the file: {e}")
        return jsonify({"error": f"An error occurred while reading the file"}), 500
    except (KeyError, ValueError) as e:
        app.logger.error(f"An error occurred while processing the data: {e}")
        return (
            jsonify({"error": f"An error occurred while processing the data"}),
            500,
            )


@app.route("/xlists")
@cache.cached(timeout=60)
def xlists():
    try:
        greylist = load_greylist()
        return render_template("xlists.html", greylist=greylist)
    except IOError as e:
        app.logger.error(f"An IOError occurred while reading the file: {e}")
        return jsonify({"error": "An internal error has occurred while reading the file."}), 500
    except (KeyError, ValueError) as e:
        app.logger.error(f"An error occurred while processing the data: {e}")
        return jsonify({"error": "An internal error has occurred while processing the data."}), 500


@app.route("/git", methods=["POST"])
def git():
    try:
        git_hash_file = "git_hash.txt"
        current_git_hash = None
        
        # Check if the git_hash.txt file exists
        if os.path.exists(git_hash_file):
            with open(git_hash_file, "r") as f:
                cached_git_hash = f.read().strip()
            
            # Get the current Git hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, shell=False
                )
            current_git_hash = result.stdout.strip()
            
            # If the cached hash is different from the current hash, update the cache
            if cached_git_hash != current_git_hash:
                with open(git_hash_file, "w") as f:
                    f.write(current_git_hash)
        else:
            # If the file does not exist, get the current Git hash and create the file
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, shell=False
                )
            current_git_hash = result.stdout.strip()
            with open(git_hash_file, "w") as f:
                f.write(current_git_hash)
        
        return jsonify({"git_hash": current_git_hash}), 200
    except subprocess.CalledProcessError as e:
        app.logger.error(f"An error occurred while getting the git hash: {e}")
        return jsonify({"error": "An error occurred while getting the git hash"}), 500


if __name__ == "__main__":
    app.run(debug=False)
