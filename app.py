import base64
import os

import steam.webapi
# flask
from flask import Flask, jsonify, request, render_template
from flask.cli import load_dotenv
from flask_caching import Cache
# steam
from steam import webapi as gs
from steam.exceptions import SteamError
import a2s
import json
# fuzzywuzzy
from fuzzywuzzy import fuzz
import subprocess
# cache clear on exit
import atexit
# config
import configparser
import pylibmc
import sqlite3

load_dotenv()


def cleardb():
    # do it exist?
    if not os.path.exists("ham.db"):
        return
    # clear the database
    conn = sqlite3.connect("ham.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS ham")
    conn.commit()
    conn.close()


atexit.register(cleardb)

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
    memservers = ["127.0.0.1:11211"]
    cache = Cache(app, config={'CACHE_TYPE': "MemcachedCache", 'CACHE_MEMCACHED_SERVERS': memservers})
else:
    cache = Cache(app, config={'CACHE_TYPE': 'FileSystemCache', 'CACHE_DIR': f'{cache_dir}'})
# if the cache is FileSystemCache, we need to clear it on exit
# this is a workaround for the fact that FileSystemCache does not clear on exit
# if we use redis or memcached, we don't need to do this
#
if cfg.get("Cache", "type") == "FileSystemCache":
    atexit.register(cache.clear)

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
    try:
        # Get the server list from the Steam API
        key = os.environ.get("STEAM_API_KEY")
        server_list = gs.webapi_request(
            url=r"https://api.steampowered.com/IGameServersService/GetServerList/v1/",
            method='GET',
            caller=None,
            params={
                "key": key,
                "filter": r"\appid\440\gametype\truequickplay\secure\1",
                "limit": limit,
            },
        )
        for server_addr in server_list.get("response", {}).get("servers", []):
            server_addr["region"] = region_names.get(server_addr["region"])
            servers_info.append(server_addr)
    except SteamError as e:
        app.logger.error(f"An error occurred while getting the server list: {e}")
        return []
    return servers_info


@app.route("/")
@cache.cached(timeout=3600)
def index():
    return render_template("index.html")


@app.route("/servers", methods=["GET"])
@cache.cached(timeout=60)
def get_servers():
    try:
        servers = TrueQuickplayServers()
        sorted_servers = sorted(servers, key=lambda x: x["max_players"], reverse=True)
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
            asyncServerPing(selected_server)
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
def server_list():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
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
        total_servers = len(servers)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_servers = servers[start:end]
        
        return render_template("server_list.html", servers=paginated_servers, page=page, per_page=per_page,
                               total_servers=total_servers)
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


# hacky way to cache the images because pylibmc is gay and will not work
hamcache = Cache(app, config={'CACHE_TYPE': 'FileSystemCache', 'CACHE_DIR': f'{cache_dir}'})
atexit.register(hamcache.clear)


@app.route("/hampics", methods=["GET"])
@hamcache.cached(timeout=30)
def ham_images():
    try:
        pic_ham = "images"
        # get the list of ham pics
        # if the directory does not exist, create it
        if not os.path.exists(pic_ham):
            os.makedirs(pic_ham)
        # initialize the database
        conn = sqlite3.connect("ham.db")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS ham (id INTEGER PRIMARY KEY, image TEXT)"
            )
        cursor.execute("SELECT COUNT(*) FROM ham")
        # add the images to the database
        images = [
            (sqlite3.Binary(open(os.path.join(pic_ham, filename), 'rb').read()),)
            for filename in os.listdir(pic_ham)
            if filename.endswith(".jpg") or filename.endswith(".png")
            ]
        cursor.executemany("INSERT INTO ham (image) VALUES (?)", images)
        conn.commit()
        
        # fetch a random image from the database
        cursor.execute("SELECT image FROM ham ORDER BY RANDOM() LIMIT 1")
        rows = cursor.fetchall()
        conn.close()
        
        # jsonify the images
        ham_pics = [base64.b64encode(row[0]).decode('utf-8') for row in rows]
        return jsonify({"ham_pics": ham_pics})
    except sqlite3.Error as e:
        app.logger.error(f"An error occurred with the database: {e}")
        return jsonify({"error": "An error occurred with the database"}), 500
    except OSError as e:
        app.logger.error(f"An OS error occurred: {e}")
        return jsonify({"error": "An OS error occurred"}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@app.route("/ham")
def ham():
    # god im hungry
    return render_template("ham.html")


@app.route("/health_check", methods=["GET"])
def health_check():
    # Health check endpoint
    return jsonify({"status": "ok"}), 200


@app.route("/load_balancer", methods=["POST"])
def nameOfLoadBalancer():
    lbn = cfg.get("LB", "lb_name")
    return jsonify({"LB": lbn}), 200


if __name__ == "__main__":
    app.run(debug=False)
